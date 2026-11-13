"""Static proof that the proposed main launcher is observation-only and fail-closed."""
import unittest
from pathlib import Path
P=Path(".github/workflows/kyoto-nov15-unattended-observer-launcher.yml")
class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.s=P.read_text(encoding="utf8")
    def test_pinned_source_and_no_default_checkout(self):
        self.assertIn("ref: b03c0a0543e65479832a01a590df94f3a28f2b92",self.s)
        self.assertIn("NOV15_SOURCE_REVISION_MISMATCH_NO_HTTP",self.s)
    def test_new_offline_tests_precede_every_live_request(self):
        marker="Verify new source acquisition and encryption regressions without JRA HTTP"
        self.assertIn(marker,self.s)
        self.assertIn("test_kyoto_nov15_two_original_observer.py",self.s)
        self.assertIn("test_kyoto_nov15_offline_race_links.py",self.s)
        self.assertIn("test_kyoto_nov15_encrypted_evidence.py",self.s)
        self.assertLess(self.s.index(marker),
                        self.s.index("Pre-HTTP date, source revision and encryption"))
        self.assertLess(self.s.index(marker),
                        self.s.index("At most EIGHT bounded original-only official PC HTTP requests"))
    def test_dependency_install_precedes_pre_http_imports(self):
        self.assertLess(self.s.index("name: Install parser and crypto"),
                        self.s.index("name: Pre-HTTP date, source revision and encryption"))
        self.assertLess(self.s.index("name: Pre-HTTP date, source revision and encryption"),
                        self.s.index("name: At most EIGHT bounded original-only official PC HTTP requests"))
    def test_offline_first_external_request_is_guarded(self):
        self.assertIn("from diagnostics.kyoto_nov15_two_original_observer import BEGIN,END",self.s)
        self.assertNotIn("from diagnostics.kyoto_p1_github_attempt_history_gate import audit_previous_runs",self.s)
    def test_date_guard_kept_and_manual_recovery_dispatch_allowed(self):
        self.assertIn('now.strftime("%Y-%m-%d")!="2026-11-15"',self.s)
        self.assertNotIn('os.environ.get("GITHUB_RUN_ATTEMPT")!="1"',self.s)
        self.assertIn('("schedule","workflow_dispatch")',self.s)
        self.assertIn("NOV15_UNEXPECTED_TRIGGER_NO_HTTP",self.s)
        self.assertNotIn("NOV15_ONLY_SCHEDULED_UNATTENDED_OBSERVATION_NO_HTTP",self.s)
    def test_no_blanket_prior_attempt_permanent_ban(self):
        self.assertNotIn("audit_previous_runs(",self.s)
        self.assertNotIn("NOV15_NO_RERUN",self.s)
    def test_secret_is_checked_and_not_logged(self):
        self.assertIn("NOV15_ARCHIVE_SECRET_INVALID_NO_HTTP",self.s)
        self.assertIn("secrets.KYOTO_JRA_ARCHIVE_AES256_HEX",self.s)
        self.assertNotIn('print(os.environ["ARCHIVE_KEY"])',self.s)
    def test_encrypted_only_artifact(self):
        self.assertIn("kyoto_nov15_encrypted_evidence import encrypt_evidence",self.s)
        self.assertIn("path: nov15_unattended_evidence/",self.s)
        self.assertNotIn("path: nov15_work_originals/",self.s)
    def test_offline_race_link_index_encrypted_not_public(self):
        self.assertIn("python -m diagnostics.kyoto_nov15_offline_race_links",self.s)
        self.assertIn("--output nov15_work_originals/observed_race_links.json",self.s)
        self.assertLess(self.s.index("python -m diagnostics.kyoto_nov15_offline_race_links"),
                        self.s.index("- name: Encrypt observation originals"))
        self.assertIn("encrypt_evidence(source,dest",self.s)
    def test_observed_racecard_then_bounded_menu_and_market_originals(self):
        self.assertIn("include_observed_racecard=True",self.s)
        self.assertIn("include_observed_odds_menu=True",self.s)
        self.assertIn("At most EIGHT bounded original-only official PC HTTP requests",self.s)
        self.assertIn("NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD",self.s)
        self.assertIn("NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",self.s)
    def test_no_market_claim_or_direct_wager(self):
        self.assertNotIn("python -m diagnostics.jra_one_shot_market_capture",self.s)
        self.assertNotIn("--authorized-live-http",self.s)
        self.assertIn("kyoto_nov15_offline_race_links",self.s)
    def test_only_fixed_sunday_schedule(self):
        self.assertIn("cron: '0 2 15 11 *'",self.s)
if __name__=="__main__": unittest.main()
