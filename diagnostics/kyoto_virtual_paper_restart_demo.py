"""Two-process and restored-copy demo of durable LAB-only virtual paper trading.

No network, JRA source attestation, Turso or real transactions. The synthetic
fixture deliberately uses a future fixture start, not a past JRA outcome.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from diagnostics.kyoto_virtual_sqlite_journal import dashboard,freeze_virtual,record_lab_final

def write_demo(directory):
    d=Path(directory)
    if d.exists():raise ValueError("demo_directory_must_be_new")
    d.mkdir(parents=True)
    db=d/"virtual_only.sqlite"
    freeze={
        "race_id":"20261114-KYOTO-R01","race_start_utc":"2026-11-14T05:00:00Z",
        "frozen_utc":"2026-11-14T04:20:00Z",
        "source_observed_utc":"2026-11-14T04:15:00Z",
        "source_sha256":"a"*64,"model_sha256":"b"*64,
        "model_version":"synthetic-lab-demonstration-only","ticket_type":"QUINELLA",
        "tickets":[{"pair":[1,2],"stake_yen":100,"observed_odds":6.5},
                   {"pair":[3,4],"stake_yen":200,"observed_odds":14.4}],
        "daily_budget_yen":1000,"provenance_scope":"UNAUTHENTICATED_LAB_INPUT"
    }
    freeze_virtual(db,freeze)
    final={"race_id":freeze["race_id"],"result_version":1,
      "result_captured_utc":"2026-11-14T06:00:00Z",
      "result_sha256":"c"*64,"result_scope":"UNAUTHENTICATED_LAB_FINAL",
      "payouts":[{"pair":[1,2],"yen_per_100":600}],"refund_pairs":[]}
    record_lab_final(db,final)
    corrected={**final,"result_version":2,"result_sha256":"d"*64,
                "payouts":[{"pair":[1,2],"yen_per_100":700}]}
    record_lab_final(db,corrected)
    state=dashboard(db)
    assert state["settled_stake_yen"]==300
    assert state["settled_return_yen"]==700
    assert state["settled_profit_yen"]==400
    assert state["event_count"]==3
    assert state["races"][0]["final_version"]==2
    # The SQLite WAL mode is checkpointed before byte-level integrity checking.
    import sqlite3
    with sqlite3.connect(db) as c:c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    receipt={
        "schema":"kyoto_virtual_sqlite_cross_process_demo.v1",
        "data_scope":"SYNTHETIC_OFFLINE_LAB_ONLY",
        "not_a_live_race":True,
        "not_a_real_purchase":True,
        "not_an_official_result":True,
        "not_a_production_turso_database":True,
        "sqlite_sha256":hashlib.sha256(db.read_bytes()).hexdigest(),
        "chain_head":state["chain_head"],
        "settled_stake_yen":state["settled_stake_yen"],
        "settled_return_yen":state["settled_return_yen"],
        "settled_profit_yen":state["settled_profit_yen"],
        "event_count":state["event_count"],
    }
    (d/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    return receipt

def verify_demo(directory):
    d=Path(directory)
    receipt=json.loads((d/"receipt.json").read_text())
    db=d/"virtual_only.sqlite"
    if receipt.get("schema")!="kyoto_virtual_sqlite_cross_process_demo.v1" or receipt.get("data_scope")!="SYNTHETIC_OFFLINE_LAB_ONLY":
        raise ValueError("invalid_lab_receipt")
    if hashlib.sha256(db.read_bytes()).hexdigest()!=receipt["sqlite_sha256"]:
        raise ValueError("sqlite_raw_bytes_mismatch")
    state=dashboard(db)
    for k in ("chain_head","settled_stake_yen","settled_return_yen","settled_profit_yen","event_count"):
        if state[k]!=receipt[k]:raise ValueError("ledger_replay_mismatch:"+k)
    if state["event_count"]!=3 or state["settled_profit_yen"]!=400:
        raise ValueError("unexpected_lab_replay")
    return state

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("create","verify"))
    p.add_argument("directory",type=Path)
    a=p.parse_args()
    value=write_demo(a.directory) if a.action=="create" else verify_demo(a.directory)
    print(json.dumps(value,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
