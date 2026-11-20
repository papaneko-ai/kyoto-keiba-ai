"""C10 source-grounded auxiliary coverage and missing-workout regressions."""
import json
import unittest
from tests.test_kyoto_g05_conditions import G05Tests, DAY
from tests.test_kyoto_g05_official_track import html
from diagnostics.kyoto_g05_conditions import compile_saved
from diagnostics.kyoto_g05_official_track import capture_kyoto_track
from diagnostics.kyoto_impl25_c10_auxiliary_coverage import assess,save,WORKOUT_REASON

class C10AuxiliaryCoverage(unittest.TestCase):
    def setUp(self):
        G05Tests.setUp(self)

    def test_full_saved_g05_counts_real_fields_and_missing_workouts(self):
        compile_saved(self.root,day=DAY)
        report=save(self.root,DAY)
        self.assertEqual(len(report["per_race"]),12)
        self.assertEqual(report["totals"]["weather"]["observed_with_saved_original"],12)
        self.assertEqual(report["totals"]["horse_body_weight_kg"]["observed_with_saved_original"],48)
        self.assertEqual(report["totals"]["workout"]["observed_with_saved_original"],0)
        self.assertEqual(report["totals"]["workout"]["missing_or_unverified"],48)
        self.assertFalse(report["workout_source_independently_verified"])
        self.assertEqual(report["workout_source_state"],WORKOUT_REASON)
        self.assertFalse(report["prediction_ready"])
        self.assertTrue((self.root/"c10_auxiliary_coverage_receipt.json").is_file())

    def test_tampered_one_original_not_counted_as_observed(self):
        compile_saved(self.root,day=DAY)
        p=self.root/"g03_official_racecard_01.html"
        p.write_bytes(p.read_bytes()+b"tamper")
        report=assess(self.root,DAY)
        self.assertEqual(report["per_race"]["1"]["state"],"RACECARD_AUXILIARY_NOT_VERIFIED")
        self.assertEqual(report["totals"]["weather"]["observed_with_saved_original"],11)
        self.assertFalse(report["workout_source_independently_verified"])

    def test_same_day_independent_track_and_byte_integrity(self):
        capture_kyoto_track(self.root,DAY,lambda url:html(),
            lambda:"2026-11-21T01:01:00Z",allowed=True)
        result=assess(self.root,DAY)
        self.assertTrue(result["g05_kyoto_track_independent_source_original_sha_verified"])
        self.assertEqual(result["g05_kyoto_track_same_day_values"]["weather"],"晴")
        (self.root/"g05_official_kyoto_track.html").write_bytes(b"changed")
        result=assess(self.root,DAY)
        self.assertFalse(result["g05_kyoto_track_independent_source_original_sha_verified"])
        self.assertIsNone(result["g05_kyoto_track_same_day_values"]["weather"])

    def test_stale_track_is_not_promoted(self):
        capture_kyoto_track(self.root,DAY,lambda url:html("20261115"),
            lambda:"2026-11-21T01:01:00Z",allowed=True)
        report=assess(self.root,DAY)
        self.assertFalse(report["g05_kyoto_track_independent_source_original_sha_verified"])
        self.assertIsNone(report["g05_kyoto_track_same_day_values"]["weather"])

    def test_missing_g05_receipt_does_not_claim_coverage(self):
        report=assess(self.root,DAY)
        self.assertFalse(report["g05_saved_receipt_available"])
        self.assertEqual(report["per_race"]["1"]["state"],"RACECARD_AUXILIARY_NOT_VERIFIED")
        self.assertFalse(report["workout_source_independently_verified"])

    def test_receipt_replay_does_not_overwrite(self):
        compile_saved(self.root,day=DAY)
        save(self.root,DAY)
        with self.assertRaisesRegex(ValueError,"already_exists"):
            save(self.root,DAY)

    def test_wrong_day_rejected(self):
        with self.assertRaisesRegex(ValueError,"invalid_day"):
            assess(self.root,"20261123")

if __name__=="__main__":
    unittest.main()
