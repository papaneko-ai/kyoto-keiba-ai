import unittest
from diagnostics.jra_p1_three_complete_races import build
class SourceEvidenceAcceptance(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.status,cls.rows=build()
 def test_complete_three(self):
  self.assertEqual(self.status["completed_races"],[1,2,3])
  self.assertEqual(self.status["completed_race_runner_counts"],{"1":9,"2":15,"3":13})
 def test_total_and_missing(self):
  self.assertEqual(len(self.rows),148)
  self.assertEqual((self.status["profile_details_source_verified"],self.status["detailed_profiles_unqueried"]),(48,100))
 def test_six_exact_batches(self):
  self.assertEqual(len(self.status["source_replay_receipt_sha256"]),6)
  self.assertEqual(self.status["new_profiles_verified_since_baseline"],36)
 def test_never_fake_missing_features(self):
  for x in self.rows:
   self.assertFalse(x["prediction_ready"])
   self.assertFalse(x["training_ready"])
   if x["source_coverage"]["horse_profile"]=="NOT_QUERIED":
    self.assertIsNone(x["performance_features"])
 def test_next_batch(self):
  self.assertEqual(self.status["next_batch"],"batch_07")
  self.assertFalse(self.status["next_batch_automatically_authorized"])
 def test_no_duplicated_horses(self):
  self.assertEqual(len({(x["race_number"],x["horse_number"]) for x in self.rows}),148)
 def test_repeatable(self):
  self.assertEqual(build(),build())
if __name__=="__main__":unittest.main()
