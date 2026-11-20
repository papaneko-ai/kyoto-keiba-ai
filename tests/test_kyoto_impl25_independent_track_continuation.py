"""Actual mocked capture control-flow tests; zero JRA HTTP and zero Turso writes."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import capture


class IndependentTrackContinuationTests(unittest.TestCase):
    def test_g03_exception_cannot_suppress_independent_track_original(self):
        calls=[]
        def observe(folder, **kwargs):
            Path(folder).mkdir()
            (Path(folder)/"receipt.json").write_text(json.dumps(
                {"day":"20261121","state":"SYNTHETIC_UNVERIFIED"}))
            (Path(folder)/"official_meeting.html").write_bytes(b"synthetic")
            return {"state":"NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD",
                    "http_requests_started":1,"selection_sha256":None}
        def track(folder, **kwargs):
            calls.append("G05_TRACK")
            (Path(folder)/"g05_official_kyoto_track.html").write_bytes(b"synthetic track")
            (Path(folder)/"g05_track_receipt.json").write_text(
                '{"day":"20261121","state":"SYNTHETIC_NOT_AUTHENTICATED"}')
            return {"same_day_official_meeting_heading_verified":False}
        with tempfile.TemporaryDirectory() as d,patch.dict(
            os.environ,{"KYOTO_TARGET_DAY":"20261121"}
        ),patch(
            "diagnostics.kyoto_nov15_two_original_observer.observe",side_effect=observe
        ),patch(
            "diagnostics.kyoto_g03_weekend_bridge.collect_after_observer",
            side_effect=ValueError("synthetic_link_failure")
        ),patch(
            "diagnostics.kyoto_g03_independent_partial.verify_partial",
            side_effect=ValueError("no_valid_g03")
        ),patch(
            "diagnostics.kyoto_g05_official_track.capture_kyoto_track",side_effect=track
        ),patch(
            "diagnostics.kyoto_g03_to_g06_input_adapter.records_from_g03",
            return_value={i:None for i in range(1,13)}
        ):
            root=Path(d)/"source"
            result=capture("20261121","PC",str(root),live=False,opener=object())
            self.assertEqual(calls,["G05_TRACK"])
            self.assertEqual(result["g03_capture_state"],"G03_EXCEPTION_PRESERVE_OTHER_SOURCES")
            self.assertTrue(result["g05_kyoto_track_source_saved"])
            self.assertFalse(result["g05_same_day_track_heading_verified"])
            self.assertFalse(result["prediction_ready"])
            self.assertEqual((root/"g05_official_kyoto_track.html").read_bytes(),
                             b"synthetic track")
            self.assertTrue((root/"official_meeting.html").is_file())

    def test_track_source_is_not_promoted_without_same_day_heading(self):
        from diagnostics.kyoto_g05_official_track import parse_kyoto_track, KYOTO_TRACK_PAGE
        raw=b"<html><h2>Unverified publication</h2></html>"
        record=parse_kyoto_track(raw,"20261121",KYOTO_TRACK_PAGE,
                                 "2026-11-21T00:15:00+00:00")
        self.assertFalse(record["same_day_official_meeting_heading_verified"])
        self.assertIsNone(record["weather"])
        self.assertFalse(record["prediction_ready"])


if __name__ == "__main__":
    unittest.main()
