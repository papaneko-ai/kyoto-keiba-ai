"""P1-FB durable GLOBAL one-shot attempt registry (OFFLINE gate).

No network client. A reserved URL is consumed even if processing crashes.
SQLite BEGIN IMMEDIATE serializes competing processes. This is a conservative
coordination primitive, not legal authorization or a working live crawler.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3

from diagnostics.jra_p1_fb_request_budget_policy import official

class Blocked(ValueError):
    pass

def utc_seconds(t):
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise Blocked("naive_or_missing_clock")
    return t.astimezone(timezone.utc).timestamp()

class GlobalAttemptRegistry:
    def __init__(self, db_path, *, max_attempts=24, gap_seconds=2):
        path=Path(db_path)
        if not path.parent.is_dir() or path.is_symlink():
            raise Blocked("unsafe_registry_path")
        if not isinstance(max_attempts,int) or type(max_attempts) is not int or max_attempts<1:
            raise Blocked("invalid_attempt_budget")
        if gap_seconds < 2:
            raise Blocked("unsafe_interval")
        self.path=str(path)
        self.max_attempts=max_attempts
        self.gap_seconds=gap_seconds
        self._schema()

    def _connect(self):
        db=sqlite3.connect(self.path, isolation_level=None, timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _schema(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS attempts(
                attempt_id INTEGER PRIMARY KEY,
                channel TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                race_key TEXT NOT NULL,
                horse_number INTEGER NOT NULL,
                roster_sha TEXT NOT NULL,
                reserved_utc REAL NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('RESERVED','RECEIPT_RECORDED')),
                detail TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS attempt_identity ON attempts(race_key,horse_number)")
            db.execute("""CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY, value TEXT NOT NULL)""")

    def reserve(self, *, channel, url, race_key, horse_number, roster_sha,
                now, cutoff, official_roster_observed, require_fresh=True):
        """Single-use reservation; independent of per-incident folders.

        Failures or crashes do NOT release the URL. Same horse may be retried
        only on a different, independently proven channel by upstream policy.
        This method never makes an HTTP request.
        """
        ts=utc_seconds(now); limit=utc_seconds(cutoff)
        if not require_fresh or not official_roster_observed:
            raise Blocked("missing_new_official_roster_evidence")
        if not official(channel,url) or not re.fullmatch(r"[0-9a-f]{64}", roster_sha):
            raise Blocked("untrusted_official_url_or_roster")
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}_KYOTO_\d{2}R",race_key):
            raise Blocked("invalid_race_key")
        if type(horse_number) is not int or not 1<=horse_number<=18:
            raise Blocked("invalid_horse_number")
        if ts>=limit:
            raise Blocked("prediction_cutoff_passed")
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT COUNT(*),MAX(reserved_utc) FROM attempts").fetchone()
            count,last=row
            if count>=self.max_attempts:
                raise Blocked("global_request_budget_exhausted")
            if last is not None and (ts<last or ts-last<self.gap_seconds):
                raise Blocked("global_gap_or_clock_rollback")
            if db.execute("SELECT 1 FROM attempts WHERE url=?",(url,)).fetchone():
                raise Blocked("url_already_attempted_globally")
            if db.execute("SELECT 1 FROM attempts WHERE race_key=? AND horse_number=? AND channel=?",
                          (race_key,horse_number,channel)).fetchone():
                raise Blocked("same_horse_channel_already_consumed")
            db.execute("""INSERT INTO attempts
                      (channel,url,race_key,horse_number,roster_sha,reserved_utc,state)
                      VALUES(?,?,?,?,?,?,'RESERVED')""",
                       (channel,url,race_key,horse_number,roster_sha,ts))
            rid=db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("COMMIT")
            return rid
        except sqlite3.IntegrityError as err:
            if db.in_transaction: db.execute("ROLLBACK")
            raise Blocked("duplicate_global_reservation") from err
        except BaseException:
            if db.in_transaction: db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def attach_receipt(self, *, attempt_id, detail):
        """Document an already reserved attempt. Does not make it retriable."""
        if not isinstance(detail,str) or not detail or len(detail)>2048:
            raise Blocked("invalid_receipt_detail")
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT state FROM attempts WHERE attempt_id=?",(attempt_id,)).fetchone()
            if row is None or row[0]!="RESERVED":
                raise Blocked("attempt_missing_or_receipt_already_recorded")
            db.execute("UPDATE attempts SET state='RECEIPT_RECORDED',detail=? WHERE attempt_id=?",
                       (detail,attempt_id))
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction: db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def inventory(self):
        with self._connect() as db:
            rows=db.execute("""SELECT channel,url,race_key,horse_number,reserved_utc,state,detail
                          FROM attempts ORDER BY attempt_id""").fetchall()
            return [dict(zip(("channel","url","race_key","horse_number","reserved_utc","state","detail"),r))
                    for r in rows]

    def unresolved(self):
        return [x for x in self.inventory() if x["state"]=="RESERVED"]
