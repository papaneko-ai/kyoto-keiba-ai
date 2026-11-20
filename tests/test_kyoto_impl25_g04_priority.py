"""Isolated no-JRA-HTTP release checks for Nov21 source stage priority."""
import inspect
import unittest
from diagnostics import kyoto_weekend_capture


class G04PriorityTests(unittest.TestCase):
    def test_verified_g03_races_come_before_profile_capture(self):
        source=inspect.getsource(kyoto_weekend_capture.capture)
        self.assertLess(source.index("verify_partial("),source.index("g04=g04_capture("))

    def test_profile_and_conditions_precede_long_market_batch(self):
        source=inspect.getsource(kyoto_weekend_capture.capture)
        places=[source.index(token) for token in (
            "g03=collect_after_observer(",
            "verify_partial(",
            "g04=g04_capture(",
            "g05=compile_saved(",
            "track=capture_kyoto_track(",
            "markets=run_twelve(")]
        self.assertEqual(places,sorted(places))

    def test_unchanged_market_turso_and_seal_boundaries(self):
        source=inspect.getsource(kyoto_weekend_capture.capture)
        for required in ("active_claims_for_weekend(", "claim_context",
                         "bundle_g06(", "g06_shared_claim_evidence",
                         "out[\"g06_twelve_race_market_attempted\"]=True",
                         "g03_independently_verified_races"):
            self.assertIn(required,source)
        seal_source=inspect.getsource(kyoto_weekend_capture.seal)
        self.assertIn("encrypt_evidence(",seal_source)
        self.assertIn("shutil.rmtree(src)",seal_source)

    def test_prestart_cutoff_remains_in_profile_fetcher(self):
        from diagnostics import kyoto_g04_all_horse_profiles
        source=inspect.getsource(kyoto_g04_all_horse_profiles.capture)
        self.assertIn("if before>=cutoff:",source)
        self.assertIn("if after>=cutoff:",source)
        self.assertIn("profile_verified_count",source)

    def test_sp_independence_unchanged(self):
        source=inspect.getsource(kyoto_weekend_capture.capture)
        self.assertIn("capture_verified_sp_seed(",source)
        self.assertIn("race_number=12",source)
        self.assertIn("sp_source_url=\"\"",source)


if __name__ == "__main__":
    unittest.main()
