"""Main-branch source-only release gate: exact repair SHA, open prediction gates."""
import json
import unittest
from pathlib import Path

WF=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")
REG=Path("docs/diagnostics/KYOTO_20261116_INDEPENDENT_RELEASE_BLOCKERS.json")
PIN="1a953bcb08adb871f930521cf24cb0266fbc2339"

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

    def test_sequential_cross_job_network_but_sp_runs_after_pc_failure(self):
        pc,sp=self.workflow.split("  sp-originals-independent:",1)
        self.assertIn("needs: pc-originals-independent",sp)
        self.assertIn("if: ${{ always() && (github.event_name",sp)
        self.assertIn("run: sleep 3",sp)
        self.assertLess(sp.index("run: sleep 3"),
                        sp.index("Independently verified SP link, otherwise record zero-request stop"))

    def test_both_lanes_verify_exact_12r_before_any_jra_http(self):
        self.assertEqual(self.workflow.count("tests.test_kyoto_weekend_race_parity"),2)
        self.assertEqual(self.ledger["required_approval"]["approved_commit_sha"],PIN)

    def test_both_schedules_and_no_global_hard_block(self):
        self.assertIn("cron: '5 2 21 11 *'",self.workflow)
        self.assertIn("cron: '10 2 22 11 *'",self.workflow)
        self.assertNotIn("Critical incident containment",self.workflow)
        self.assertNotIn("RELEASE_BLOCKED_OPEN_CRITICAL_INCIDENTS",self.workflow)

    def test_schedule_backup_is_not_blocked_by_prior_failed_attempt(self):
        for cron in ("50 2 21 11 *","55 2 22 11 *"):
            self.assertIn("cron: '"+cron+"'",self.workflow)
        self.assertEqual(self.workflow.count("kyoto_weekend_retry_guard --day"),2)
        self.assertNotIn("RERUN_FORBIDDEN_NO_HTTP",self.workflow)
        self.assertNotIn("PREVIOUS_WORKFLOW_RUN_ON_TARGET_DAY_NO_HTTP",self.workflow)
        self.assertIn("KYOTO_NOV22_VERIFIED_COLLECTOR_SHA",self.workflow)

    def test_two_critical_defects_have_test_proof(self):
        self.assertEqual(self.ledger["status"],"OBSERVATION_ONLY_CANDIDATE_OFFLINE_VERIFIED")
        self.assertEqual(self.ledger["required_approval"]["approved_commit_sha"],PIN)
        for issue in ("KW-001","KW-002"):
            self.assertEqual(self.issues[issue]["state"],"FIXED_AND_OFFLINE_REGRESSION_VERIFIED")
            self.assertIn("CI run",self.issues[issue]["fix_evidence"])

    def test_source_observation_cannot_be_mistaken_for_complete_predictable_risk_audit(self):
        approval=self.ledger["required_approval"]
        self.assertIs(approval["fmea_completeness_demonstrated"],False)
        self.assertEqual(approval["top_level_functions_in_source_closure"],81)
        self.assertEqual(approval["unreviewed_top_level_functions"],52)
        self.assertEqual(approval["unreviewed_class_methods"],10)
        self.assertEqual(approval["additional_open_risk_families"],22)
        self.assertIs(approval["source_only_observation_not_certification"],True)

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
