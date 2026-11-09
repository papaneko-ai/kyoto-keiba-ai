import copy
import json
import unittest
from pathlib import Path

from diagnostics.p1_monitor_viewmodel import StatusInvalid, summarize

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json"


class HistoricalStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(STATUS.read_text(encoding="utf-8"))

    def case(self, change):
        status = copy.deepcopy(self.original)
        change(status)
        return summarize(status)

    def test_real_archived_status(self):
        result = self.case(lambda s: None)
        self.assertEqual((result["runner_count"], result["verified"], result["unqueried"]),
                         (148, 96, 52))
        self.assertEqual(result["prior_rows"], 592)
        self.assertEqual(result["completed_race_sum"], 91)
        self.assertEqual(result["verified_not_allocated_to_completed_races"], 5)
        self.assertIs(result["prediction_ready"], False)

    def test_reproducible(self):
        self.assertEqual(self.case(lambda s: None), self.case(lambda s: None))

    def test_reject_wrong_schema(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s.update(schema_version="invalid"))

    def test_reject_old_12_profiles(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s.update(profile_details_source_verified=12))

    def test_reject_missing_verification_group(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s.update(unverified_groups=[]))

    def test_reject_unsafe_prediction_flag(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s.update(prediction_ready=True))

    def test_reject_nonboolean_prediction_flag(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s.update(prediction_ready=0))

    def test_reject_extra_finished_race(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s['completed_race_runner_counts'].update({'9': 2}))

    def test_reject_sum_greater_than_verified(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s['completed_race_runner_counts'].update({'1': 18, '2': 18, '3': 18, '4': 18,
                                                                           '5': 18, '6': 18, '7': 18, '8': 18}))

    def test_reject_negative_rows(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s.update(total_finished_prior_rows=-1))

    def test_reject_flag_changed(self):
        with self.assertRaises(StatusInvalid):
            self.case(lambda s: s.update(permanent_html_archive_completed=True))


if __name__ == "__main__":
    unittest.main()
