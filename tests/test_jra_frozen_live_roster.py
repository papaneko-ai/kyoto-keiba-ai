"""Regression for frozen JRA official upcoming racecard; no network or live DB writes."""
import unittest,json
from datetime import datetime,timezone
from pathlib import Path
FILE=Path(__file__).resolve().parents[1]/"docs/diagnostics/JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json"
class FrozenRacecard(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.d=json.loads(FILE.read_text(encoding="utf8"))
 def test_source_capture_hash(self):
  self.assertEqual(len(self.d["source_sha256"]),64)
  self.assertTrue(self.d["raw_capture_verified"])
 def test_all_eleven(self):
  self.assertEqual(self.d["runner_count"],11)
  self.assertEqual([r["horse_number"] for r in self.d["runners"]],list(range(1,12)))
 def test_unique_names_and_links(self):
  rows=self.d["runners"]
  self.assertEqual(len({r["horse_name"] for r in rows}),11)
  self.assertEqual(len({r["horse_profile_href"] for r in rows}),11)
 def test_eight_frames_valid(self):
  frames=[r["frame_number"] for r in self.d["runners"]]
  self.assertTrue(all(type(x) is int and 1<=x<=8 for x in frames))
  self.assertEqual(frames,sorted(frames))
 def test_forty_four_past_race_dates(self):
  dates=[date for r in self.d["runners"] for date in r["prior_race_dates"]]
  self.assertEqual(len(dates),44)
  self.assertTrue(all(d<'2026-11-07' for d in dates))
 def test_capture_before_event(self):
  ts=datetime.fromisoformat(self.d["fetched_at_utc"])
  self.assertLess(ts,datetime(2026,11,7,4,25,tzinfo=timezone.utc))
 def test_fail_closed_training(self):
  self.assertFalse(self.d["ready_for_prediction"])
  self.assertFalse(self.d["ready_for_training"])
  self.assertFalse(self.d["official_permanent_ids_verified"])
 def test_zero_parse_errors(self):
  self.assertEqual(self.d["errors"],[])
  self.assertTrue(self.d["racecard_horse_rows_verified"])
if __name__=="__main__":unittest.main()
