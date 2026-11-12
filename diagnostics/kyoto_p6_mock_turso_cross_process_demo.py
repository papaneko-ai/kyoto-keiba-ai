"""Two ACTUAL Python processes using ONE local fake Turso service DB.

This is a mocked remote protocol and persistent SQLite test, not an actual
Turso connection or cross-host network. Kept separate from production code.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from diagnostics.kyoto_turso_isolated_virtual_store import TursoLabStore,EXPECTED_HOST
from tests.test_kyoto_turso_isolated_virtual_store import FakePipeline,TOKEN
from tests.test_kyoto_virtual_sqlite_journal import frozen,final

def instance(path):
    return TursoLabStore(database_url="libsql://"+EXPECTED_HOST,
        token=TOKEN,transport=FakePipeline(path))

def run(action,folder):
    path=Path(folder)
    if action=="create":
        if path.exists():raise ValueError("target_already_exists")
        path.mkdir(parents=True)
        db=path/"synthetic_remote.sqlite"
        a=instance(db)
        a.prepare_isolated_namespace()
        a.append_freeze_lab(frozen())
        a.append_final_lab(final(1,400))
        report=a.read_race_lab(frozen()["race_id"])
        assert len(report["events"])==2
        receipt={
            "schema":"kyoto_p6_mock_remote_two_process_evidence.v1",
            "scope":"LOCAL_SQLITE_FAKE_TURSO_HTTP_ONLY",
            "sqlite_sha256":hashlib.sha256(db.read_bytes()).hexdigest(),
            "event_sha256":[x["sha256"] for x in report["events"]],
            "no_actual_turso_connection":True,
            "no_actual_jra_source":True,
            "no_production_db_or_real_bets":True}
        (path/"receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
        return {"stage":"create","event_count":len(report["events"])}
    if action=="verify":
        db=path/"synthetic_remote.sqlite"
        receipt=json.loads((path/"receipt.json").read_text())
        if receipt.get("schema")!="kyoto_p6_mock_remote_two_process_evidence.v1" or not receipt.get("no_actual_turso_connection"):
            raise ValueError("incorrect_lab_scope")
        if hashlib.sha256(db.read_bytes()).hexdigest()!=receipt["sqlite_sha256"]:
            raise ValueError("remote_db_changed")
        # Independent process, separate HTTP client object and read-only lookup.
        b=instance(db)
        report=b.read_race_lab(frozen()["race_id"])
        if [x["sha256"] for x in report["events"]]!=receipt["event_sha256"]:
            raise ValueError("cross_process_event_sha_mismatch")
        if b.append_freeze_lab(frozen())["status"]!="ALREADY_PRESENT":
            raise ValueError("not_idempotent")
        if b.append_final_lab(final(1,400))["status"]!="ALREADY_PRESENT":
            raise ValueError("final_not_idempotent")
        return {"stage":"independent_process_verify","event_count":len(report["events"]),
                "already_present_events":2,"real_turso_verified":False}
    raise ValueError("unknown_action")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["create","verify"])
    parser.add_argument("folder",type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.action,args.folder),sort_keys=True))
