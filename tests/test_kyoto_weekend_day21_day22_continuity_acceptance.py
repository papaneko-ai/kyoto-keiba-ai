"""Offline Day21-to-Day22 continuity using the actual pinned collector's logic.

No live HTTP. This is a pre-event functional certification fixture, never
a claim that Saturday's official race data has been acquired.
"""
import unittest
from diagnostics.kyoto_weekend_day21_triage import classify
from diagnostics.kyoto_weekend_retry_guard import evaluate, EARLY, PRIMARY, BACKUP

OBS="Kyoto Nov21-22 independent encrypted original collection"
def run(day="20261121",outcome="failure"):
    return {"id":20261121001,"event":"schedule",
            "name":OBS,"created_at":f"{day[:4]}-{day[4:6]}-{day[6:]}T02:05:00Z",
            "conclusion":outcome,"status":"completed"}
def job(lane, *, conclusion="failure", failed_step=None):
    return {"name":lane+"-originals-independent","conclusion":conclusion,
            "steps":[{"name":failed_step,"conclusion":"failure"}] if failed_step else []}
def artifact(lane):
    return {"name":f"kyoto-{lane}-20261121001-20261121","expired":False}
class WeekendContinuityTests(unittest.TestCase):
    def test_first_day_no_artifacts_still_allows_all_sunday_windows(self):
        diagnosis=classify("20261121",run(),
            [job("pc",failed_step="Capture official PC observed originals (bounded no guessed URLs)"),
             job("sp",failed_step="Independently verified SP link, otherwise record zero-request stop")],[])
        self.assertEqual(diagnosis["next_day"],"20261122")
        self.assertFalse(diagnosis["ready_for_prerace_predictions"])
        for cron in (*EARLY["20261122"],PRIMARY["20261122"],BACKUP["20261122"]):
            with self.subTest(cron=cron):
                self.assertIn("ALLOWED",evaluate("20261122",20261122002,"schedule",cron,[],{}))
    def test_first_day_pre_http_failure_does_not_cancel_sunday(self):
        diagnosis=classify("20261121",run(),[
            job("pc",failed_step="Race date, immutable commit, secret, first attempt and non-replay guard"),
            job("sp",failed_step="Independent SP offline regression")],[])
        self.assertTrue(diagnosis["day22_strategy"]["requires_manual_intervention"])
        self.assertEqual(diagnosis["day22_strategy"]["PC"],
                         "FRESH_NEXT_DAY_INDEPENDENT_OFFICIAL_SOURCE_CAPTURE")
        self.assertFalse(diagnosis["automatic_code_patch_approved"])
        self.assertEqual(evaluate("20261122",20261122002,"schedule",PRIMARY["20261122"],[],{}),
                         "PRIMARY_ALLOWED_INDEPENDENT_OF_PRIOR_RUN")
    def test_artifact_success_not_market_proof(self):
        d=classify("20261121",run(outcome="success"),[
            job("pc",conclusion="success"),job("sp",conclusion="success")],
            [artifact("pc"),artifact("sp")])
        self.assertEqual(d["lanes"]["PC"]["state"],"ARTIFACT_RETAINED_CONTENT_UNVERIFIED")
        self.assertEqual(d["lanes"]["SP"]["state"],"ARTIFACT_RETAINED_CONTENT_UNVERIFIED")
        self.assertTrue(d["requires_actual_original_decrypt_and_hash_check"])
        self.assertFalse(d["ready_for_prerace_predictions"])
    def test_pc_success_sp_failure_preserved(self):
        d=classify("20261121",run(),[
            job("pc",conclusion="success"),job("sp",
            failed_step="Independently verified SP link, otherwise record zero-request stop")],
            [artifact("pc")])
        self.assertEqual(d["lanes"]["PC"]["artifact_count"],1)
        self.assertEqual(d["lanes"]["SP"]["stage"],"SP_CAPTURE")
        self.assertEqual(d["next_day"],"20261122")
    def test_wrong_day_metadata_rejected(self):
        with self.assertRaisesRegex(ValueError,"wrong_day"):
            classify("20261121",run(day="20261122"),[],[])
    def test_bad_event_rejected(self):
        r=run();r["event"]="push"
        with self.assertRaisesRegex(ValueError,"unexpected_observation_event"):
            classify("20261121",r,[],[])
    def test_duplicate_jobs_do_not_claim_success(self):
        d=classify("20261121",run(),[
            job("pc",conclusion="success"),job("pc",conclusion="success"),
            job("sp",conclusion="success")],[artifact("pc"),artifact("sp")])
        self.assertEqual(d["lanes"]["PC"]["state"],"JOB_MISSING_OR_DUPLICATE")
        self.assertTrue(d["day22_strategy"]["requires_manual_intervention"])
    def test_day21_existing_attempts_do_not_block_day22(self):
        past=[{"id":20261121001,"conclusion":"success","status":"completed","event":"schedule"}]
        for cron in (*EARLY["20261122"],PRIMARY["20261122"],BACKUP["20261122"]):
            self.assertIn("ALLOWED",evaluate("20261122",20261122002,"schedule",cron,past,{}))
    def test_day21_no_run_is_not_imagined_success(self):
        d=classify("20261121",dict(run(),actual_run_observed=False),
                   [job("pc"),job("sp")],[])
        self.assertFalse(d["observed_workflow_run_exists"])
        self.assertFalse(d["ready_for_prerace_predictions"])
    def test_no_automatic_unreviewed_source_promotion(self):
        d=classify("20261121",run(),[job("pc"),job("sp")],[])
        self.assertFalse(d["candidate_promotion_permitted_without_independent_tests"])
        self.assertFalse(d["automatic_code_patch_approved"])
        self.assertTrue(d["day22_strategy"]["configured_before_day21"])
if __name__=="__main__":
    unittest.main()
