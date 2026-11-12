"""Immutable, real JRA POST-RACE final-only settlement-source journal.

It accepts only actual previously archived JRA result bytes under pinned SHA.
A race FINAL is a source observation, NOT a prior prediction, purchase, or
profit. All labels are post-race, no network or Turso or production operations.
Separate DB so synthetic investment journal cannot launder post-race outcomes.
"""
from __future__ import annotations
import hashlib,json,re,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from diagnostics.kyoto_p6_real_historical_final_payout_reaudit import (
    extract_real_two_race_payouts, RealHistoricalPayoutRejected
)

class OfficialSourceRegistryRejected(ValueError):pass
ZERO="0"*64
def canonical(o):
    return json.dumps(o,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
def digest(o):return hashlib.sha256(canonical(o).encode("utf-8")).hexdigest()
def _check(cond,reason):
    if not cond:raise OfficialSourceRegistryRejected(reason)
def _db(path):
    p=Path(path)
    _check(not p.is_symlink() and not p.exists() or (p.is_file() and not p.is_symlink()),
           "invalid_registry_path")
    p.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(p,timeout=10,isolation_level=None)
    c.execute("PRAGMA busy_timeout=10000")
    c.execute("PRAGMA synchronous=FULL")
    c.execute("""CREATE TABLE IF NOT EXISTS official_postrace_observations(
       seq INTEGER PRIMARY KEY AUTOINCREMENT,
       event_key TEXT NOT NULL UNIQUE,
       race_id TEXT NOT NULL,
       observed_at_utc TEXT NOT NULL,
       raw_payload TEXT NOT NULL,
       prior_sha256 TEXT NOT NULL,
       event_sha256 TEXT NOT NULL UNIQUE)""")
    c.execute("""CREATE TRIGGER IF NOT EXISTS official_postrace_no_update
       BEFORE UPDATE ON official_postrace_observations
       BEGIN SELECT RAISE(ABORT,'immutable_official_observation'); END""")
    c.execute("""CREATE TRIGGER IF NOT EXISTS official_postrace_no_delete
       BEFORE DELETE ON official_postrace_observations
       BEGIN SELECT RAISE(ABORT,'immutable_official_observation'); END""")
    return c
def _read(c):
    prev=ZERO
    events=[]
    for seq,key,rid,at,raw,previous,record_hash in c.execute(
        "SELECT seq,event_key,race_id,observed_at_utc,raw_payload,prior_sha256,event_sha256 "
        "FROM official_postrace_observations ORDER BY seq"):
        try:p=json.loads(raw)
        except (ValueError,TypeError):
            raise OfficialSourceRegistryRejected("corrupted_json") from None
        _check(raw==canonical(p) and previous==prev,"corrupted_event_encoding_or_chain")
        _check(record_hash==digest({"event_key":key,"race_id":rid,
               "observed_at_utc":at,"payload":p,"prior_sha256":previous}),"corrupted_event_sha")
        _check(p.get("source_type")=="OFFICIAL_HISTORICAL_POST_RACE_FINAL"
               and p.get("no_prerace_bets_asserted") is True
               and p.get("payouts_are_genuine_final_not_prerace_odds") is True,
               "false_source_status")
        _check(key=="official_final:"+rid and rid==p["date"]+"-KYOTO-R"+f"{p['race_number']:02d}",
               "race_identity_corrupt")
        prev=record_hash
        events.append({"key":key,"race_id":rid,"observed_at_utc":at,
                       "event_sha256":record_hash,"payload":p})
    return events,prev
def validate_time(t):
    _check(type(t) is str and t.endswith("Z"),"utc_z_required")
    try:d=datetime.fromisoformat(t.replace("Z","+00:00"))
    except ValueError:
        raise OfficialSourceRegistryRejected("bad_utc") from None
    _check(d.utcoffset().total_seconds()==0,"non_utc")
    return d

def register_actual_final_sources(db_path,source_archive_bytes,*,observed_at_utc):
    stamp=validate_time(observed_at_utc)
    source=extract_real_two_race_payouts(source_archive_bytes)
    payloads=source["races"]
    _check(len(payloads)==2 and source["real_final_payout_pairs_verified"]==4,"archive_incomplete")
    for item in payloads:
        day=datetime.fromisoformat(item["date"]+"T00:00:00+00:00")
        _check(stamp>day and stamp.year>=2026,"observation_prior_to_race")
    c=_db(db_path)
    try:
        c.execute("BEGIN IMMEDIATE")
        current,chain=_read(c)
        by_key={e["key"]:e for e in current}
        seen=0
        new=0
        for item in payloads:
            rid=item["date"]+"-KYOTO-R"+f"{item['race_number']:02d}"
            key="official_final:"+rid
            if key in by_key:
                _check(by_key[key]["payload"]==item and
                       by_key[key]["observed_at_utc"]<=observed_at_utc,
                       "immutable_conflict_or_time_rollback")
                seen+=1
                continue
            raw=canonical(item)
            body={"event_key":key,"race_id":rid,"observed_at_utc":observed_at_utc,
                  "payload":item,"prior_sha256":chain}
            new_hash=digest(body)
            c.execute("INSERT INTO official_postrace_observations(event_key,race_id,observed_at_utc,raw_payload,prior_sha256,event_sha256) VALUES(?,?,?,?,?,?)",
                      (key,rid,observed_at_utc,raw,chain,new_hash))
            chain=new_hash
            new+=1
        after,head=_read(c)
        _check(len(after)==len(current)+new and len(after)<=2,
               "unexpected_registry_event_count")
        c.execute("COMMIT")
        return {"schema":"kyoto_actual_official_postrace_registry.v1",
                "scope":"ACTUAL_JRA_HISTORICAL_POST_RACE_SOURCE_ONLY",
                "new_final_sources":new,"already_present":seen,
                "total_final_sources":len(after),"chain_head":head,
                "source_archive_sha256":hashlib.sha256(source_archive_bytes).hexdigest(),
                "pre_race_odds_verified":False,"real_paper_trading_verified":False,
                "pnl_computed":False,"real_bet_authorized":False}
    except Exception:
        c.execute("ROLLBACK")
        raise
    finally:c.close()

def replay_official_sources(db_path):
    _check(Path(db_path).is_file(),"no_existing_official_source_journal")
    c=_db(db_path)
    try:events,head=_read(c)
    finally:c.close()
    _check(len(events)<=2,"unexpected_record_count")
    return {"schema":"kyoto_actual_official_postrace_replay.v1",
            "source_scope":"ACTUAL_JRA_POST_RACE_FINAL_ONLY",
            "count":len(events),"chain_head":head,
            "races":[{"race_id":e["race_id"],"event_sha256":e["event_sha256"],
                     "quinella":e["payload"]["quinella_final"],
                     "bracket":e["payload"]["bracket_final"],
                     "source_sha256":e["payload"]["source_sha256"]}
                     for e in events],
            "pre_race_investment_or_profit_proven":False}
