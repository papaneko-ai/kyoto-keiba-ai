"""Regression of the time-bounded Kyoto 2026-11-21/22 acquisition closeout."""
import unittest
from datetime import datetime,timezone,timedelta
from diagnostics.kyoto_weekend_experiment_closeout import classify,CUTOFF
T=CUTOFF+timedelta(minutes=10)
def run(day,id,conclusion="success"):
    return {"id":id,"event":"schedule","created_at":f"2026-11-{day}T02:20:00Z",
            "status":"completed","conclusion":conclusion}
def art(day,id,lane):
    return {"id":id*100,"name":f"kyoto-{lane}-{id}-202611{day}",
            "expired":False,"digest":"sha256:012345"}
class Closeout(unittest.TestCase):
    def test_zero_run_closes_on_time(self):
        x=classify([],{},now=T)
        self.assertEqual(x["experiment_status"],"CLOSED")
        self.assertEqual(x["data_outcome"],"NO_RUN")
        self.assertEqual(x["days"]["20261121"]["outcome"],"NOT_EXECUTED")
        self.assertFalse(x["source_accepted"])
    def test_early_not_certified(self):
        with self.assertRaisesRegex(ValueError,"NOT_YET_ENDED"):
            classify([],{},now=CUTOFF-timedelta(seconds=1))
    def test_two_days_fail_closes(self):
        x=classify([run("21",100,"failure"),run("22",101,"failure")],{},now=T)
        self.assertEqual(x["days"]["20261122"]["outcome"],"EXECUTED_WITHOUT_SOURCE_ARTIFACT")
        self.assertEqual(x["data_outcome"],"UNVERIFIED_OR_INCOMPLETE")
    def test_multiple_runs_all_retained(self):
        r=[run("21",100,"failure"),run("21",101),run("22",102)]
        x=classify(r,{"101":[art("21",101,"pc")],"102":[art("22",102,"sp")]},now=T)
        self.assertEqual(x["days"]["20261121"]["run_count"],2)
        self.assertEqual(x["days"]["20261122"]["run_count"],1)
        self.assertTrue(x["days"]["20261121"]["runs"][1]["lanes"]["pc"]["artifact_present"])
        self.assertEqual(x["days"]["20261121"]["outcome"],"ARTIFACT_PRESENT_CONTENT_UNVERIFIED")
        self.assertFalse(x["source_accepted"])
        self.assertFalse(x["prediction_ready"])
    def test_expired_does_not_certify(self):
        a=art("21",100,"pc");a["expired"]=True
        x=classify([run("21",100)],{"100":[a]},now=T)
        self.assertEqual(x["days"]["20261121"]["outcome"],"EXECUTED_WITHOUT_SOURCE_ARTIFACT")
    def test_unrelated_run_excluded(self):
        r=run("21",100);r["event"]="push"
        x=classify([r],{},now=T)
        self.assertEqual(x["data_outcome"],"NO_RUN")
    def test_artifact_not_source_proof(self):
        x=classify([run("21",100)],{"100":[art("21",100,"pc"),art("21",100,"sp")]},now=T)
        self.assertFalse(x["source_accepted"])
        self.assertFalse(x["days"]["20261121"]["runs"][0]["verified_source_claim"])
    def test_no_automatic_retry(self):
        x=classify([],{},now=T)
        self.assertTrue(x["no_new_retries_authorized_by_this_report"])
        self.assertEqual(x["terminal_decision"],"EXPERIMENT_ENDED_PROCESS_NEXT_PHASE_SEPARATELY")
if __name__=="__main__":unittest.main()
