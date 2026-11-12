"""Offline-only append ledger: ENTRIES -> NUMBERED -> MARKET -> LAB_FREEZE.
This is a synthetic LAB instrument, NOT live JRA proof, licensing or deployment.
"""
from __future__ import annotations
import hashlib, json, re, sqlite3
from datetime import datetime

STAGES=("ENTRIES","NUMBERED","MARKET","LAB_FREEZE")
class StageError(ValueError): pass

def _utc(s):
    if type(s) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",s):
        raise StageError("INVALID_UTC")
    try: return datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError: raise StageError("INVALID_UTC") from None

def _canonical(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

class StageLedger:
    def __init__(self,path):
        self.conn=sqlite3.connect(str(path),timeout=5,isolation_level=None)
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("CREATE TABLE IF NOT EXISTS stages (race_id TEXT NOT NULL,stage TEXT NOT NULL,captured_utc TEXT NOT NULL,source_sha256 TEXT NOT NULL,record TEXT NOT NULL,record_sha256 TEXT NOT NULL,PRIMARY KEY(race_id,stage))")
        self.conn.execute("CREATE TRIGGER IF NOT EXISTS stages_no_update BEFORE UPDATE ON stages BEGIN SELECT RAISE(ABORT,'immutable_stage'); END")
        self.conn.execute("CREATE TRIGGER IF NOT EXISTS stages_no_delete BEFORE DELETE ON stages BEGIN SELECT RAISE(ABORT,'immutable_stage'); END")
    def close(self): self.conn.close()
    def read(self,race_id):
        rows=self.conn.execute("SELECT stage,captured_utc,source_sha256,record,record_sha256 FROM stages WHERE race_id=?",(race_id,)).fetchall()
        keys=("stage","captured_utc","source_sha256","record","record_sha256")
        return sorted((dict(zip(keys,r)) for r in rows),key=lambda r:STAGES.index(r["stage"]))
    def append(self,*,race_id,stage,captured_utc,start_utc,raw,payload):
        if type(race_id) is not str or not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{5,60}",race_id): raise StageError("BAD_RACE")
        if stage not in STAGES or type(payload) is not dict: raise StageError("BAD_STAGE")
        t,start=_utc(captured_utc),_utc(start_utc)
        if t>=start: raise StageError("POST_START")
        if type(raw) is not bytes or not 0<len(raw)<=5000000: raise StageError("RAW_REQUIRED")
        source_sha=hashlib.sha256(raw).hexdigest()
        if payload.get("race_id")!=race_id or payload.get("race_start_utc")!=start_utc: raise StageError("IDENTITY_MISMATCH")
        if payload.get("scope")!="SYNTHETIC_LAB_ONLY": raise StageError("REAL_SOURCE_NOT_APPROVED")
        if stage=="LAB_FREEZE":
            if payload.get("real_purchase") is not False or payload.get("source_verified_live") is not False: raise StageError("LAB_ONLY")
            tickets=payload.get("tickets")
            if type(tickets) is not list or not tickets or any(type(x) is not dict or type(x.get("stake_yen")) is not int or x["stake_yen"]<=0 or x["stake_yen"]%100 for x in tickets): raise StageError("BAD_STAKES")
            budget=payload.get("daily_budget_yen")
            if type(budget) is not int or budget<0 or budget%100 or sum(x["stake_yen"] for x in tickets)>budget: raise StageError("BUDGET_EXCEEDED")
        try: rec=_canonical(payload)
        except (TypeError,ValueError): raise StageError("BAD_RECORD") from None
        digest=hashlib.sha256(rec.encode()).hexdigest()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            rows=self.read(race_id)
            prior={x["stage"]:x for x in rows}
            if stage in prior:
                p=prior[stage]
                if (p["captured_utc"],p["source_sha256"],p["record"],p["record_sha256"])!=(captured_utc,source_sha,rec,digest): raise StageError("IMMUTABLE_CONFLICT")
                self.conn.execute("COMMIT")
                return {"status":"ALREADY_PRESENT","record_sha256":digest}
            n=STAGES.index(stage)
            if len(rows)!=n or [x["stage"] for x in rows]!=list(STAGES[:n]): raise StageError("OUT_OF_ORDER")
            if rows and t<_utc(rows[-1]["captured_utc"]): raise StageError("TIME_REVERSED")
            if stage=="LAB_FREEZE" and payload.get("market_record_sha256")!=prior["MARKET"]["record_sha256"]: raise StageError("MARKET_BINDING_MISMATCH")
            self.conn.execute("INSERT INTO stages VALUES(?,?,?,?,?,?)",(race_id,stage,captured_utc,source_sha,rec,digest))
            self.conn.execute("COMMIT")
            return {"status":"APPENDED","record_sha256":digest}
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
