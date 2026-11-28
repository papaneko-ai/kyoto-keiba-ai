import copy,unittest
from diagnostics.kyoto_cushion_trigger_evidence import capture,verify,REPO,PATH,PREFIX
def fixture(event="schedule",at="2026-11-29T01:17:00Z"):
    parent={"id":12,"head_sha":"a"*40,"created_at":at,"event":event,"head_repository":{"full_name":REPO},"head_branch":"main","status":"completed","path":PREFIX+"two-source-production-observer.yml"}
    env={"GITHUB_RUN_ID":"42","GITHUB_SHA":"b"*40,"GITHUB_EVENT_NAME":"workflow_run","GITHUB_REPOSITORY":REPO,"GITHUB_REF":"refs/heads/main"}
    run={"id":42,"head_sha":"b"*40,"event":"workflow_run","head_branch":"main","head_repository":{"full_name":REPO},"path":PATH,"created_at":"2026-11-29T04:00:00Z"}
    jobs={"total_count":2,"jobs":[{"id":1,"run_id":42,"name":"trigger-evidence","status":"completed","conclusion":"success"},{"id":2,"run_id":42,"name":"cushion-source-only","status":"completed","conclusion":"skipped"}]}
    return capture({"workflow_run":parent},env),run,jobs,parent
class CushionTrigger(unittest.TestCase):
    def test_native_and_unapproved_hour_distinct(self):
        for event,at,reason in (("schedule","2026-11-29T01:17:00Z","PARENT_EVENT_NOT_AUTHORIZED_DISPATCH"),("workflow_dispatch","2026-11-29T02:57:00Z","PARENT_HOUR_NOT_APPROVED")):
            d,r,j,p=fixture(event,at)
            v=verify(d,r,j,lambda i:p)
            self.assertEqual(v["state"],"DIRECT_SKIP_CONDITION_VERIFIED")
            self.assertEqual(v["gate_reasons"],[reason]);self.assertFalse(v["source_success_certified"]);self.assertFalse(v["upstream_scheduler_root_cause_proved"])
    def test_eligible_skip_not_explained(self):
        d,r,j,p=fixture("workflow_dispatch")
        self.assertEqual(verify(d,r,j,lambda i:p)["state"],"ELIGIBLE_BUT_PRODUCER_SKIPPED")
    def test_reject_tampered_parent_run_and_gate(self):
        d,r,j,p=fixture()
        for x,y,z,parent in (({**d,"head_sha":"c"*40},r,j,p),(d,r,j,{**p,"id":13}),(d,r,j,{**p,"event":"workflow_dispatch"}),({**d,"gate_reasons":[]},r,j,p),(d,r,{**j,"total_count":3},p)):
            with self.assertRaises(ValueError):verify(x,y,z,lambda i:parent)
    def test_no_secret_or_raw_confirmation_in_receipt(self):
        d,r,j,p=fixture()
        self.assertNotIn("SECRET",str(d))
        env={"GITHUB_RUN_ID":"42","GITHUB_SHA":"b"*40,"GITHUB_EVENT_NAME":"workflow_dispatch","GITHUB_REPOSITORY":REPO,"GITHUB_REF":"refs/heads/main"}
        d=capture({"inputs":{"confirmation":"SECRET","race_day":"20261129"}},env)
        self.assertNotIn("SECRET",str(d));self.assertEqual(d["gate_reasons"],["MANUAL_CONFIRMATION_MISMATCH"])
