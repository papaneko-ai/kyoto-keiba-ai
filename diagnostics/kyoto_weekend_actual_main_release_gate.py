"""Read-only verification of the *actual* main weekend schedule and pinned sources.

This gate deliberately never promotes the experiment to production.
"""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
WORKFLOW=".github/workflows/kyoto-20261121-22-two-source-production-observer.yml"
HANDOFF=".github/workflows/kyoto-20261121-22-result-handoff.yml"
G06="diagnostics/kyoto_g06_all12_capture.py"
PIN="c96df31542cb94435ca36cb4a1b8bd6de938233f"
MARKET="diagnostics/kyoto_g06_item_level_recovery.py"

def git_head(path):
    return subprocess.check_output(["git","-C",str(path),"rev-parse","HEAD"],text=True).strip()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def audit(main,collector,experiment):
    main,collector,experiment=map(Path,(main,collector,experiment))
    prod=main/WORKFLOW
    hand=main/HANDOFF
    if not prod.is_file() or not hand.is_file():
        raise ValueError("production_workflow_missing")
    wf=prod.read_text(encoding="utf8")
    hf=hand.read_text(encoding="utf8")
    assert_main=git_head(main)
    assert_collector=git_head(collector)
    assert_exp=git_head(experiment)
    checks={
        "production_main_checked_out":len(assert_main)==40,
        "source_pin_exact":assert_collector==PIN,
        "source_pin_in_workflow":PIN in wf,
        "scheduled_both_days":all(("21 11 *" in wf,"22 11 *" in wf)),
        "first_capture_0915_both_days":all(x in wf for x in ("15 0 21 11 *","15 0 22 11 *")),
        "four_windows_each_day":all(sum(day+" 11 *" in l for l in wf.splitlines() if "cron:" in l)==4 for day in ("21","22")),
        "two_independent_lanes":all(x in wf for x in ("pc-originals-independent:","sp-originals-independent:")),
        "production_encryption":all(x in wf for x in ("KYOTO_JRA_ARCHIVE_AES256_HEX","--seal-only","upload-artifact@v4")),
        "release_has_pre_http_tests":"Offline regression mandatory before any live HTTP" in wf,
        "handoff_on_completed_runs":all(x in hf for x in ("workflow_run:","types: [completed]","diagnostics.kyoto_weekend_day21_triage")),
        "main_workflow_differs_from_experiment":(main/WORKFLOW).read_bytes()!=(experiment/WORKFLOW).read_bytes(),
        "experimental_g06_exists":(experiment/G06).is_file(),
        "experimental_item_recovery_exists":(experiment/MARKET).is_file(),
        "production_collector_not_experimental_g06":not (collector/G06).is_file() or sha(collector/G06)!=sha(experiment/G06),
    }
    # A success here proves source/preflight wiring, NOT real race acquisition.
    result={
        "schema":"kyoto_weekend_release_readiness_audit.v1",
        "production_main_sha":assert_main,
        "pinned_collector_sha":assert_collector,
        "experiment_sha":assert_exp,
        "production_workflow_sha256":sha(prod),
        "production_handoff_sha256":sha(hand),
        "checks":checks,
        "pass_read_only_preflight":all(checks.values()),
        "production_g06_market_recovery_integrated":False,
        "full_12r_live_quinella_bracket_proven":False,
        "live_trigger_proven":False,
        "secrets_presence_proven":False,
        "variable_NOV22_sha_proven":False,
        "promotion_authorized":False,
        "next_required_gate":"review live execution prerequisites and approve isolated production patch only after tests",
    }
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",required=True)
    p.add_argument("--collector",required=True)
    p.add_argument("--experiment",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=audit(a.main,a.collector,a.experiment)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))
    if not report["pass_read_only_preflight"]:
        raise SystemExit(1)
if __name__=="__main__":main()
