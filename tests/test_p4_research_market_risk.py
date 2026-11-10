import copy,unittest
from diagnostics.p4_research_market_risk import audit_market_risk,RiskRejected

P={(1,2):0.7,(1,3):0.2,(2,3):0.1}
O={(1,2):2.0,(1,3):5.0,(2,3):10.0}
class MarketRiskTests(unittest.TestCase):
 def test_stress_is_monotone_and_never_recommends_bet(self):
  base=audit_market_risk(P,O,probability_error_bound=0,odds_drift_fraction=0)
  stressed=audit_market_risk(P,O,probability_error_bound=0.05,odds_drift_fraction=0.2)
  self.assertEqual(base["stress_survivors"],1)
  self.assertTrue(all(b["stressed_expected_net_lower"]<=a["stressed_expected_net_lower"]
                      for a,b in zip(base["pairs"],stressed["pairs"])))
  self.assertEqual(stressed["stake_recommendation_yen"],0)
  self.assertFalse(stressed["live_prediction_ready"])
  self.assertFalse(stressed["real_operational_score_eligible"])
  self.assertEqual(stressed,audit_market_risk(P,O,probability_error_bound=0.05,odds_drift_fraction=0.2))
 def test_full_market_required_and_no_mutation(self):
  p=copy.deepcopy(P);o=copy.deepcopy(O)
  audit_market_risk(P,O,probability_error_bound=0.1,odds_drift_fraction=0.1)
  self.assertEqual(p,P);self.assertEqual(o,O)
  with self.assertRaisesRegex(RiskRejected,"market_coverage_mismatch"):
   audit_market_risk(P,{(1,2):2.0},probability_error_bound=0,odds_drift_fraction=0)
 def test_invalid_inputs_fail_closed(self):
  for kwargs in ({"probability_error_bound":-0.1,"odds_drift_fraction":0},
                 {"probability_error_bound":0,"odds_drift_fraction":1},
                 {"probability_error_bound":float("nan"),"odds_drift_fraction":0},
                 {"probability_error_bound":0,"odds_drift_fraction":0,"maximum_exposure_fraction":1}):
   with self.assertRaises(RiskRejected):audit_market_risk(P,O,**kwargs)
  with self.assertRaises(RiskRejected):
   audit_market_risk({(1,2):0.7,(1,3):0.2,(2,3):0.2},O,probability_error_bound=0,odds_drift_fraction=0)
 def test_shock_can_reject_nominally_positive_edge(self):
  p={(1,2):0.51,(1,3):0.29,(2,3):0.2}
  o={(1,2):2.1,(1,3):3.5,(2,3):5.0}
  r=audit_market_risk(p,o,probability_error_bound=0.1,odds_drift_fraction=0.1)
  self.assertGreater(r["pairs"][0]["model_expected_net"],0)
  self.assertLess(r["pairs"][0]["stressed_expected_net_lower"],0)
  self.assertFalse(r["pairs"][0]["passes_stress_gate"])
if __name__=="__main__":unittest.main()
