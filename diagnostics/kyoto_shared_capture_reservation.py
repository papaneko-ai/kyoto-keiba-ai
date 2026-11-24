"""Cross-host acquisition coordination using one shared transactional database.

Reservation keys contain the scheduled slot, so a prior window never blocks
another. Atomic BEGIN IMMEDIATE, lease fencing, and conditional completion
prevent two workers from owning the same opportunity simultaneously.
This module only implements the coordination protocol; live Turso wiring
is a separate deployment decision. No JRA HTTP is performed here.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib,re,sqlite3
from pathlib import Path

VALID_DAY=frozenset(("20261121","20261122","20261128","20261129"))
VALID_MARKET=frozenset(("racecard","quinella","bracket_quinella","profile"))
VALID_CHANNEL=frozenset(("PC","SP"))
class ReservationError(ValueError):pass
def key(*,day,slot,race,channel,market):
    if day not in VALID_DAY or type(slot) is not int or not 0<=slot<=3:
        raise ReservationError("invalid_day_or_slot")
    if type(race) is not int or not 1<=race<=12 or channel not in VALID_CHANNEL or market not in VALID_MARKET:
        raise ReservationError("invalid_race_channel_or_market")
    return f"{day}:{slot}:{race:02d}:{channel}:{market}"

class SharedLedger:
    """SQLite backend for concurrency testing; same SQL can be ported to Turso."""
    def __init__(self,path):
        self.path=str(path)
        self.db=sqlite3.connect(self.path,timeout=15,isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS capture_claims ("
                        "claim_key TEXT PRIMARY KEY, owner TEXT NOT NULL,"
                        "generation INTEGER NOT NULL, expires_at INTEGER NOT NULL,"
                        "state TEXT NOT NULL CHECK(state IN ('LEASED','DONE')),"
                        "receipt_sha256 TEXT)")
    def close(self):self.db.close()
    def _begin(self):self.db.execute("BEGIN IMMEDIATE")
    def claim(self,*,claim_key,owner,now_epoch,lease_seconds=180):
        if (not isinstance(claim_key,str) or
            not re.fullmatch(r"2026112[1289]:[0-3]:(0[1-9]|1[0-2]):(PC|SP):(racecard|quinella|bracket_quinella|profile)",claim_key)):
            raise ReservationError("claim_key_invalid")
        if not isinstance(owner,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{5,100}",owner):
            raise ReservationError("owner_invalid")
        if type(now_epoch) is not int or now_epoch<=0 or type(lease_seconds) is not int or not 30<=lease_seconds<=1800:
            raise ReservationError("lease_parameters_invalid")
        self._begin()
        try:
            row=self.db.execute("SELECT owner,generation,expires_at,state,receipt_sha256 FROM capture_claims WHERE claim_key=?",(claim_key,)).fetchone()
            if row and row[3]=="DONE":
                answer={"state":"DONE_REUSE_EXISTING","generation":row[1],
                        "receipt_sha256":row[4],"must_fetch":False}
            elif row and row[2]>now_epoch:
                answer={"state":"ACTIVE_LEASE","generation":row[1],
                        "must_fetch":False}
            else:
                generation=(row[1]+1 if row else 1)
                self.db.execute("INSERT INTO capture_claims(claim_key,owner,generation,expires_at,state,receipt_sha256) VALUES(?,?,?,?, 'LEASED',NULL) ON CONFLICT(claim_key) DO UPDATE SET owner=excluded.owner,generation=excluded.generation,expires_at=excluded.expires_at,state='LEASED',receipt_sha256=NULL",
                                (claim_key,owner,generation,now_epoch+lease_seconds))
                answer={"state":"ACQUIRED" if not row else "EXPIRED_LEASE_TAKEN_OVER",
                        "generation":generation,"must_fetch":True}
            self.db.execute("COMMIT")
            return answer
        except Exception:
            self.db.execute("ROLLBACK")
            raise
    def complete(self,*,claim_key,owner,generation,sha256):
        if (type(generation) is not int or generation<1 or
            not isinstance(sha256,str) or not re.fullmatch(r"[a-f0-9]{64}",sha256)):
            raise ReservationError("completion_identity_invalid")
        self._begin()
        try:
            changed=self.db.execute("UPDATE capture_claims SET state='DONE',receipt_sha256=? WHERE claim_key=? AND owner=? AND generation=? AND state='LEASED'",
                        (sha256,claim_key,owner,generation)).rowcount
            self.db.execute("COMMIT")
            return {"state":"COMMITTED" if changed==1 else "FENCE_REJECTED",
                    "committed":changed==1}
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def abandon(self,*,claim_key,owner,generation,now_epoch):
        """Release a failed fetch so another worker can retry in the same slot."""
        if type(generation) is not int or generation<1 or type(now_epoch) is not int:
            raise ReservationError("abandon_parameters_invalid")
        self._begin()
        try:
            changed=self.db.execute(
                "UPDATE capture_claims SET expires_at=? WHERE claim_key=? AND owner=? AND generation=? AND state='LEASED'",
                (now_epoch,claim_key,owner,generation)).rowcount
            self.db.execute("COMMIT")
            return {"released":changed==1}
        except Exception:
            self.db.execute("ROLLBACK")
            raise
