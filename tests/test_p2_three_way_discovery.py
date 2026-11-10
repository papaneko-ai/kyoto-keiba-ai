import copy,unittest
from diagnostics.p2_three_way_discovery import discover_interactions,DiscoveryRejected

def fixtures():
 out=[]
 for i in range(12):
  horses=[]
  for n in (1,2,3):
   # train favors horse 1, validation/holdout horse 2;
   # feature A deliberately overfits training.
   horses.append({"number":n,"features":{
    "form":0.9 if n==1 else 0.2,
    "pace":0.8 if n==1 else 0.3,
    "track":0.7 if n==1 else 0.4}})
  out.append({"race_id":f"LAB-{i}","cutoff_utc":f"2026-10-{i+1:02d}T04:00:00Z",
              "pre_result_frozen":True,"horses":horses,
              "winner":1 if i<4 else 2})
 return out

class ThreeWayTests(unittest.TestCase):
 def test_discovery_and_independent_refutation(self):
  x=discover_interactions(fixtures(),train_count=4,selection_count=3)
  self.assertEqual(x["candidate_family_size"],6)
  self.assertEqual(len(x["race_ids"]["training"]),4)
  self.assertEqual(len(x["race_ids"]["validation"]),4)
  self.assertEqual(len(x["race_ids"]["untouched_holdout"]),4)
  self.assertEqual(len(x["selected"]),3)
  self.assertTrue(all(c["refuted"] for c in x["selected"]))
  self.assertTrue(all(not c["deployable"] for c in x["selected"]))
  self.assertFalse(x["future_labels_used_for_selection"])
  self.assertFalse(x["official_pre_result_receipts_verified"])
  self.assertEqual(x,discover_interactions(fixtures(),train_count=4,selection_count=3))
 def test_future_labels_cannot_change_selected_features(self):
  rows=fixtures();before=discover_interactions(rows,train_count=4)
  for r in rows[4:]:r["winner"]=1
  after=discover_interactions(rows,train_count=4)
  self.assertEqual([x["features"] for x in before["selected"]],
                   [x["features"] for x in after["selected"]])
  self.assertEqual([x["training"] for x in before["selected"]],
                   [x["training"] for x in after["selected"]])
  self.assertNotEqual([x["untouched_holdout"] for x in before["selected"]],
                      [x["untouched_holdout"] for x in after["selected"]])
 def test_training_labels_change_training_stats(self):
  rows=fixtures();a=discover_interactions(rows,train_count=4)
  rows[0]["winner"]=2
  b=discover_interactions(rows,train_count=4)
  self.assertNotEqual([x["training"] for x in a["selected"]],
                      [x["training"] for x in b["selected"]])
 def test_reject_unfrozen(self):
  rows=fixtures();rows[1]["pre_result_frozen"]=False
  with self.assertRaisesRegex(DiscoveryRejected,"unfrozen_pre_result_features"):
   discover_interactions(rows,train_count=4)
 def test_reject_time_reverse(self):
  rows=fixtures();rows[1],rows[2]=rows[2],rows[1]
  with self.assertRaisesRegex(DiscoveryRejected,"time_not_strictly_increasing"):
   discover_interactions(rows,train_count=4)
 def test_reject_duplicate_race(self):
  rows=fixtures();rows[1]["race_id"]=rows[0]["race_id"]
  with self.assertRaisesRegex(DiscoveryRejected,"duplicate_race_id"):
   discover_interactions(rows,train_count=4)
 def test_reject_future_label_feature(self):
  rows=fixtures();rows[0]["horses"][0]["features"]["winner"]=1
  with self.assertRaisesRegex(DiscoveryRejected,"forbidden_or_missing_feature"):
   discover_interactions(rows,train_count=4)
 def test_reject_feature_drift(self):
  rows=fixtures();del rows[0]["horses"][0]["features"]["form"]
  with self.assertRaisesRegex(DiscoveryRejected,"feature_schema_drift"):
   discover_interactions(rows,train_count=4)
 def test_reject_nan(self):
  rows=fixtures();rows[0]["horses"][0]["features"]["form"]=float("nan")
  with self.assertRaisesRegex(DiscoveryRejected,"nonfinite_or_future_feature"):
   discover_interactions(rows,train_count=4)
 def test_reject_duplicate_horse(self):
  rows=fixtures();rows[0]["horses"][1]["number"]=1
  with self.assertRaisesRegex(DiscoveryRejected,"horse_number_invalid"):
   discover_interactions(rows,train_count=4)
 def test_reject_insufficient_independent_windows(self):
  for n in (0,2,7,12):
   with self.subTest(n=n):
    with self.assertRaisesRegex(DiscoveryRejected,"independent_three_way_split_required"):
     discover_interactions(fixtures(),train_count=n)
 def test_reject_winner_not_present(self):
  rows=fixtures();rows[0]["winner"]=7
  with self.assertRaisesRegex(DiscoveryRejected,"winner_missing"):
   discover_interactions(rows,train_count=4)
 def test_family_size_and_correction(self):
  r=discover_interactions(fixtures(),train_count=4)
  self.assertAlmostEqual(r["bonferroni_alpha"],0.05/6)
  self.assertFalse(r["auto_promote"])
  self.assertFalse(r["real_bet_authorized"])

if __name__=="__main__":unittest.main()
