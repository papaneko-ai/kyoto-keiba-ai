import unittest
from diagnostics.jra_p1_four_complete_races import build
class FourCompleteRaces(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.summary,cls.rows=build()
 def test_four_complete(self):
  self.assertEqual(self.summary["completed_races"],[1,2,3,4])
  self.assertEqual(self.summary["completed_race_runner_counts"],{"1":9,"2":15,"3":13,"4":15})
 def test_totals(self):
  self.assertEqual(len(self.rows),148)
  self.assertEqual(self.summary["profile_details_source_verified"],60)
  self.assertEqual(self.summary["detailed_profiles_unqueried"],88)
 def test_eight_replayed_batches(self):
  self.assertEqual(self.summary["completed_batches"],[f"batch_{i:02d}" for i in range(1,9)])
  self.assertEqual(len(self.summary["source_replay_receipt_sha256"]),8)
 def test_source_sha_and_no_future_data_imputation(self):
  self.assertEqual(len({(r["race_number"],r["horse_number"]) for r in self.rows}),148)
  for r in self.rows:
   self.assertFalse(r["prediction_ready"])
   self.assertFalse(r["training_ready"])
   if r["source_coverage"]["horse_profile"]=="NOT_QUERIED":
    self.assertIsNone(r["performance_features"])
 def test_next_batch_unapproved(self):
  self.assertEqual(self.summary["next_batch"],"batch_09")
  self.assertFalse(self.summary["next_batch_automatically_authorized"])
 def test_repeatable(self):
  self.assertEqual(build(),build())
if __name__=="__main__":unittest.main()
