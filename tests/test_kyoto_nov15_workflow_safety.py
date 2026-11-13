"""Workflow source guard rails: Nov15 cannot accidentally run on routine pushes."""
import unittest
from pathlib import Path

WORKFLOW=Path(".github/workflows/kyoto-nov15-second-day-observed-oneshot.yml")

class Nov15WorkflowSafetyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    cls.s=WORKFLOW.read_text(encoding="utf8")
 def test_only_explicit_activation_is_push_trigger(self):
    self.assertIn("paths: ['diagnostics/nov15_pc_explicit_activation.txt']",self.s)
    self.assertNotIn("schedule:",self.s)
 def test_manual_dispatch_requires_confirmation(self):
    self.assertIn("NOV15-ONE-SHOT-READ-ONLY",self.s)
    self.assertIn("github.event.inputs.confirmation == 'NOV15-ONE-SHOT-READ-ONLY'",self.s)
 def test_actual_http_only_after_offline_original_handoff(self):
    self.assertLess(self.s.index("validate"),self.s.index("--authorized-live-http")) if "validate" in self.s else self.assertLess(self.s.index("python -m diagnostics.kyoto_nov14_nov15_second_day_handoff"),self.s.index("--authorized-live-http"))
 def test_replay_attempt_blocked_before_network(self):
    self.assertIn('GITHUB_RUN_ATTEMPT',self.s)
    self.assertIn('NOV15_PRIOR_DISPATCH_ALREADY_EXISTS_NO_REPEAT',self.s)
    self.assertLess(self.s.index('NOV15_PRIOR_DISPATCH_ALREADY_EXISTS_NO_REPEAT'),self.s.index('--authorized-live-http'))
 def test_fail_closed_git_hub_run_api(self):
    self.assertIn('NOV15_PRIOR_RUN_AUDIT_INCOMPLETE',self.s)
    self.assertIn('urlopen(request,timeout=12)',self.s)
    self.assertIn('actions: read',self.s)
 def test_no_guessed_sp_urls(self):
    self.assertIn('--channel PC',self.s)
    self.assertNotIn('--channel SP',self.s)
    self.assertNotIn('--hybrid',self.s)
 def test_no_live_model_or_real_wager(self):
    self.assertIn('NO_REAL_BETS=TRUE',self.s)
    self.assertIn('NOV15_SOURCE_ONLY_NOT_LIVE_CERTIFICATION=TRUE',self.s)
 def test_utc_start_must_be_verified(self):
    self.assertIn('NOV15_VERIFIED_START_NOT_PROVIDED',self.s)
    self.assertIn('nov15_pc_verified_start_utc.txt',self.s)
    self.assertIn('export START_UTC',self.s)
 def test_no_day14_capture_reactivation(self):
    self.assertIn('nov14_existing_attempt_safe_stop_20261113.md',self.s)
    self.assertIn('NOV14_EXISTING_ATTEMPT_NOT_REPEATED=TRUE',self.s)
 def test_preserves_artifact_even_on_failure(self):
    self.assertIn('if: always()',self.s)
    self.assertIn('retention-days: 30',self.s)
    self.assertIn('nov15_preflight_receipt.json',self.s)
 def test_racecard_links_are_not_hardcoded(self):
    self.assertIn('nov15_pc_official_selection.html',self.s)
    self.assertIn('nov15_pc_official_meeting.html',self.s)
    self.assertNotIn('CNAME=pw',self.s)
 def test_only_dev_branch_dispatch_path(self):
    self.assertIn('branches: [jra-html-diagnostic-20261105]',self.s)
    self.assertIn('cancel-in-progress: false',self.s)

if __name__=="__main__":
    unittest.main()
