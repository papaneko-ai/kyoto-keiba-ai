"""Static proof that the proposed main launcher is observation-only and fail-closed."""
import unittest
from pathlib import Path
P=Path(".github/workflows/kyoto-nov15-unattended-observer-launcher.yml")
class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.s=P.read_text(encoding="utf8")
    def test_pinned_source_and_no_default_checkout(self):
        self.assertIn("ref: ba320b5c8de6bb1a5b1ffacb9e48a6e967d94a6a",self.s)
        self.assertIn("NOV15_SOURCE_REVISION_MISMATCH_NO_HTTP",self.s)
    def test_dependency_install_precedes_pre_http_imports(self):
        self.assertLess(self.s.index("name: Install parser and crypto"),
                        self.s.index("name: Pre-HTTP date, launch, key, revision"))
        self.assertLess(self.s.index("name: Pre-HTTP date, launch, key, revision"),
                        self.s.index("name: At most THREE bounded original-only official PC HTTP GET"))
    def test_offline_first_external_request_is_guarded(self):
        self.assertIn("from diagnostics.kyoto_nov15_two_original_observer import BEGIN,END",self.s)
        self.assertIn("from diagnostics.kyoto_p1_github_attempt_history_gate import audit_previous_runs",self.s)
    def test_date_and_no_rerun(self):
        self.assertIn('now.strftime("%Y-%m-%d")!="2026-11-15"',self.s)
        self.assertIn('os.environ.get("GITHUB_RUN_ATTEMPT")!="1"',self.s)
        self.assertIn('os.environ.get("GITHUB_EVENT_NAME")!="schedule"',self.s)
    def test_history_before_external_get(self):
        self.assertLess(self.s.index("audit_previous_runs("),self.s.index("At most THREE bounded original-only official PC HTTP GET"))
    def test_secret_is_checked_and_not_logged(self):
        self.assertIn("NOV15_ARCHIVE_SECRET_INVALID_NO_HTTP",self.s)
        self.assertIn("secrets.KYOTO_JRA_ARCHIVE_AES256_HEX",self.s)
        self.assertNotIn('print(os.environ["ARCHIVE_KEY"])',self.s)
    def test_encrypted_only_artifact(self):
        self.assertIn("kyoto_nov15_encrypted_evidence import encrypt_evidence",self.s)
        self.assertIn("path: nov15_unattended_evidence/",self.s)
        self.assertNotIn("path: nov15_work_originals/",self.s)
    def test_third_observed_racecard_only_without_market_release(self):
        self.assertIn("include_observed_racecard=True",self.s)
        self.assertIn("At most THREE bounded original-only official PC HTTP GET",self.s)
        self.assertIn("NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD",self.s)
    def test_no_market_claim_or_direct_wager(self):
        self.assertNotIn("jra_one_shot_market_capture",self.s)
        self.assertNotIn("--authorized-live-http",self.s)
    def test_only_fixed_sunday_schedule(self):
        self.assertIn("cron: '0 2 15 11 *'",self.s)
if __name__=="__main__": unittest.main()
