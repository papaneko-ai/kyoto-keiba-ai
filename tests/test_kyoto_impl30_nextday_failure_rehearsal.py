"""Failure replay from Nov21, with real artifact handoff in the separate CI job."""
import json,os,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_impl30_nextday_adaptation import derive,make,accept,recover,budgets,NAME,WORKFLOW,SOURCE_DAY,TARGET_DAY
from diagnostics.kyoto_weekend_day21_triage import classify
from tests.test_kyoto_impl30_nextday_adaptation import saturday
REPO="papaneko-ai/kyoto-keiba-ai"
KEY="ab"*32 # public dummy key; never a production secret
OLD_RUNS=(44854931835,44857934629,44861934823)

def failed_report(rid=44854931835,stage="OFFLINE_REGRESSION"):
    return {"day":SOURCE_DAY,"next_day":TARGET_DAY,"all_run_metadata_screened":False,
            "github_run_listing_complete":False,"scheduled_runs":[{"run":{"id":rid,"event":"schedule",
            "created_at":"2026-11-28T01:00:00Z","status":"completed"},"state":"ALL_LANES_CLASSIFIED",
            "lanes":{"PC":{"job_conclusion":"failure","job_state":"FAILED_WITH_ARTIFACT",
            "failure_stage":stage,"artifact_evidence_state":"PRE_HTTP_SAFE_STOP_NO_SOURCE"}}}],
            "day_source_coverage":{"authenticated_pc_slots":0}}

class Failures(unittest.TestCase):
    def test_known_prior_failure_without_originals_selects_recovery(self):
        r=failed_report()
        d=derive(r)
        self.assertEqual(d["mode"],"MARKET_OR_ROSTER_RECOVERY")
        self.assertFalse(d["source_coverage_proved"])
        self.assertEqual(budgets(d["mode"]),(720,360))
        self.assertEqual(derive(r),d)
    def test_unclassified_or_wrong_day_cannot_trigger_recovery(self):
        for field,value in [("event","workflow_dispatch"),("created_at","2026-11-22T00:00:00Z"),("status","in_progress")]:
            r=failed_report();r["scheduled_runs"][0]["run"][field]=value
            self.assertEqual(derive(r)["mode"],"BASELINE")
        r=failed_report();r["scheduled_runs"][0]["state"]="RUN_METADATA_UNAVAILABLE"
        self.assertEqual(derive(r)["mode"],"BASELINE")
    def test_no_failure_evidence_and_missing_report_is_baseline(self):
        r=failed_report();r["scheduled_runs"]=[]
        self.assertEqual(derive(r)["mode"],"BASELINE")
    def test_authenticated_failure_cannot_be_changed_to_profile_mode(self):
        r=failed_report();sha="a"*40
        doc=make(r,repo=REPO,run_id=100,collector_sha=sha,key=KEY)
        self.assertEqual(accept(doc,r,repo=REPO,run_id=100,collector_sha=sha,key=KEY),"MARKET_OR_ROSTER_RECOVERY")
        doc["body"]["decision"]["mode"]="PROFILE_RECOVERY"
        with self.assertRaises(ValueError):accept(doc,r,repo=REPO,run_id=100,collector_sha=sha,key=KEY)

def prepare():
    """Retrieve actual Nov21 failure metadata; create explicitly hypothetical Nov28 replay."""
    def api(endpoint):
        return json.loads(subprocess.check_output(["gh","api",endpoint],text=True,timeout=20))
    fixtures=[];facts=[]
    for rid in OLD_RUNS:
        base=f"repos/{REPO}/actions/runs/{rid}"
        run=api(base);jobs=api(base+"/jobs?per_page=100");arts=api(base+"/artifacts?per_page=100")
        assert jobs["total_count"]==len(jobs["jobs"]) and arts["total_count"]==len(arts["artifacts"])
        triage=classify("20261121",run,jobs["jobs"],arts["artifacts"])
        pc=triage["lanes"]["PC"]
        assert pc["job_conclusion"]=="failure" and pc["stage"]=="OFFLINE_REGRESSION",pc
        facts.append({"historical_run_id":rid,"actual_day":"20261121","failed_stage":pc["stage"],"failed_steps":pc["failed_steps"]})
        entry=failed_report(rid,pc["stage"])["scheduled_runs"][0]
        entry["lanes"]["PC"]["job_state"]=pc["state"]
        fixtures.append(entry)
    report=failed_report()
    report["scheduled_runs"]=fixtures
    report["rehearsal_only"]={"actual_source_day":"20261121","simulated_source_day":SOURCE_DAY,"historical_facts":facts}
    sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    rid=os.environ["GITHUB_RUN_ID"]
    doc=make(report,repo=REPO,run_id=rid,collector_sha=sha,key=KEY)
    assert doc["body"]["decision"]["mode"]=="MARKET_OR_ROSTER_RECOVERY"
    root=Path("rehearsal_handoff");root.mkdir()
    (root/"report.json").write_text(json.dumps(report,ensure_ascii=False),encoding="utf8")
    (root/"nextday_policy.json").write_text(json.dumps(doc),encoding="utf8")
    print("HISTORICAL_FAILURES_REPLAYED=3; POLICY=MARKET_OR_ROSTER_RECOVERY; NO_JRA_HTTP")

