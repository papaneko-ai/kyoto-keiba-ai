"""P5-02 rank actual P4-02 receipt schema, never turn LAB into live trades."""
import copy
import unittest
from test_p4_source_bound_model_ev_research import SourceBoundMarketResearch
from diagnostics.p4_source_bound_model_ev_research import _hash
from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races,RankingRejected

class SourceBoundRankingTests(unittest.TestCase):
 def setUp(self):
  self.fx=SourceBoundMarketResearch(methodName="test_both_markets_original_bound_same_model_comparison")
  self.fx.setUp()
  self.addCleanup(self.fx.doCleanups)
  self.base=self.fx.audit(probability_error_bound=0.0,odds_drift_fraction=0.0)
 def report(self,race=1,edge=None):
  c=copy.deepcopy(self.base)
  c["race"]=race
  if edge is not None:
   for k in c["markets"]:
    for x in c["markets"][k]["research_model_expected_net"]:
     x["stressed_net_lower"]=edge
     x["expected_net_per_unit"]=edge
  c["comparison_sha256"]=_hash({k:v for k,v in c.items() if k!="comparison_sha256"})
  return c
 def rank(self,reports=None,**kw):
  return rank_lab_research_races([self.report()] if reports is None else reports,
          daily_budget_yen=1000,**kw)
 def test_real_p4_receipt_deterministic_ranking(self):
  a=self.rank()
  self.assertEqual(a,self.rank())
  self.assertEqual(len(a["selected"]),1)
  self.assertEqual(a["selected"][0]["rank"],1)
  self.assertEqual(a["research_spent_yen"],100)
  self.assertEqual(a["unspent_yen"],900)
  self.assertFalse(a["actual_purchase_authorized"])
  self.assertFalse(a["real_paper_trade_recorded"])
 def test_ideal_two_to_three_races_not_forced(self):
  a=self.rank([self.report(2,1.2),self.report(1,2.0),self.report(3,0.8),self.report(4,0.7)])
  self.assertEqual([r["race"] for r in a["selected"]],[1,2,3])
  self.assertEqual([r["rank"] for r in a["selected"]],[1,2,3])
  self.assertEqual(a["research_spent_yen"],300)
 def test_override_four_allowed(self):
  a=self.rank([self.report(i,2.0-i/10) for i in range(1,5)],max_races=4)
  self.assertEqual(len(a["selected"]),4)
 def test_budget_ceiling_not_forced(self):
  a=rank_lab_research_races([self.report(1),self.report(2)],daily_budget_yen=100)
  self.assertEqual(a["research_spent_yen"],100)
  self.assertEqual(a["unspent_yen"],0)
  self.assertEqual(len(a["selected"]),1)
 def test_zero_budget_is_skip(self):
  a=rank_lab_research_races([self.report()],daily_budget_yen=0)
  self.assertEqual(a["selected"],[])
  self.assertEqual(a["research_spent_yen"],0)
 def test_no_positive_stress_means_skip(self):
  a=self.rank([self.report(1,edge=-0.1)])
  self.assertEqual(a["selected"],[])
  self.assertEqual(a["available_positive_ev_races"],0)
 def test_both_ticket_types_independently_calculated(self):
  q=self.rank(ticket_type="QUINELLA")
  b=self.rank(ticket_type="BRACKET")
  self.assertEqual(q["ticket_type"],"QUINELLA")
  self.assertEqual(b["ticket_type"],"BRACKET")
  self.assertNotEqual(q["ranking_sha256"],b["ranking_sha256"])
 def test_p4_digest_tamper_rejected(self):
  c=self.report();c["markets"]["QUINELLA"]["research_model_expected_net"][0]["stressed_net_lower"]=100
  with self.assertRaisesRegex(RankingRejected,"p4_receipt_tampered"):
   self.rank([c])
 def test_duplicate_race_rejected(self):
  with self.assertRaisesRegex(RankingRejected,"duplicate_or_invalid_race"):
   self.rank([self.report(),self.report()])
 def test_fake_live_market_flag_rejected_even_if_digest_recomputed(self):
  c=self.report();c["source_official_origin_authenticated"]=True
  c["comparison_sha256"]=_hash({k:v for k,v in c.items() if k!="comparison_sha256"})
  with self.assertRaisesRegex(RankingRejected,"unauthorized_live_market_claim"):
   self.rank([c])
 def test_negative_budget_rejected(self):
  with self.assertRaisesRegex(RankingRejected,"budget_ceiling_invalid"):
   rank_lab_research_races([self.report()],daily_budget_yen=-100)
 def test_nonfinite_ev_rejected(self):
  c=self.report(edge=float("nan"))
  # JSON canonical validation cannot serialize NaN and must refuse the sample.
  with self.assertRaises(ValueError):
   self.rank([c])
 def test_wrong_market_coverage_rejected(self):
  c=self.report();c["markets"]["BRACKET"]["full_pair_count"]=99
  c["comparison_sha256"]=_hash({k:v for k,v in c.items() if k!="comparison_sha256"})
  with self.assertRaisesRegex(RankingRejected,"market_report_count_mismatch"):
   self.rank([c])
if __name__=="__main__":unittest.main()
