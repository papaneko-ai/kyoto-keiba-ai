"""Main-branch source-only release gate: exact repair SHA, open prediction gates."""
import json
import unittest
from pathlib import Path

WF=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")
REG=Path("docs/diagnostics/KYOTO_20261116_INDEPENDENT_RELEASE_BLOCKERS.json")
PIN="fca19b05450d52427b6e9507e94041ceee6abd14"

class SourceOnlyReleaseAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow=WF.read_text(encoding="utf8")
        cls.ledger=json.loads(REG.read_text(encoding="utf8"))
        cls.issues={x["id"]:x for x in cls.ledger["issues"]}

    def test_both_dated_jobs_use_fixed_sha_and_fault_injection(self):
        self.assertEqual(self.workflow.count("ref: ${{ env.COLLECTOR_SHA }}"),2)
        self.assertIn(PIN,self.workflow)
        self.assertEqual(self.workflow.count("tests.test_kyoto_weekend_interruption_and_pacing"),2)
        self.assertEqual(self.workflow.count("GITHUB_RUN_ATTEMPT"),2)
        self.assertEqual(self.workflow.count("ENCRYPTION_KEY_REQUIRED_NO_HTTP"),2)

    def test_both_lanes_run_actual_foreseeable_failure_cases_before_jra(self):
        self.assertEqual(self.workflow.count("diagnostics.kyoto_predictable_failure_gate"),2)
        self.assertEqual(self.workflow.count("tests.test_kyoto_predictable_failure_gate"),2)
        self.assertEqual(self.workflow.count("PREDICTABLE_FAILURE_PREFLIGHT_30_OF_30_EXECUTED"),2)
        self.assertLess(self.workflow.index("PREDICTABLE_FAILURE_PREFLIGHT_30_OF_30_EXECUTED"),
                        self.workflow.index("Capture official PC observed originals"))
        self.assertLess(self.workflow.rindex("PREDICTABLE_FAILURE_PREFLIGHT_30_OF_30_EXECUTED"),
                        self.workflow.index("Independently verified SP link, otherwise record zero-request stop"))
        self.assertEqual(self.ledger["required_approval"]["enumerated_cases"],30)
        self.assertFalse(self.ledger["required_approval"]["prediction_release_allowed"])

    def test_both_schedules_and_no_global_hard_block(self):
        self.assertIn("cron: '5 2 21 11 *'",self.workflow)
        self.assertIn("cron: '10 2 22 11 *'",self.workflow)
        self.assertNotIn("Critical incident containment",self.workflow)
        self.assertNotIn("RELEASE_BLOCKED_OPEN_CRITICAL_INCIDENTS",self.workflow)

    def test_two_critical_defects_have_test_proof(self):
        self.assertEqual(self.ledger["status"],"OBSERVATION_ONLY_CANDIDATE_OFFLINE_VERIFIED")
        self.assertEqual(self.ledger["required_approval"]["approved_commit_sha"],PIN)
        for issue in ("KW-001","KW-002"):
            self.assertEqual(self.issues[issue]["state"],"FIXED_AND_OFFLINE_REGRESSION_VERIFIED")
            self.assertIn("CI run",self.issues[issue]["fix_evidence"])

    def test_no_fake_live_market_certification(self):
        self.assertFalse(self.ledger["required_approval"]["live_source_verified"])
        self.assertFalse(self.ledger["required_approval"]["prediction_release_allowed"])
        self.assertEqual(self.issues["KW-005"]["state"],"LIVE_OBSERVATION_REQUIRED")
        self.assertIn("KYOTO_NOV22_VERIFIED_COLLECTOR_SHA",self.workflow)
        self.assertEqual(self.workflow.count("--seal-only"),2)
        self.assertNotIn("path: pc_raw/",self.workflow)
        self.assertNotIn("path: sp_raw/",self.workflow)

if __name__=="__main__":
    unittest.main()
