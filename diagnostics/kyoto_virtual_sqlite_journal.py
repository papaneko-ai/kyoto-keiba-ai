"""Durable SQLite VIRTUAL-ONLY paper ledger for source-linked integration testing.

NOT a JRA-authenticated live prediction/settlement service. Production Turso,
old public app, and all real-money channels are unreachable. This validates
idempotent multi-session persistence, pre-cutoff freezes, append-only correction
events and independent replay. Historical final odds are never accepted as
documented pre-race observations by this module.
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "kyoto_p6_virtual_sqlite_journal.v1"
ZERO = "0" * 64
HEX = re.compile(r"^[0-9a-f]{64}$")
MAX_EVENT_BYTES = 100_000

class VirtualLedgerRejected(ValueError):
    pass

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)

def sha(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()

def utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise VirtualLedgerRejected("utc_z_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise VirtualLedgerRejected("utc_invalid") from e
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise VirtualLedgerRejected("utc_offset_invalid")
    return parsed

def _hash(value, name):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise VirtualLedgerRejected(name + "_must_be_sha256")

def _money(v, name, zero=False):
    if type(v) is not int or v < (0 if zero else 100) or v % 100:
        raise VirtualLedgerRejected(name + "_must_be_100yen_units")

def _pair(p):
    if not isinstance(p, list) or len(p) != 2 or any(type(n) is not int or n < 1 or n > 18 for n in p):
        raise VirtualLedgerRejected("pair_invalid")
    if p[0] >= p[1]:
        raise VirtualLedgerRejected("pair_must_be_ascending_distinct")
    return tuple(p)

def validate_freeze(p):
    if not isinstance(p, dict) or set(p) != {
        "race_id", "race_start_utc", "frozen_utc", "source_observed_utc",
        "source_sha256", "model_sha256", "model_version", "ticket_type",
        "tickets", "daily_budget_yen", "provenance_scope"
    }:
        raise VirtualLedgerRejected("freeze_schema_invalid")
    if p["provenance_scope"] != "UNAUTHENTICATED_LAB_INPUT":
        raise VirtualLedgerRejected("live_source_certification_not_supported")
    if not isinstance(p["race_id"], str) or not re.fullmatch(r"20\d{6}-KYOTO-R(?:0[1-9]|1[0-2])", p["race_id"]):
        raise VirtualLedgerRejected("race_id_invalid")
    if not isinstance(p["model_version"], str) or not 1 <= len(p["model_version"]) <= 100:
        raise VirtualLedgerRejected("model_version_invalid")
    if p["ticket_type"] not in ("QUINELLA", "BRACKET"):
        raise VirtualLedgerRejected("ticket_type_invalid")
    for k in ("source_sha256", "model_sha256"):
        _hash(p[k], k)
    if not utc(p["source_observed_utc"]) <= utc(p["frozen_utc"]) < utc(p["race_start_utc"]):
        raise VirtualLedgerRejected("not_a_prerace_freeze")
    if utc(p["frozen_utc"]).timestamp() > utc(p["race_start_utc"]).timestamp() - 600:
        raise VirtualLedgerRejected("ten_minute_cutoff_violated")
    _money(p["daily_budget_yen"], "daily_budget", zero=True)
    if type(p["tickets"]) is not list or len(p["tickets"]) not in (1,2,3):
        raise VirtualLedgerRejected("tickets_count_invalid")
    seen, spent = set(), 0
    for t in p["tickets"]:
        if not isinstance(t, dict) or set(t) != {"pair", "stake_yen", "observed_odds"}:
            raise VirtualLedgerRejected("ticket_schema_invalid")
        pair = _pair(t["pair"])
        if pair in seen:
            raise VirtualLedgerRejected("duplicate_pair")
        seen.add(pair)
        _money(t["stake_yen"], "stake")
        if type(t["observed_odds"]) not in (float, int) or not (1.0 < t["observed_odds"] <= 10000):
            raise VirtualLedgerRejected("odds_invalid")
        spent += t["stake_yen"]
    if spent > p["daily_budget_yen"]:
        raise VirtualLedgerRejected("budget_exceeded")
    return spent

def validate_final(p, freeze):
    if not isinstance(p, dict) or set(p) != {
        "race_id", "result_version", "result_captured_utc",
        "result_sha256", "result_scope", "payouts", "refund_pairs"
    }:
        raise VirtualLedgerRejected("result_schema_invalid")
    if p["race_id"] != freeze["race_id"]:
        raise VirtualLedgerRejected("result_wrong_race")
    if p["result_scope"] != "UNAUTHENTICATED_LAB_FINAL":
        raise VirtualLedgerRejected("official_result_verification_not_supported")
    if type(p["result_version"]) is not int or p["result_version"] < 1:
        raise VirtualLedgerRejected("result_version_invalid")
    if utc(p["result_captured_utc"]) <= utc(freeze["race_start_utc"]):
        raise VirtualLedgerRejected("result_before_race")
    _hash(p["result_sha256"], "result_sha256")
    if type(p["payouts"]) is not list or type(p["refund_pairs"]) is not list:
        raise VirtualLedgerRejected("result_pairs_invalid")
    seen = set()
    for i in p["payouts"]:
        if not isinstance(i, dict) or set(i) != {"pair", "yen_per_100"}:
            raise VirtualLedgerRejected("payout_schema_invalid")
        pair = _pair(i["pair"])
        if pair in seen:
            raise VirtualLedgerRejected("duplicate_payout_pair")
        seen.add(pair)
        _money(i["yen_per_100"], "payout_per_100")
    refunds = [_pair(x) for x in p["refund_pairs"]]
    if len(refunds) != len(set(refunds)) or set(refunds) & seen:
        raise VirtualLedgerRejected("refund_conflicts_with_payout")
    return True

def _connect(path):
    path = Path(path)
    if path.is_symlink():
        raise VirtualLedgerRejected("symlink_database_forbidden")
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=10000")
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=FULL")
    return c

def initialize(path):
    with _connect(path) as c:
        c.executescript("""
          CREATE TABLE IF NOT EXISTS events(
            event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_key TEXT UNIQUE NOT NULL,
            race_id TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK(event_type IN ('FREEZE','FINAL')),
            payload TEXT NOT NULL,
            prev_sha256 TEXT NOT NULL,
            entry_sha256 TEXT NOT NULL UNIQUE
          );
          CREATE TRIGGER IF NOT EXISTS no_modify_events BEFORE UPDATE ON events
            BEGIN SELECT RAISE(ABORT,'immutable_event'); END;
          CREATE TRIGGER IF NOT EXISTS no_delete_events BEFORE DELETE ON events
            BEGIN SELECT RAISE(ABORT,'immutable_event'); END;
        """)
        return True

def _load(c):
    events = []
    prev = ZERO
    for seq,key,race,kind,raw,previous,digest in c.execute(
            "SELECT event_seq,event_key,race_id,event_type,payload,prev_sha256,entry_sha256 FROM events ORDER BY event_seq"):
        try:
            p = json.loads(raw)
        except (ValueError, TypeError) as e:
            raise VirtualLedgerRejected("invalid_stored_json") from e
        body = {"event_key":key,"race_id":race,"type":kind,"payload":p,"prev_sha256":previous}
        if previous != prev or digest != sha(body) or raw != canonical(p):
            raise VirtualLedgerRejected("hash_chain_tampered")
        events.append(body | {"entry_sha256":digest,"sequence":seq})
        prev = digest
    frozen, final_versions = {}, {}
    for e in events:
        race, p = e["race_id"], e["payload"]
        if e["type"] == "FREEZE":
            if race in frozen or e["event_key"] != "freeze:"+race:
                raise VirtualLedgerRejected("duplicate_or_wrong_freeze")
            validate_freeze(p)
            frozen[race] = p
        else:
            if race not in frozen or e["event_key"] != "final:"+race+":"+str(p.get("result_version")):
                raise VirtualLedgerRejected("unbound_final")
            validate_final(p, frozen[race])
            version_key=(race,p["result_version"])
            if version_key in final_versions or p["result_version"] != 1 + max(
                    [v for r,v in final_versions if r==race], default=0):
                raise VirtualLedgerRejected("nonsequential_final")
            final_versions[version_key] = p
    return events, frozen, final_versions

def _append(path,key,race,kind,p):
    initialize(path)
    c=_connect(path)
    try:
        c.execute("BEGIN IMMEDIATE")
        events, frozen, finals = _load(c)
        existing=next((x for x in events if x["event_key"]==key),None)
        if existing:
            if existing["payload"] != p or existing["type"] != kind:
                raise VirtualLedgerRejected("idempotent_event_conflict")
            c.execute("COMMIT")
            return {"status":"ALREADY_PRESENT","entry_sha256":existing["entry_sha256"]}
        if kind=="FREEZE":
            validate_freeze(p)
            if race in frozen:
                raise VirtualLedgerRejected("race_frozen_twice")
        else:
            if race not in frozen:
                raise VirtualLedgerRejected("result_before_freeze")
            validate_final(p, frozen[race])
            expected=1+max([v for r,v in finals if r==race],default=0)
            if p["result_version"]!=expected:
                raise VirtualLedgerRejected("result_version_out_of_order")
        prev=events[-1]["entry_sha256"] if events else ZERO
        body={"event_key":key,"race_id":race,"type":kind,"payload":p,"prev_sha256":prev}
        digest=sha(body)
        raw=canonical(p)
        if len(raw.encode("utf-8")) > MAX_EVENT_BYTES:
            raise VirtualLedgerRejected("event_storage_limit")
        c.execute("INSERT INTO events(event_key,race_id,event_type,payload,prev_sha256,entry_sha256) VALUES(?,?,?,?,?,?)",
                  (key,race,kind,raw,prev,digest))
        _load(c)
        c.execute("COMMIT")
        return {"status":"APPENDED","entry_sha256":digest}
    except Exception:
        c.execute("ROLLBACK")
        raise
    finally:
        c.close()

def freeze_virtual(path, record):
    validate_freeze(record)
    return _append(path,"freeze:"+record["race_id"],record["race_id"],"FREEZE",record)

def record_lab_final(path, record):
    if not isinstance(record,dict) or "race_id" not in record or "result_version" not in record:
        raise VirtualLedgerRejected("final_identity_required")
    return _append(path,"final:"+str(record["race_id"])+":"+str(record["result_version"]),
                   record["race_id"],"FINAL",record)

def dashboard(path):
    """All final versions REPLACE prior settlement, never stack double P&L."""
    initialize(path)
    c=_connect(path)
    try:
        events,frozen,finals=_load(c)
    finally:
        c.close()
    spent,returned,settled,unsettled,hit_tickets=0,0,0,0,0
    race_rows=[]
    for race,plan in sorted(frozen.items()):
        cost=sum(t["stake_yen"] for t in plan["tickets"])
        versions=[v for (r,v) in finals if r==race]
        if not versions:
            unsettled+=1
            race_rows.append({"race_id":race,"status":"UNSETTLED","stake_yen":cost,
                              "return_yen":None,"profit_yen":None})
            continue
        event=finals[(race,max(versions))]
        pays={tuple(x["pair"]):x["yen_per_100"] for x in event["payouts"]}
        refunds=set(map(tuple,event["refund_pairs"]))
        revenue=sum(t["stake_yen"]//100*pays.get(tuple(t["pair"]),0) +
                    (t["stake_yen"] if tuple(t["pair"]) in refunds else 0)
                    for t in plan["tickets"])
        hit_tickets+=sum(tuple(t["pair"]) in pays for t in plan["tickets"])
        spent+=cost
        returned+=revenue
        settled+=1
        race_rows.append({"race_id":race,"status":"LAB_SETTLED_UNAUTHENTICATED",
                          "stake_yen":cost,"return_yen":revenue,
                          "profit_yen":revenue-cost,"final_version":max(versions)})
    return {"scope":"LAB_VIRTUAL_NO_JRA_AUTHENTICATION_OR_REAL_BETS",
            "frozen_races":len(frozen),"settled_races":settled,
            "unsettled_races":unsettled,"settled_stake_yen":spent,
            "settled_return_yen":returned,
            "settled_profit_yen":returned-spent,
            "settled_roi_percent":round(100*returned/spent,3) if spent else None,
            "hit_ticket_count":hit_tickets,"event_count":len(events),
            "chain_head":events[-1]["entry_sha256"] if events else ZERO,
            "races":race_rows}
