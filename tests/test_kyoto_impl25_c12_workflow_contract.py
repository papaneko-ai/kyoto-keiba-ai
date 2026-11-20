"""C12 handoff has one schedule; current main 8-slot contract is checked separately."""
import unittest
from pathlib import Path

class C12WorkflowContract(unittest.TestCase):
    def test_handoff_schedule_not_expanded_and_all_run_job_present(self):
        handoff=Path(".github/workflows/kyoto-20261121-22-result-handoff.yml").read_text()
        production=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml").read_text()
        self.assertEqual(handoff.count("- cron:"),1)
        # Immutable collector-native history predates the main 8-slot release.\n        # The released main schedule is checked in the separate release gate.\n        self.assertEqual(production.count("- cron:"),4)
        self.assertIn("all-four-day21-run-aggregation:",handoff)
        self.assertIn("github.event_name == 'schedule'",handoff)
        self.assertIn("diagnostics.kyoto_impl25_c12_all_runs_handoff",handoff)
        self.assertIn("KYOTO_JRA_ARCHIVE_AES256_HEX",handoff)
        self.assertIn("GITHUB_STEP_SUMMARY",handoff)
        self.assertIn("retention-days: 60",handoff)
        self.assertIn("path: day21_all_runs_handoff/",handoff)
        self.assertNotIn("path: day21_ephemeral/",handoff)
        self.assertNotIn("path: pc_raw/",handoff)
        self.assertIn("KYOTO_NOV22_VERIFIED_COLLECTOR_SHA",production)
        self.assertNotIn("all-four-day21-run-aggregation:",production)
    def test_source_only_github_actions_metadata_and_private_local_aes(self):
        src=Path("diagnostics/kyoto_impl25_c12_all_runs_handoff.py").read_text()
        self.assertIn("actions/workflows/",src)
        self.assertIn("for lane in LANES",src)
        self.assertIn("assess_lane(target,day=day",src)
        self.assertIn("TemporaryDirectory",src)
        self.assertIn("automatic_patch_or_secret_edit_authorized\":False",src)
        self.assertIn("full_live_jra_coverage_proved\":False",src)
        self.assertIn("new_live_jra_http_requests_started\":0",src)
        self.assertNotIn("requests.get",src)
        self.assertNotIn("urllib.request",src)
        self.assertNotIn("https://jra.jp",src)
    def test_c11_decrypted_family_counts_are_recomputed_not_taken_at_face_value(self):
        s=Path("diagnostics/kyoto_weekend_day21_artifact_triage.py").read_text()
        self.assertIn("recomputed=reassess_c11(source,day)",s)
        self.assertIn("stored==recomputed",s)
        self.assertIn("RECOMPUTED_SOURCE_SHA_UTC_MATCH",s)
        self.assertIn("SAVED_C11_CANNOT_BE_REVALIDATED",s)

if __name__=="__main__":
    unittest.main()
