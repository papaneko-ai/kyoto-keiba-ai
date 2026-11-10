import copy
import unittest
from diagnostics.p7_evo_candidate_falsification import (
 discover_and_refute,EvolutionRejected,EVO_RULES)

def fixtures():
 rows=[]
 for i in range(10):
  runners=[]
  for n in (1,2,3):
   features={name: (0.9 if n==1 else 0.2 if n==2 else 0.1)
             for name,_ in EVO_RULES.values()}
   runners.append({"horse_number":n,"features":features})
  rows.append({"race_id":f"SYNTHETIC-{i}","cutoff_utc":f"2026-10-{i+1:02d}T05:00:00Z",
               "pre_result_frozen":True,"runners":runners,
               "winner":1 if i<5 else 2})
 return rows

class EightEvoTests(unittest.TestCase):
 def test_eight_candidates_falsified_on_holdout(self):
  result=discover_and_refute(fixtures(),train_count=5)
  self.assertEqual(result["candidate_count"],8)
  self.assertEqual(result["candidate_ids"],list(EVO_RULES))
  self.assertEqual(len(result["candidates"]),8)
  self.assertTrue(all(c["training"]["hits"]==5 for c in result["candidates"]))
  self.assertTrue(all(c["unseen_holdout"]["hits"]==0 for c in result["candidates"]))
  self.assertTrue(all(c["verdict"]=="REFUTED_OR_INSUFFICIENT" for c in result["candidates"]))
  self.assertFalse(result["auto_promote"])
  self.assertFalse(result["prediction_ready"])
  self.assertEqual(result,discover_and_refute(fixtures(),train_count=5))
 def test_holdout_labels_do_not_change_training_or_candidate_family(self):
  rows=fixtures();a=discover_and_refute(rows,train_count=5)
  for r in rows[5:]:r["winner"]=1
  b=discover_and_refute(rows,train_count=5)
  self.assertEqual(a["candidate_ids"],b["candidate_ids"])
  self.assertEqual([x["training"] for x in a["candidates"]],
                   [x["training"] for x in b["candidates"]])
  self.assertNotEqual([x["unseen_holdout"] for x in a["candidates"]],
                      [x["unseen_holdout"] for x in b["candidates"]])
  self.assertTrue(all(not x["deployable"] for x in b["candidates"]))
 def test_refuse_unfrozen(self):
  rows=fixtures();rows[3]["pre_result_frozen"]=False
  with self.assertRaisesRegex(EvolutionRejected,"unfrozen_prediction_features"):
   discover_and_refute(rows,train_count=5)
 def test_refuse_time_shuffle(self):
  rows=fixtures();rows[2],rows[3]=rows[3],rows[2]
  with self.assertRaisesRegex(EvolutionRejected,"chronological_order_invalid"):
   discover_and_refute(rows,train_count=5)
 def test_refuse_duplicate_race(self):
  rows=fixtures();rows[1]["race_id"]=rows[0]["race_id"]
  with self.assertRaisesRegex(EvolutionRejected,"duplicate_race_id"):
   discover_and_refute(rows,train_count=5)
 def test_refuse_duplicate_horse(self):
  rows=fixtures();rows[1]["runners"][1]["horse_number"]=1
  with self.assertRaisesRegex(EvolutionRejected,"horse_number_invalid"):
   discover_and_refute(rows,train_count=5)
 def test_refuse_future_or_missing_feature(self):
  for key,value in (("recent_form",float("nan")),("speed_index",2.0)):
   rows=fixtures();rows[1]["runners"][0]["features"][key]=value
   with self.assertRaisesRegex(EvolutionRejected,"feature_out_of_range"):
    discover_and_refute(rows,train_count=5)
  rows=fixtures();del rows[1]["runners"][0]["features"]["pace_fit"]
  with self.assertRaisesRegex(EvolutionRejected,"feature_set_incomplete"):
   discover_and_refute(rows,train_count=5)
 def test_refuse_insufficient_holdout(self):
  with self.assertRaisesRegex(EvolutionRejected,"train_holdout_minimum_three_each"):
   discover_and_refute(fixtures(),train_count=8)
 def test_refuse_winner_missing(self):
  rows=fixtures();rows[0]["winner"]=7
  with self.assertRaisesRegex(EvolutionRejected,"winner_missing"):
   discover_and_refute(rows,train_count=5)

if __name__=="__main__":unittest.main()
