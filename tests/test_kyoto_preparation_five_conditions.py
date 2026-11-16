"""Fixed five pre-experiment quality contracts; real execution is gated by CI needs."""
import json,unittest
from pathlib import Path
P=Path("docs/diagnostics/KYOTO_PREPARATION_FIVE_CONDITIONS_20261116.json")
R=Path("docs/diagnostics/KYOTO_20261116_INDEPENDENT_RELEASE_BLOCKERS.json")
W=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")
H=Path(".github/workflows/kyoto-20261121-22-result-handoff.yml")
S=Path(".github/workflows/kyoto-weekend-production-readiness-smoke.yml")
class FiveFixedReadinessCriteria(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    cls.p=json.loads(P.read_text());cls.r=json.loads(R.read_text())
    cls.w=W.read_text();cls.h=H.read_text();cls.s=S.read_text()
 def test_c1_prior_week_regressions_not_omitted(self):
    history=Path("docs/diagnostics/KYOTO_NOV14_15_PREHTTP_ROOT_CAUSE_AND_PREVENTION_20261116.md").read_text()
    for code in ("43547344697","43669118231","mandatory_original_capture_timestamp_missing","FileNotFoundError"):
        self.assertIn(code,history)
    for module in ("tests.test_kyoto_nov15_offline_race_links","tests.test_kyoto_safe_stop_artifact","tests.test_kyoto_nov15_two_original_observer"):
        self.assertIn(module,self.s)
 def test_c2_same_12r_and_sequential_sp_fallback(self):
    self.assertEqual(self.w.count("tests.test_kyoto_weekend_race_parity"),2)
    self.assertIn("needs: pc-originals-independent",self.w)
    self.assertIn("if: ${{ always() && (github.event_name",self.w)
    self.assertIn("run: sleep 3",self.w)
    self.assertIn("tests.test_kyoto_weekend_race_parity",self.s)
 def test_c3_crypto_provenance_and_failure_path(self):
    self.assertEqual(self.w.count("--seal-only"),2)
    self.assertIn("path: pc_sealed/",self.w)
    self.assertIn("path: sp_sealed/",self.w)
    self.assertNotIn("path: pc_raw/",self.w)
    for module in ("tests.test_kyoto_weekend_postflight","tests.test_kyoto_nov15_encrypted_evidence","tests.test_kyoto_weekend_day21_artifact_triage","tests.test_kyoto_weekend_interruption_and_pacing"):
        self.assertIn(module,self.s)
 def test_c4_sunday_plan_and_actual_21st_evidence_triage(self):
    self.assertIn("cron: '10 2 22 11 *'",self.w)
    self.assertIn("cron: '50 2 21 11 *'",self.w)
    self.assertIn("cron: '55 2 22 11 *'",self.w)
    self.assertEqual(self.w.count("kyoto_weekend_retry_guard --day"),2)
    self.assertIn("workflow_run:",self.h)
    self.assertIn("cron: '0 12 21 11 *'",self.h)
    self.assertIn("kyoto_weekend_day21_artifact_triage",self.h)
    self.assertIn("strategy[\'SP\']",self.h)
    self.assertIn("tests.test_kyoto_weekend_sp_discovery",self.s)
    self.assertIn("tests.test_kyoto_weekend_handoff_workflow",self.s)
    self.assertIn("tests.test_kyoto_weekend_handoff_workflow",self.s)
 def test_c5_exact_sha_active_runtime_gates_and_backup(self):
    sha=self.p["collector_sha"]
    self.assertEqual(len(sha),40)
    self.assertEqual(self.r["production_observer_pinned_sha"],sha)
    self.assertEqual(self.r["required_approval"]["approved_commit_sha"],sha)
    self.assertEqual(self.s.count("ref: "+sha),1)
    for word in ("DAY21_22_CRITICAL_SECRET_FORMAT_VALID=TRUE","DAY21_22_SCHEDULED_WORKFLOWS_ACTIVE=TRUE","DAY22_OVERRIDE_VERIFIED_OR_BASELINE_FALLBACK=TRUE"):
        self.assertIn(word,self.s)
    self.assertEqual(self.r["required_approval"]["pre_experiment_backup_run_id"],self.p["backup"]["run_id"])
    self.assertGreater(self.p["backup"]["size_bytes"],1000000)
    self.assertFalse(self.r["required_approval"]["prediction_release_allowed"])
if __name__=="__main__":
 unittest.main()
