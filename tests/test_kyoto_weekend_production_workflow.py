"""Static release gates for the exact scheduled weekend no-replay workflow."""
from pathlib import Path
import unittest

SRC=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")


class ProductionWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=SRC.read_text(encoding="utf8")

    def test_two_distinct_date_locked_schedules(self):
        self.assertIn("cron: '5 1 21 11 *'", self.s)
        self.assertIn("cron: '10 1 22 11 *'", self.s)
        self.assertIn("cron: '5 2 21 11 *'", self.s)
        self.assertIn("cron: '10 2 22 11 *'", self.s)
        self.assertIn("cron: '50 2 21 11 *'",self.s)
        self.assertIn("cron: '55 2 22 11 *'",self.s)
        self.assertIn("20261121", self.s)
        self.assertIn("20261122", self.s)

    def test_day21_immutable_source_and_day22_verified_promotion(self):
        pinned="e2a48f8b58ae13c210eead22533ee107004a45cd"
        self.assertIn("KYOTO_NOV22_VERIFIED_COLLECTOR_SHA",self.s)
        self.assertEqual(self.s.count("ref: ${{ env.COLLECTOR_SHA }}"),2)
        self.assertEqual(self.s.count("DAY21_SOURCE_UNEXPECTED_NO_HTTP"),2)
        self.assertEqual(self.s.count("DAY22_CANDIDATE_NOT_PREFLIGHT_VERIFIED_NO_HTTP"),2)
        self.assertIn(pinned,self.s)
        self.assertNotIn("ref: main",self.s)

    def test_full_predictable_failure_gate_required_in_both_lanes(self):
        self.assertEqual(self.s.count("diagnostics.kyoto_predictable_failure_gate"),2)
        self.assertEqual(self.s.count("tests.test_kyoto_predictable_failure_gate"),2)
        self.assertEqual(self.s.count("PREDICTABLE_FAILURE_PREFLIGHT_30_OF_30_EXECUTED"),2)
        self.assertLess(self.s.index("PREDICTABLE_FAILURE_PREFLIGHT_30_OF_30_EXECUTED"),
                        self.s.index("Capture official PC observed originals"))
        self.assertLess(self.s.rindex("PREDICTABLE_FAILURE_PREFLIGHT_30_OF_30_EXECUTED"),
                        self.s.index("Independently verified SP link, otherwise record zero-request stop"))

    def test_pre_http_both_lanes_rehearse_exact_race_parity(self):
        self.assertEqual(self.s.count("tests.test_kyoto_weekend_race_parity"),2)
        self.assertIn("12R",Path("diagnostics/kyoto_nov15_two_original_observer.py").read_text())

    def test_independent_source_lanes_run_sequentially_even_if_pc_fails(self):
        self.assertIn("pc-originals-independent:",self.s)
        self.assertIn("sp-originals-independent:",self.s)
        pc,sp=self.s.split("  sp-originals-independent:",1)
        self.assertNotIn("needs:",pc)
        self.assertIn("needs: pc-originals-independent",sp)
        self.assertIn("if: ${{ always() && (github.event_name",sp)
        self.assertIn("Cross-job HTTP separation before any official SP request",sp)
        self.assertIn("run: sleep 3",sp)
        self.assertLess(sp.index("run: sleep 3"),
                        sp.index("Independently verified SP link, otherwise record zero-request stop"))
        self.assertEqual(self.s.count("uses: actions/upload-artifact@v4"),2)

    def test_pre_http_all_bounded_and_no_replay(self):
        self.assertEqual(self.s.count('GITHUB_RUN_ATTEMPT'),2)
        self.assertEqual(self.s.count("python -m diagnostics.kyoto_weekend_retry_guard --day"),2)
        self.assertIn("GITHUB_EVENT_SCHEDULE",self.s)
        self.assertIn("kyoto-20261121-22-source-",self.s)
        self.assertIn("github.event.schedule == '50 2 21 11 *'",self.s)
        self.assertIn("github.event.schedule == '55 2 22 11 *'",self.s)
        self.assertIn("tests.test_kyoto_weekend_retry_guard",self.s)
        self.assertEqual(self.s.count("ENCRYPTION_KEY_REQUIRED_NO_HTTP"),2)
        self.assertEqual(self.s.count("SOURCE_REVISION_MISMATCH_NO_HTTP"),2)
        self.assertIn("concurrency:",self.s)
        self.assertIn("queue: max",self.s)
        self.assertIn("cancel-in-progress: false",self.s)

    def test_backup_same_day_concurrency_and_failure_only_policy(self):
        from diagnostics.kyoto_weekend_retry_guard import ADVANCE,PRIMARY,BACKUP
        self.assertEqual(set(ADVANCE),{"20261121","20261122"})
        self.assertEqual(set(PRIMARY),{"20261121","20261122"})
        self.assertEqual(set(BACKUP),set(PRIMARY))
        group=self.s.split("concurrency:",1)[1].split("jobs:",1)[0]
        self.assertIn("20261121",group)
        self.assertIn("github.event.schedule == '5 1 21 11 *'",group)
        self.assertIn("20261122",group)
        self.assertNotIn("github.event.schedule || inputs.race_day",group)

    def test_seal_all_exits_and_no_plaintext_upload(self):
        self.assertEqual(self.s.count("if: always()"),6)
        self.assertEqual(self.s.count("--seal-only"),2)
        self.assertEqual(self.s.count("tests.test_kyoto_weekend_end_to_end"),2)
        self.assertEqual(self.s.count("kyoto_weekend_postflight"),4)
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
