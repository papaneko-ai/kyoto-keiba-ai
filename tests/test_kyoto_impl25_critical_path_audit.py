"""No-network contract for exact Nov21-22 acquisition critical path audit."""
import unittest
from diagnostics.kyoto_impl25_critical_path_audit import audit


COLLECTOR = """
g03=collect_after_observer(
g04=g04_capture(
g05=compile_saved(
track=capture_kyoto_track(
markets=run_twelve(
"""
WORKFLOW = """
on:
  schedule:
    - cron: '15 0 21 11 *'
    - cron: '15 1 21 11 *'
    - cron: '5 2 21 11 *'
    - cron: '50 2 21 11 *'
    - cron: '15 0 22 11 *'
    - cron: '15 1 22 11 *'
    - cron: '10 2 22 11 *'
    - cron: '55 2 22 11 *'
jobs:
  pc-originals-independent:
    timeout-minutes: 20
    steps: []
  sp-originals-independent:
    needs: pc-originals-independent
    timeout-minutes: 12
    env:
      COLLECTOR_SHA: '324a76fd57ea9c660d984fcc4fc373cba4e30109'
"""


class TimingAuditTests(unittest.TestCase):
    def test_current_risk_is_observed_without_claiming_runtime(self):
        a = audit(COLLECTOR, WORKFLOW)
        self.assertEqual(a["scheduled_slot_count"], 8)
        self.assertEqual(a["pc_timeout_minutes"], 20)
        self.assertFalse(a["g04_after_g06"])
        self.assertFalse(a["duration_measured"])
        self.assertFalse(a["race_day_success_proven"])

    def test_eight_slots_must_not_be_silently_reduced(self):
        with self.assertRaisesRegex(ValueError, "eight_independent"):
            audit(COLLECTOR, WORKFLOW.replace("    - cron: '55 2 22 11 *'\n", ""))

    def test_missing_stage_cannot_be_hidden(self):
        with self.assertRaisesRegex(ValueError, "capture_stage_missing"):
            audit(COLLECTOR.replace("g04=g04_capture(", "no_g04("), WORKFLOW)

    def test_missing_immutable_pin_fails(self):
        with self.assertRaisesRegex(ValueError, "expected_immutable"):
            audit(COLLECTOR, WORKFLOW.replace("324a76fd57ea9c660d984fcc4fc373cba4e30109", "bad"))

    def test_reordering_is_reported_not_assumed_safe(self):
        reordered = COLLECTOR.replace("g04=g04_capture(\ng05=compile_saved(\ntrack=capture_kyoto_track(\nmarkets=run_twelve(", "markets=run_twelve(\ng04=g04_capture(\ng05=compile_saved(\ntrack=capture_kyoto_track(")
        a = audit(reordered, WORKFLOW)
        self.assertTrue(a["g04_after_g06"])
        self.assertFalse(a["race_day_success_proven"])


if __name__ == "__main__":
    unittest.main()
