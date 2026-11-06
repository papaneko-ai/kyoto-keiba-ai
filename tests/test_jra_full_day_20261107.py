"""Independent CI gate for a full Kyoto 2026-11-07 pre-race day; no JRA network."""
import json,unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"docs"/"diagnostics"
EIGHT=(2,3,4,5,8,9,10,11)
def row(r):
 if r==7:p=ROOT/"JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json"
 elif r in (1,6,12):p=ROOT/"multirace_20261106"/f"kyoto_{r:02d}_snapshot.json"
 else:p=ROOT/"remaining8_20261106"/f"kyoto_{r:02d}_snapshot.json"
 return json.loads(p.read_text(encoding="utf8"))
class FullDay(unittest.TestCase):
 def test_all_twelve_present(self):
  self.assertEqual([row(r)["race_number"] for r in range(1,13)],list(range(1,13)))
 def test_all_complete_unique(self):
  for race in range(1,13):
   d=row(race);horses=d["runners"]
   self.assertTrue(horses)
   self.assertEqual(d["runner_count"],len(horses))
   self.assertEqual([x["horse_number"] for x in horses],list(range(1,len(horses)+1)))
   self.assertEqual(len({x["horse_name"] for x in horses}),len(horses))
   self.assertEqual(len({x["horse_profile_href"] for x in horses}),len(horses))
 def test_all_prior_dates_belong_to_past(self):
  for race in range(1,13):
   d=row(race)
   for h in d["runners"]:
    for dt in h.get("prior_race_dates",h.get("past_race_dates",[])):
     self.assertLess(dt,"2026-11-07")
 def test_no_errors_or_post_off_captures(self):
  limit=datetime.fromisoformat("2026-11-07T01:05:00+00:00")
  for race in range(1,13):
   d=row(race)
   self.assertEqual(d.get("errors",d.get("parse_errors",[])),[])
   timestamp=d.get("fetched_at_utc",d.get("captured_at_utc"))
   self.assertLess(datetime.fromisoformat(timestamp).astimezone(timezone.utc),limit)
   self.assertEqual(len(d.get("source_sha256",d.get("sha256",""))),64)
 def test_no_training_promotion(self):
  for race in range(1,13):
   d=row(race)
   self.assertFalse(d.get("ready_for_training",d.get("training_ready")))
   self.assertFalse(d.get("ready_for_prediction",d.get("prediction_ready")))
 def test_new_horse_race_zero_history(self):
  self.assertEqual(sum(len(x.get("past_race_dates",[])) for x in row(6)["runners"]),0)
if __name__=="__main__":unittest.main()
