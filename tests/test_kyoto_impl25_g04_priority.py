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


    def test_runtime_order_g04_failure_does_not_suppress_g06(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        calls = []

        def observer(folder, **kwargs):
            root = Path(folder)
            root.mkdir()
            (root / "receipt.json").write_text('{"state":"TEST_UNVERIFIED"}')
            return {"state": "NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD",
                    "http_requests_started": 0}

        def g04(**kwargs):
            calls.append("G04")
            raise ValueError("synthetic_profile_failure")

        def g05(*args, **kwargs):
            calls.append("G05")
            return {"observed_field_values": 0}

        def track(*args, **kwargs):
            calls.append("TRACK")
            return {"same_day_official_meeting_heading_verified": False}

        def market(*args, **kwargs):
            calls.append("G06")
            return {"verified_dual_market_races": 0,
                    "downstream_intake_created": False}

        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {"KYOTO_TARGET_DAY": "20261121"}
        ), patch(
            "diagnostics.kyoto_nov15_two_original_observer.observe", side_effect=observer
        ), patch(
            "diagnostics.kyoto_g03_weekend_bridge.collect_after_observer",
            return_value={"complete": False, "network_requests_started": 0}
        ), patch(
            "diagnostics.kyoto_g03_independent_partial.verify_partial",
            return_value={"verified_race_numbers": [1], "excluded_races": {}}
        ), patch(
            "diagnostics.kyoto_g04_all_horse_profiles.capture", side_effect=g04
        ), patch(
            "diagnostics.kyoto_g05_conditions.compile_saved", side_effect=g05
        ), patch(
            "diagnostics.kyoto_g05_official_track.capture_kyoto_track", side_effect=track
        ), patch(
            "diagnostics.kyoto_g03_to_g06_input_adapter.records_from_g03",
            return_value={r: ("synthetic" if r == 1 else None) for r in range(1,13)}
        ), patch(
            "diagnostics.kyoto_g06_all12_capture.run_twelve", side_effect=market
        ), patch(
            "diagnostics.kyoto_weekend_remote_claim_runtime.active_claims_for_weekend",
            return_value={"enabled": False}
        ):
            result = kyoto_weekend_capture.capture(
                "20261121", "PC", str(Path(temp) / "source"), live=False,
                opener=object())
        self.assertEqual(calls, ["G04", "G05", "TRACK", "G06"])
        self.assertEqual(result["g04_error_class"], "ValueError")
        self.assertTrue(result["g06_twelve_race_market_attempted"])
        self.assertFalse(result["prediction_ready"])

if __name__ == "__main__":
    unittest.main()
