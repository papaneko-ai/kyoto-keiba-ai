"""Static release gates for the exact scheduled weekend no-replay workflow."""
from pathlib import Path
import unittest

SRC=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")


class ProductionWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=SRC.read_text(encoding="utf8")

    def test_two_distinct_date_locked_schedules(self):
        self.assertIn("cron: '5 2 21 11 *'", self.s)
        self.assertIn("cron: '10 2 22 11 *'", self.s)
        self.assertIn("20261121", self.s)
        self.assertIn("20261122", self.s)

    def test_day21_immutable_source_and_day22_verified_promotion(self):
        pinned="d5e0de7cc39afe8fd168f40a1915e9ddfb668f1a"
        self.assertIn("KYOTO_NOV22_VERIFIED_COLLECTOR_SHA",self.s)
        self.assertEqual(self.s.count("ref: ${{ env.COLLECTOR_SHA }}"),2)
        self.assertEqual(self.s.count("DAY21_SOURCE_UNEXPECTED_NO_HTTP"),2)
        self.assertEqual(self.s.count("DAY22_CANDIDATE_NOT_PREFLIGHT_VERIFIED_NO_HTTP"),2)
        self.assertIn(pinned,self.s)
        self.assertNotIn("ref: main",self.s)

    def test_independent_lane_jobs_no_dependency(self):
        self.assertIn("pc-originals-independent:",self.s)
        self.assertIn("sp-originals-independent:",self.s)
        self.assertNotIn("needs:",self.s)
        self.assertEqual(self.s.count("uses: actions/upload-artifact@v4"),2)

    def test_pre_http_all_bounded_and_no_replay(self):
        self.assertEqual(self.s.count('GITHUB_RUN_ATTEMPT'),2)
        self.assertEqual(self.s.count("PREVIOUS_WORKFLOW_RUN_ON_TARGET_DAY_NO_HTTP"),2)
        self.assertEqual(self.s.count("RUN_HISTORY_UNVERIFIED_NO_HTTP"),2)
        self.assertEqual(self.s.count("SAME_DAY_HISTORY_NEEDS_PAGINATION_NO_HTTP"),2)
        self.assertEqual(self.s.count('"?created="+target'),2)
        self.assertEqual(self.s.count("ENCRYPTION_KEY_REQUIRED_NO_HTTP"),2)
        self.assertEqual(self.s.count("SOURCE_REVISION_MISMATCH_NO_HTTP"),2)
        self.assertIn("concurrency:",self.s)

    def test_seal_all_exits_and_no_plaintext_upload(self):
        self.assertEqual(self.s.count("if: always()"),6)
        self.assertEqual(self.s.count("--seal-only"),2)
        self.assertEqual(self.s.count("tests.test_kyoto_weekend_end_to_end"),2)
        self.assertEqual(self.s.count("kyoto_weekend_postflight"),2)
        self.assertIn("path: pc_sealed/",self.s)
        self.assertIn("path: sp_sealed/",self.s)
        self.assertNotIn("path: pc_raw/",self.s)
        self.assertNotIn("path: sp_raw/",self.s)

    def test_sp_url_is_independently_configured_not_computed(self):
        self.assertIn("vars.KYOTO_NOV21_SP_OFFICIAL_R12_URL",self.s)
        self.assertIn("vars.KYOTO_NOV22_SP_OFFICIAL_R12_URL",self.s)
        self.assertNotIn("CNAME=sw",self.s)

    def test_only_explicit_dispatch_or_schedule(self):
        self.assertIn("NOV21-22-OBSERVE-READ-ONLY",self.s)
        self.assertNotIn("  push:",self.s)
        self.assertEqual(self.s.count("GITHUB_EVENT_NAME"),2)


if __name__ == "__main__":
    unittest.main()
