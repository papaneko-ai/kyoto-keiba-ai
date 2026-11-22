import unittest
from diagnostics.kyoto_impl28_detailed_coverage import check_race, check_day

class CoverageTests(unittest.TestCase):
    def test_no_starters_fails(self):
        self.assertIn("NO_STARTERS", check_race({}))
    def test_missing_fields_are_not_silently_accepted(self):
        errors = check_race({"starters":[{"horse_number":1,"horse_id":"h1","fields":{"frame_number":1}},{"horse_number":2,"horse_id":"h2","fields":{"frame_number":2}}]})
        self.assertIn("HORSE_1_MISSING_training", errors)
        self.assertIn("QUINELLA_MISSING_PAIRS_1", errors)
        self.assertIn("BRACKET_QUINELLA_MISSING_PAIRS_1", errors)
    def test_cancelled_is_not_invalid_price(self):
        r={"starters":[{"horse_number":1,"horse_id":"h1","fields":{"frame_number":1}},{"horse_number":2,"horse_id":"h2","fields":{"frame_number":2}}],"markets":{"quinella":{"1-2":"取消"},"bracket_quinella":{"1-2":"取消"}}}
        errors=check_race(r)
        self.assertFalse(any("INVALID_1-2" in e for e in errors))
    def test_same_frame_pair_is_required(self):
        r={"starters":[{"horse_number":1,"horse_id":"h1","fields":{"frame_number":1}},{"horse_number":2,"horse_id":"h2","fields":{"frame_number":1}}],"markets":{"quinella":{"1-2":"3.4"},"bracket_quinella":{}}}
        self.assertIn("BRACKET_QUINELLA_MISSING_PAIRS_1", check_race(r))
    def test_all_twelve_required(self):
        self.assertEqual(len(check_day({})["failed_races"]),12)
if __name__ == "__main__":
    unittest.main()
