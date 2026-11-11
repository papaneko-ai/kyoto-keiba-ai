"""P5-03 risk budgeting from independently tested P4/P5 research receipts."""
import copy
import unittest
from test_p5_source_bound_race_ranking_lab import SourceBoundRankingTests
from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races
from diagnostics.p5_bounded_risk_capital_lab import research_capital_control,CapitalRiskRejected
from diagnostics.p5_source_bound_race_ranking_lab import _hash

class CapitalControlTests(unittest.TestCase):
 def setUp(self):
  self.fx=SourceBoundRankingTests(methodName="test_real_p4_receipt_deterministic_ranking")
  self.fx.setUp()
  self.addCleanup(self.fx.doCleanups)
  self.ranking=rank_lab_research_races(
       [self.fx.report(i,edge=1.5-i*0.1) for i in range(1,5)],
       daily_budget_yen=20000,max_races=3,max_tickets_per_race=2)
 def calc(self,**kw):
  return research_capital_control(self.ranking,**kw)
 def test_reproducible_and_not_a_live_prediction(self):
  a=self.calc();b=self.calc()
  self.assertEqual(a,b)
  self.assertFalse(a["real_model_calibrated"])
  self.assertFalse(a["official_market_verified"])
  self.assertFalse(a["real_paper_trade_recorded"])
  self.assertFalse(a["actual_purchase_authorized"])
  self.assertGreater(a["research_spent_yen"],0)
 def test_limits_total_race_pair_and_budget(self):
  a=self.calc()
  self.assertLessEqual(a["research_spent_yen"],a["max_total_exposure_yen"])
  self.assertEqual(a["research_spent_yen"]+a["unused_yen"],20000)
  for race in a["selected"]:
   self.assertLessEqual(race["race_exposure_yen"],a["max_race_exposure_yen"])
   self.assertEqual(race["race_exposure_yen"],sum(x["heuristic_stake_yen"] for x in race["tickets"]))
   for t in race["tickets"]:
    self.assertLessEqual(t["heuristic_stake_yen"],a["max_pair_exposure_yen"])
    self.assertEqual(t["heuristic_stake_yen"]%100,0)
 def test_tighter_caps_never_increase_spending(self):
  wide=self.calc(exposure_fraction=.8,max_race_fraction=.4,max_pair_fraction=.3)
  tight=self.calc(exposure_fraction=.2,max_race_fraction=.1,max_pair_fraction=.05)
  self.assertLessEqual(tight["research_spent_yen"],wide["research_spent_yen"])
 def test_low_stressed_ev_causes_skip(self):
  low=rank_lab_research_races([self.fx.report(1,edge=0.05)],
                              daily_budget_yen=20000)
  a=research_capital_control(low,downside_guard=.10)
  self.assertEqual(a["research_spent_yen"],0)
  self.assertEqual(a["selected"],[])
 def test_zero_budget_safely_skips(self):
  r=rank_lab_research_races([self.fx.report(1,edge=1.1)],daily_budget_yen=0)
  z=research_capital_control(r)
  self.assertEqual(z["research_spent_yen"],0)
  self.assertEqual(z["unused_yen"],0)
 def test_forged_ranking_receipt_rejected(self):
  q=copy.deepcopy(self.ranking)
  q["selected"][0]["tickets"][0]["stressed_net_lower"]=100
  with self.assertRaisesRegex(CapitalRiskRejected,"P5_receipt_sha_mismatch"):
   research_capital_control(q)
 def test_fake_operational_label_rejected_even_if_hash_matches(self):
  q=copy.deepcopy(self.ranking)
  q["actual_purchase_authorized"]=True
  q["ranking_sha256"]=_hash({k:v for k,v in q.items() if k!="ranking_sha256"})
  with self.assertRaisesRegex(CapitalRiskRejected,"research_only_required"):
   research_capital_control(q)
 def test_nonfinite_risk_controls_refused(self):
  for v in (float("nan"),float("inf"),-0.1,1.1):
   with self.assertRaises(CapitalRiskRejected):
    self.calc(exposure_fraction=v)
 def test_invalid_cap_order_refused(self):
  with self.assertRaisesRegex(CapitalRiskRejected,"unordered_exposure_caps"):
   self.calc(exposure_fraction=.1,max_race_fraction=.2)
  with self.assertRaisesRegex(CapitalRiskRejected,"unordered_exposure_caps"):
   self.calc(max_race_fraction=.1,max_pair_fraction=.2)
 def test_no_fractional_yen_or_tiny_positions(self):
  with self.assertRaisesRegex(CapitalRiskRejected,"max_pair_stake_invalid"):
   self.calc(max_pair_stake_yen=150)
 def test_duplicate_race_blocks_spending(self):
  q=copy.deepcopy(self.ranking)
  q["selected"][1]["race"]=q["selected"][0]["race"]
  q["ranking_sha256"]=_hash({k:v for k,v in q.items() if k!="ranking_sha256"})
  with self.assertRaisesRegex(CapitalRiskRejected,"duplicate_selected_race"):
   research_capital_control(q)
 def test_invalid_ticket_pair_blocks_spending(self):
  q=copy.deepcopy(self.ranking)
  q["selected"][0]["tickets"][0]["pair"]=[2,1]
  q["ranking_sha256"]=_hash({k:v for k,v in q.items() if k!="ranking_sha256"})
  with self.assertRaisesRegex(CapitalRiskRejected,"risk_ticket_invalid"):
   research_capital_control(q)
 def test_stake_spend_mismatch_blocks(self):
  q=copy.deepcopy(self.ranking)
  q["research_spent_yen"]+=100
  q["ranking_sha256"]=_hash({k:v for k,v in q.items() if k!="ranking_sha256"})
  with self.assertRaisesRegex(CapitalRiskRejected,"P5_budget_reconciliation_failed"):
   research_capital_control(q)
if __name__=="__main__":unittest.main()
