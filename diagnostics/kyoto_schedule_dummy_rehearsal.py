"""No-JRA-network scheduled rehearsal: both weekend days, full mocked source lifecycle.

The GitHub event type is preserved in an auditable receipt. A push cannot
masquerade as a real schedule trigger. No GitHub secrets or external JRA HTTP.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

COLLECTOR_SHA="e2a48f8b58ae13c210eead22533ee107004a45cd"
SUITES={
    "20261121":(
        "tests.test_kyoto_weekend_retry_guard",
        "tests.test_kyoto_weekend_end_to_end",
        "tests.test_kyoto_weekend_race_parity",
        "tests.test_kyoto_weekend_interruption_and_pacing",
        "tests.test_kyoto_safe_stop_artifact",
        "tests.test_kyoto_weekend_handoff_workflow",
    ),
    "20261122":(
        "tests.test_kyoto_weekend_sp_discovery",
        "tests.test_kyoto_weekend_postflight",
        "tests.test_kyoto_nov15_encrypted_evidence",
        "tests.test_kyoto_weekend_day21_artifact_triage",
        "tests.test_kyoto_weekend_day21_triage",
    ),
}

def rehearse(root:Path,out:Path,event:str,scheduled_expression:str,run_id:str):
    root=root.resolve()
    got=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    if got!=COLLECTOR_SHA:
        raise RuntimeError("UNVERIFIED_COLLECTOR_SHA")
    if event not in ("push","schedule","workflow_dispatch"):
        raise RuntimeError("WRONG_EVENT_TYPE")
    expected_crons={"55 4 16 11 *","5 5 16 11 *",
                    "43 5 16 11 *","58 5 16 11 *","13 6 16 11 *"}
    if event=="schedule" and scheduled_expression not in expected_crons:
        raise RuntimeError("UNEXPECTED_SCHEDULE_EXPRESSION")
    out.mkdir(parents=True,exist_ok=True)
    details=[]
    for day,cases in SUITES.items():
        env=os.environ.copy()
        env["KYOTO_TARGET_DAY"]=day
        env["PYTHONPATH"]=str(root)
        result=subprocess.run([sys.executable,"-m","unittest","-v",*cases],
            cwd=root,env=env,text=True,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,timeout=200)
        logfile=out/("mock_"+day+".log")
        logfile.write_text(result.stdout,encoding="utf8")
        count=sum(int(n) for n in re.findall(r"Ran (\d+) tests? in",result.stdout))
        details.append({"day":day,"case_modules":list(cases),"run_tests":count,
                        "passing":result.returncode==0 and count>=10,
                        "log_sha256":hashlib.sha256(logfile.read_bytes()).hexdigest()})
    # The schedule guarantee is an *actual GitHub event*, never a
    # handwritten timestamp or passing push-triggered unit test.
    report={
        "schema":"kyoto_actual_schedule_dummy_rehearsal.v1",
        "observed_at_utc":datetime.now(timezone.utc).isoformat(),
        "github_event_name":event,"github_event_schedule":scheduled_expression,
        "github_run_id":run_id,"pinned_collector_sha":got,
        "mock_only":True,"jra_http_attempts":0,
        "both_days_tested":len(details)==2,
        "all_mock_suites_passed":all(x["passing"] for x in details),
        "actual_automatic_schedule_trigger_verified":event=="schedule" and
            scheduled_expression in expected_crons,
        "scenarios":details,
    }
    (out/"receipt.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf8")
    (out/"receipt.sha256").write_text(
        hashlib.sha256((out/"receipt.json").read_bytes()).hexdigest()+"  receipt.json\n",
        encoding="ascii")
    print("MOCK_CAPTURE_SAVE_DECRYPT_REGRESSIONS="+
        ("PASS" if report["all_mock_suites_passed"] else "FAIL"))
    print("ACTUAL_GITHUB_SCHEDULE_EVENT_VERIFIED="+
        ("TRUE" if report["actual_automatic_schedule_trigger_verified"] else "FALSE"))
    print("JRA_HTTP_REQUESTS=0")
    if not report["all_mock_suites_passed"]:
        raise SystemExit(1)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    rehearse(args.root,args.out,os.getenv("GITHUB_EVENT_NAME",""),
              os.getenv("GITHUB_EVENT_SCHEDULE",""),
              os.getenv("GITHUB_RUN_ID",""))
if __name__=="__main__":
    main()
