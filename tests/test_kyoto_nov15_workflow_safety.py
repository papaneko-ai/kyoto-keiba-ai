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
 def test_historical_replay_blocked_by_fixed_market_window_before_http(self):
    # This is a 2026-11-15 historical diagnostic, not the Nov21/22 workflow.
    # It must stop outside the exact 2026-11-15 start-time window.
    self.assertIn("NOV15_PC_OUTSIDE_MARKET_WINDOW_NO_HTTP_RETRY_SAFE",self.s)
    self.assertIn('strftime("%Y%m%d")!="20261115"',self.s)
    self.assertLess(self.s.index("NOV15_PC_OUTSIDE_MARKET_WINDOW_NO_HTTP_RETRY_SAFE"),
                    self.s.index("--authorized-live-http"))
 def test_fail_closed_prior_observer_api_and_identity(self):
    self.assertIn('gh api "repos/$GITHUB_REPOSITORY/actions/runs/$OBSERVER_RUN"',self.s)
    self.assertIn("kyoto_nov15_observer_artifact_identity",self.s)
    self.assertLess(self.s.index("kyoto_nov15_observer_artifact_identity"),
                    self.s.index("--authorized-live-http"))
    self.assertIn("actions: read",self.s)
 def test_optional_pc_404_repair_is_not_implicitly_enabled(self):
    # Legacy 11/15 source uses default no-repair; bounded 404 repair is a
    # separate opt-in in the actual capturer, not an implied workflow option.
    source=Path("diagnostics/jra_one_shot_market_capture.py").read_text(encoding="utf8")
    self.assertIn("auto_repair_broken_pc_link=False",source)
    self.assertIn("broken.code in (404,410)",source)
    self.assertNotIn("--auto-repair-broken-pc-link",self.s)
 def test_no_guessed_sp_urls(self):
    self.assertIn("--channel PC",self.s)
    self.assertNotIn("--channel SP",self.s)
    self.assertNotIn("CNAME=sw",self.s)
    # A hybrid is valid only where a separate SP observed link already exists.
    source=Path("diagnostics/jra_one_shot_market_capture.py").read_text(encoding="utf8")
    self.assertIn("other_source_available=bool(other_url)",source)
    self.assertIn("spec.validate(require_channels=(primary_channel,))",source)
 def test_no_live_model_or_real_wager(self):
    self.assertIn('NO_REAL_BETS=TRUE',self.s)
    self.assertIn('python -m diagnostics.kyoto_nov15_capture_acceptance',self.s)
    self.assertLess(self.s.index('--authorized-live-http'),self.s.index('python -m diagnostics.kyoto_nov15_capture_acceptance'))
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
 def test_plaintext_artifacts_never_uploaded(self):
    self.assertIn('path: nov15_encrypted_capture/',self.s)
    self.assertNotIn('path: nov15_pc_one_shot/',self.s)
    self.assertIn('kyoto_nov15_full_capture_seal',self.s)
 def test_prior_observation_artifact_is_authenticated(self):
    # Artifact identity is computed from actual GitHub run metadata; requiring
    # one hard-coded artifact name would reintroduce guessing.
    self.assertIn("kyoto_nov15_observer_artifact_identity",self.s)
    self.assertIn("kyoto_nov15_encrypted_evidence",self.s)
    self.assertIn("ARCHIVE_KEY",self.s)
 def test_racecard_links_are_not_hardcoded(self):
    self.assertIn('nov15_decrypted/official_selection.html',self.s)
    self.assertIn('nov15_decrypted/official_meeting.html',self.s)
    self.assertNotIn('CNAME=pw',self.s)
 def test_only_dev_branch_dispatch_path(self):
    self.assertIn('branches: [jra-html-diagnostic-20261105]',self.s)
    self.assertIn('cancel-in-progress: false',self.s)

if __name__=="__main__":
    unittest.main()
