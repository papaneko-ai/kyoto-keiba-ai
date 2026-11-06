import copy,json,unittest
from diagnostics.jra_benchmark_acceptance import audit_report,REPORT,_read
class TestRealJRAComparison(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.report=_read(REPORT)
 def test_five_real_races_pass(self):
  x=audit_report(self.report)
  self.assertTrue(x["parity_passed_for_all_five"])
  self.assertEqual(len(x["sampled_races"]),5)
 def test_bytes_observed(self):
  x=audit_report(self.report)
  self.assertGreater(x["sp_bytes_reduction_pct"],30)
  self.assertLess(x["sp_bytes_reduction_pct"],50)
 def test_end_to_end_sp_better_in_sample(self):
  x=audit_report(self.report)
  self.assertGreater(x["sp_end_to_end_gain_pct"],15)
  self.assertEqual(x["sp_faster_race_count"],4)
 def test_router_candidate_not_production(self):
  x=audit_report(self.report)
  self.assertEqual(x["router_state"],"CANDIDATE")
  self.assertEqual(x["router_candidate"],"SP")
  self.assertFalse(x["safety"]["production_switch_performed"])
  self.assertFalse(x["safety"]["training_ready"])
 def test_invalid_roster_blocks(self):
  d=copy.deepcopy(self.report);d["races"][0]["sp_snapshot_match"]=False
  with self.assertRaises(ValueError):audit_report(d)
 def test_invalid_speed_does_not_validate(self):
  d=copy.deepcopy(self.report);d["races"][0]["sp"]["network_ms"]=-1
  d["races"][0]["sp"]["parse_ms"]=0
  with self.assertRaises(ValueError):audit_report(d)
 def test_mismatch_counters_block(self):
  d=copy.deepcopy(self.report);d["pc_total_bytes"]+=1
  with self.assertRaises(ValueError):audit_report(d)
 def test_determinism(self):
  self.assertEqual(audit_report(self.report),audit_report(self.report))
if __name__=="__main__":unittest.main()