def consume():
    """Actual GitHub artifact index + download across distinct jobs.
    Only the future schedule identity is simulated; no JRA requests.
    """
    from diagnostics.kyoto_weekend_capture import capture
    rid=int(os.environ["GITHUB_RUN_ID"])
    sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    real_api=subprocess.check_output
    real_run=subprocess.run
    transfers=[]
    def api(args,**kwargs):
        if "/actions/workflows/" in args[-1]:
            # November 28 is still future; test the exact scheduled-run selector
            # with synthetic future metadata, not a claim of a real schedule run.
            return json.dumps({"total_count":1,"workflow_runs":[{"id":rid,"name":NAME,
                "created_at":"2026-11-28T12:00:00Z","event":"schedule","status":"completed",
                "conclusion":"success","head_repository":{"full_name":REPO},"path":".github/workflows/"+WORKFLOW}]})
        return real_api(args,**kwargs)
    def download(args,**kwargs):
        result=real_run(args,**kwargs)
        transfers.append(args[3])
        return result
    def discover(root,**kwargs):
        root.mkdir();(root/"sp_discovery_receipt.json").write_text("{}")
        return {"network_requests_started":0,"racecard_url":"fixture"}
    with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{
        "KYOTO_TARGET_DAY":TARGET_DAY,"KYOTO_WEEKEND_HTTP_APPROVED":"YES",
        "GITHUB_EVENT_NAME":"schedule","ARCHIVE_KEY":KEY,"GITHUB_REPOSITORY":REPO,"COLLECTOR_SHA":sha
    }),patch("diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output",side_effect=api),patch(
        "diagnostics.kyoto_impl30_nextday_adaptation.subprocess.run",side_effect=download),patch(
        "diagnostics.kyoto_weekend_capture.validate_day"),patch(
        "diagnostics.kyoto_weekend_sp_discovery.discover",side_effect=discover),patch(
        "diagnostics.kyoto_sp_all12_observed_capture.capture_all",return_value={"races":{}}) as actual:
        import time
        before=time.monotonic()
        result=capture(TARGET_DAY,"SP",str(Path(tmp)/"sp"),live=True,opener=object())
        remaining=actual.call_args.kwargs["deadline_monotonic"]-time.monotonic()
        assert 355<=remaining<=360,(remaining,actual.call_args)
        assert transfers==[str(rid)],transfers
        assert result["observed_http_requests_started"]==0
        assert not result["prediction_ready"]
    out=Path("rehearsal_result");out.mkdir()
    report={"schema":"kyoto_nextday_rehearsal.v1","collector_sha":sha,"actual_artifact_downloads":len(transfers),
            "actual_historical_failure_runs":list(OLD_RUNS),"simulated_schedule":True,
            "sp_runtime_deadline_seconds":360,"baseline_seconds":240,"new_jra_http":0,
            "automatic_code_repair_proven":False}
    (out/"report.json").write_text(json.dumps(report,sort_keys=True,indent=2))
    print("REAL_GITHUB_ARTIFACT_TRANSFER=1; SUNDAY_RUNTIME_SP_DEADLINE=360; NO_JRA_HTTP")
if __name__=="__main__":
    import sys
    if sys.argv[1:]==["prepare"]:prepare()
    elif sys.argv[1:]==["consume"]:consume()
    else:unittest.main()
