"""Frozen 2026-11-07 Kyoto four-race source regression, using real structured receipts."""
import json,unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"docs"/"diagnostics"
COUNTS={1:9,6:11,7:11,12:17}
HISTORY={1:14,6:0,7:44,12:68}
def snap(n):
 p=ROOT/"JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json" if n==7 else ROOT/"multirace_20261106"/f"kyoto_{n:02d}_snapshot.json"
 return json.loads(p.read_text(encoding="utf8"))
class FourRaceRealSnapshot(unittest.TestCase):
 def test_four_race_counts(self):
  self.assertEqual({n:snap(n)["runner_count"] for n in COUNTS},COUNTS)
  self.assertEqual(sum(COUNTS.values()),48)
 def test_actual_prior_date_counts(self):
  for n in COUNTS:
   d=snap(n);runs=sum(len(x.get("prior_race_dates",x.get("past_race_dates",[]))) for x in d["runners"])
   self.assertEqual(runs,HISTORY[n])
  self.assertEqual(sum(HISTORY.values()),126)
 def test_all_pre_race(self):
  before=datetime.fromisoformat("2026-11-07T01:05:00+00:00")
  for n in COUNTS:
   d=snap(n);when=d["fetched_at_utc"] if n==7 else d["captured_at_utc"]
   self.assertLess(datetime.fromisoformat(when).astimezone(timezone.utc),before)
   self.assertEqual(len(d["source_sha256"]),64)
 def test_unique_numbers_names_links(self):
  for n in COUNTS:
   rows=snap(n)["runners"]
   self.assertEqual([r["horse_number"] for r in rows],list(range(1,len(rows)+1)))
   for k in ("horse_name","horse_profile_href"):
    self.assertEqual(len({x[k] for x in rows}),len(rows))
 def test_no_parse_errors(self):
  for n in COUNTS:
   d=snap(n)
   self.assertEqual(d["errors"] if n==7 else d["parse_errors"],[])
 def test_correctly_empty_new_race_histories(self):self.assertEqual(snap(6)["prior_date_count"],0)
 def test_no_prediction_or_training_promotion(self):
  for n in COUNTS:
   d=snap(n)
   self.assertFalse(d["ready_for_prediction"] if n==7 else d["prediction_ready"])
   self.assertFalse(d["ready_for_training"] if n==7 else d["training_ready"])
if __name__=="__main__":unittest.main()
