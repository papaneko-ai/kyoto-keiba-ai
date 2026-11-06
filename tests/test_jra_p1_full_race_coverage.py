import unittest
from diagnostics.jra_p1_full_race_coverage import build
class FullRaceCoverage(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.summary,cls.rows=build()
 def test_full_first_two_races(self):
  self.assertEqual(self.summary["completed_races"],[1,2])
  self.assertEqual(self.summary["completed_race_runner_counts"],{"1":9,"2":15})
 def test_all_four_batches_exactly_once(self):
  self.assertEqual(self.summary["completed_batches"],["batch_01","batch_02","batch_03","batch_04"])
  self.assertEqual(self.summary["new_profiles_verified_since_baseline"],24)
 def test_all_148_unchanged(self):
  self.assertEqual(len(self.rows),148)
  self.assertEqual(len({(x["race_number"],x["horse_number"]) for x in self.rows}),148)
 def test_36_and_112_and_no_future(self):
  self.assertEqual(self.summary["profile_details_source_verified"],36)
  self.assertEqual(self.summary["detailed_profiles_unqueried"],112)
  self.assertFalse(self.summary["prediction_ready"])
 def test_provenance(self):
  self.assertEqual(len(self.summary["source_replay_receipt_sha256"]),4)
  self.assertTrue(all(len(x)==64 for x in self.summary["source_replay_receipt_sha256"].values()))
 def test_feature_gaps_not_invented(self):
  self.assertEqual(sum(x["source_coverage"]["horse_profile"]=="NOT_QUERIED" for x in self.rows),112)
  self.assertTrue(all(x["performance_features"] is None for x in self.rows if x["source_coverage"]["horse_profile"]=="NOT_QUERIED"))
 def test_race3_is_not_complete(self):
  self.assertTrue(any(x["source_coverage"]["horse_profile"]=="NOT_QUERIED" for x in self.rows if x["race_number"]==3))
 def test_deterministic(self):
  self.assertEqual(build(),build())
if __name__=="__main__":unittest.main()
