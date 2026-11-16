"""Day21/day22 handoff classifies missing, failed and retained source separately."""
import unittest
from diagnostics.kyoto_weekend_day21_triage import classify

DAY="20261121"
RUN={"event":"schedule","created_at":"2026-11-21T02:05:01Z","id":111,"conclusion":"failure"}
def job(name, conclusion, failed_step=None):
    return {"name":name,"conclusion":conclusion,"steps":[{"name":failed_step,"conclusion":"failure"}] if failed_step else []}

class TriageTests(unittest.TestCase):
    def test_pc_pre_http_failure_but_sp_artifact_present(self):
        result=classify(DAY,RUN,[job("pc-originals-independent","failure",
            "Race date, immutable commit, secret, first attempt and non-replay guard"),
            job("sp-originals-independent","success")],
            [{"name":"kyoto-sp-111-20261121","expired":False}])
        self.assertEqual(result["lanes"]["PC"]["stage"],"PRE_HTTP_GUARD")
        self.assertEqual(result["lanes"]["SP"]["state"],"ARTIFACT_RETAINED_CONTENT_UNVERIFIED")
        self.assertFalse(result["candidate_promotion_permitted_without_independent_tests"])
    def test_both_success_jobs_do_not_prove_jra_success(self):
        result=classify(DAY,{**RUN,"conclusion":"success"},
            [job("pc-originals-independent","success"),
             job("sp-originals-independent","success")],
            [{"name":"kyoto-pc-111-20261121"},{"name":"kyoto-sp-111-20261121"}])
        self.assertFalse(result["ready_for_prerace_predictions"])
        self.assertTrue(result["requires_actual_original_decrypt_and_hash_check"])
    def test_fails_closed_if_day_mismatch(self):
        with self.assertRaisesRegex(ValueError,"wrong_day_run"):
            classify("20261122",RUN,[],[])
    def test_missing_job_never_passes(self):
        result=classify(DAY,RUN,[],[])
        self.assertEqual(result["lanes"]["PC"]["state"],"JOB_MISSING_OR_DUPLICATE")
    def test_missing_artifacts_never_pass(self):
        result=classify(DAY,RUN,[job("pc-originals-independent","success"),
            job("sp-originals-independent","success")],[])
        self.assertEqual(result["lanes"]["PC"]["state"],"NO_ARTIFACT")
    def test_encryption_fail_is_separate_from_capture_failure(self):
        result=classify(DAY,RUN,[job("pc-originals-independent","failure",
            "Always encrypt any source originals or save factual pre-HTTP stop"),
            job("sp-originals-independent","failure",
            "Always encrypt SP originals or save factual pre-HTTP stop")],[])
        self.assertEqual(result["lanes"]["PC"]["stage"],"ENCRYPTION_OR_STOP")
        self.assertEqual(result["lanes"]["SP"]["stage"],"ENCRYPTION_OR_STOP")

if __name__=="__main__":
    unittest.main()
