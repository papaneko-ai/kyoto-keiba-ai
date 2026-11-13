"""R10 fixed acceptance: 3 existing-P5 risk policies on one sealed P4/P5 LAB day."""
import copy,unittest
import test_p5_source_bound_race_ranking_lab as src
from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races,_hash
from diagnostics.p5_r10_risk_strategy_comparison import (
    compare_risk_strategies,StrategyComparisonRejected,PROFILES)

class R10RiskStrategyAcceptance(unittest.TestCase):
 def setUp(self):
  f=src.SourceBoundRankingTests(methodName="test_real_p4_receipt_deterministic_ranking")
  f.setUp();self.addCleanup(f.doCleanups);self.fx=f
  self.ranking=rank_lab_research_races(
      [f.report(i,edge=1.5-.1*i) for i in range(1,5)],
      daily_budget_yen=20000,max_races=3,max_tickets_per_race=2)
 def audit(self,**kw):return compare_risk_strategies(self.ranking,**kw)
 def reject(self,msg,**kw):
  with self.assertRaisesRegex(StrategyComparisonRejected,msg):self.audit(**kw)
 def test_three_fixed_distinct_profiles(self):
  r=self.audit();self.assertEqual([x["strategy"] for x in r["profiles"]],list(PROFILES))
 def test_strategy_ordered_stakes(self):
  p=self.audit()["profiles"];self.assertLessEqual(p[0]["stake_yen"],p[1]["stake_yen"]);self.assertLessEqual(p[1]["stake_yen"],p[2]["stake_yen"])
 def test_strategies_not_all_identical(self):self.assertGreater(len({p["stake_yen"] for p in self.audit()["profiles"]}),1)
 def test_total_stake_under_budget(self):
  for p in self.audit()["profiles"]:self.assertLessEqual(p["stake_yen"],20000)
 def test_race_and_pair_concentration_bounded(self):
  for p in self.audit()["profiles"]:
   rules=PROFILES[p["strategy"]]
   self.assertLessEqual(p["max_race_exposure_yen"],20000*rules["max_race_fraction"])
   self.assertLessEqual(p["max_pair_exposure_yen"],min(20000*rules["max_pair_fraction"],rules["max_pair_stake_yen"]))
 def test_exposure_total_bounded(self):
  for p in self.audit()["profiles"]:
   self.assertLessEqual(p["stake_yen"],20000*PROFILES[p["strategy"]]["exposure_fraction"])
 def test_all_stakes_100_yen(self):self.assertTrue(all(x["risk_budget_100_yen_aligned"] for x in self.audit()["profiles"]))
 def test_unspent_and_spent_reconcile(self):self.assertTrue(all(x["unspent_yen"]+x["stake_yen"]==20000 for x in self.audit()["profiles"]))
 def test_worst_loss_never_understates_full_stake(self):
  for x in self.audit()["profiles"]:self.assertEqual(x["worst_case_loss_yen"],x["stake_yen"])
 def test_probability_error_worsens_stress(self):
  a=self.audit(probability_error=0)["profiles"];b=self.audit(probability_error=.5)["profiles"]
  for x,y in zip(a,b):self.assertLessEqual(y["scenario_expected_net_yen"],x["scenario_expected_net_yen"])
 def test_odds_shock_worsens_stress(self):
  a=self.audit(odds_downshift=0)["profiles"];b=self.audit(odds_downshift=.5)["profiles"]
  for x,y in zip(a,b):self.assertLessEqual(y["scenario_expected_net_yen"],x["scenario_expected_net_yen"])
 def test_baseline_same_rank_with_scenario_haircuts(self):
  self.assertEqual([x["stake_yen"] for x in self.audit(probability_error=0)["profiles"]],
                   [x["stake_yen"] for x in self.audit(probability_error=.5)["profiles"]])
 def test_replay_determinism(self):self.assertEqual(self.audit(),self.audit())
 def test_tampering_stake_sha_rejected(self):
  self.ranking["selected"][0]["tickets"][0]["stake_yen"]+=100
  self.reject("sealed_ranking_rejected")
 def test_fake_live_authorization_rejected(self):
  self.ranking["actual_purchase_authorized"]=True
  self.ranking["ranking_sha256"]=_hash({k:v for k,v in self.ranking.items() if k!="ranking_sha256"})
  self.reject("sealed_ranking_rejected")
 def test_invalid_prob_error_rejected(self):
  for val in (-.1,1,float('nan'),True):self.reject("invalid_stress",probability_error=val)
 def test_invalid_odds_drop_rejected(self):
  for val in (-.1,1,float('inf'),True):self.reject("invalid_stress",odds_downshift=val)
 def test_invalid_loss_ceiling_rejected(self):
  for val in (-1,150,True):self.reject("invalid_loss_ceiling",maximum_loss_yen=val)
 def test_loss_ceiling_flags_rather_than_forges_stakes(self):
  a=self.audit(maximum_loss_yen=100)
  self.assertTrue(any(not x["loss_ceiling_satisfied"] for x in a["profiles"]))
  self.assertEqual([x["stake_yen"] for x in a["profiles"]],[x["stake_yen"] for x in self.audit()["profiles"]])
 def test_zero_budget_results_safe_skip(self):
  self.ranking=rank_lab_research_races([self.fx.report(1,edge=1.1)],daily_budget_yen=0)
  r=self.audit();self.assertEqual([x["stake_yen"] for x in r["profiles"]],[0,0,0]);self.assertEqual(r["minimum_loss_strategy"],"BALANCED")
 def test_zero_loss_ceiling_marks_nonzero_infeasible(self):
  self.assertTrue(all(not r["loss_ceiling_satisfied"] for r in self.audit(maximum_loss_yen=0)["profiles"]))
 def test_models_never_claim_real_returns(self):
  r=self.audit()
  for key in ("all_scenarios_profitable_claimed","real_probability_calibrated","real_market_verified","real_paper_trade_recorded","actual_purchase_authorized"):
   self.assertFalse(r[key])
  self.assertEqual(r["network_requests"],0)
 def test_source_digest_propagation(self):self.assertEqual(self.audit()["source_ranking_sha256"],self.ranking["ranking_sha256"])
 def test_risk_receipts_not_identical(self):self.assertEqual(len({r["receipt_sha256"] for r in self.audit()["profiles"]}),3)
