import unittest
from diagnostics.jra_feature_coverage_148 import build
class RealFrozenFeatureAudit(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.summary,cls.rows=build()
 def test_all_148_real_runners(self):
  self.assertEqual(self.summary["runner_count"],148)
  self.assertEqual(len(self.rows),148)
 def test_twelve_actual_races(self):
  self.assertEqual(self.summary["race_count"],12)
  self.assertEqual(len({x["race"] for x in self.rows}),12)
 def test_396_source_prior_dates(self):
  self.assertEqual(self.summary["prior_race_date_records"],396)
 def test_newcomer_no_fake_past(self):
  r=[x for x in self.rows if x["race_number"]==5]
  self.assertTrue(r)
  self.assertTrue(all(x["date_only_features"]["date_records_visible"]==0 for x in r))
 def test_genuine_profile_sample(self):
  self.assertEqual(self.summary["profile_sources_queried"],3)
  self.assertGreaterEqual(self.summary["profile_sources_with_parsed_form"],2)
 def test_missing_not_imputed(self):
  for x in self.rows:
   self.assertFalse(x["prediction_ready"])
   self.assertFalse(x["training_ready"])
   if x["source_coverage"]["horse_profile"]!="VERIFIED_SOURCE_ROWS":
    self.assertIsNone(x["performance_features"])
 def test_source_provenance(self):
  self.assertTrue(all(len(x["racecard_source_sha256"])==64 for x in self.rows))
 def test_determinism(self):
  a,b=build()
  self.assertEqual(a,self.summary)
  self.assertEqual(b,self.rows)
if __name__=="__main__":unittest.main()
