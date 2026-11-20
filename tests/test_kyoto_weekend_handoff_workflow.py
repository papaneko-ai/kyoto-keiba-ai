"""Day21 unattended failure classification is itself scheduled and evidence-backed."""
from pathlib import Path
import unittest

class HandoffWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=Path(".github/workflows/kyoto-20261121-22-result-handoff.yml").read_text(encoding="utf8")
    def test_day21_completion_or_absent_run_both_trigger_handoff(self):
        self.assertIn("workflow_run:",self.src)
        self.assertIn("types: [completed]",self.src)
        self.assertIn("cron: '0 12 21 11 *'",self.src)
        self.assertIn('if [ "$OBSERVED_RUN" = "0" ]; then',self.src)
        self.assertIn('"actual_run_observed":false',self.src)
    def test_actual_metadata_not_synthetic_success(self):
        for fragment in ("run.json","jobs.json","artifacts.json",
                         "diagnostics.kyoto_weekend_day21_triage",
                         "diagnostic.sha256","if: always()"):
            self.assertIn(fragment,self.src)
        self.assertNotIn("authorized-live-http",self.src)
        self.assertNotIn("sp.jra.jp/",self.src)
    def test_actual_encrypted_artifacts_are_privately_decrypted_before_decision(self):
        self.assertIn("gh run download",self.src)
        self.assertIn("KYOTO_JRA_ARCHIVE_AES256_HEX",self.src)
        self.assertIn("kyoto_weekend_day21_artifact_triage",self.src)
        self.assertIn("source_assessment.json",self.src)
        self.assertIn("rm -rf day21_ephemeral",self.src)
        self.assertIn("Manual intervention before Nov22",self.src)
        self.assertIn("SUNDAY_EXPANDED_BOUNDED",Path(
            "diagnostics/kyoto_weekend_day21_triage.py").read_text())
        self.assertIn("path: day_result_handoff/",self.src)
        self.assertNotIn("path: day21_ephemeral/",self.src)

    def test_only_official_workflow_is_accepted(self):
        self.assertIn("WRONG_WORKFLOW_IDENTITY",self.src)
        self.assertIn("SOURCE_RUN_NOT_COMPLETED",self.src)
        self.assertIn("UNEXPECTED_RACE_DAY",self.src)
        self.assertIn("KYOTO_NOV22_VERIFIED_COLLECTOR_SHA",self.src)

if __name__=="__main__":
    unittest.main()
