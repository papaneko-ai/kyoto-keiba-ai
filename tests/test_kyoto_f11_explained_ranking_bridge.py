"""F11->F12 source-bound integration and exception tests.

Use the repo's existing P4 synthetic-original test factory, never real JRA,
old public app, deployed Turso or actual purchase.
"""
import copy,unittest
from test_p5_source_bound_race_ranking_lab import SourceBoundRankingTests
from diagnostics.kyoto_f11_explained_ranking_bridge import (
    rank_f11,handoff_f11_to_f12,F11Rejected,digest
)
from diagnostics.kyoto_f12_ticket_budget_planner import F12Rejected
from diagnostics.p5_source_bound_race_ranking_lab import RankingRejected

class F11ExplainedRankAcceptance(unittest.TestCase):
 def setUp(self):
  self.fixture=SourceBoundRankingTests(methodName="test_real_p4_receipt_deterministic_ranking")
  self.fixture.setUp()
  self.addCleanup(self.fixture.doCleanups)
 def comparisons(self):
  return [self.fixture.report(1,1.2),self.fixture.report(2,0.9),
          self.fixture.report(3,0.5),self.fixture.report(4,-0.2)]
 def run_ranking(self,comparisons=None,**kw):
  rows=self.comparisons() if comparisons is None else comparisons
  inp=dict(comparisons=rows,day_budget_yen=10000,ticket_type="QUINELLA",
           observed_utc="2026-11-14T03:00:00Z",
           cutoff_utc="2026-11-14T03:05:00Z",
           confidence_by_race={r["race"]:0.75 for r in rows})
  inp.update(kw)
  return rank_f11(**inp)
 def test_lab_p4_four_races_to_three_ranked_explained(self):
  a=self.run_ranking()
  self.assertEqual(a,self.run_ranking())
  self.assertEqual([r["race"] for r in a["selected"]],[1,2,3])
  self.assertEqual([r["rank"] for r in a["selected"]],[1,2,3])
  for item in a["selected"]:
   self.assertEqual(item["source_age_seconds"],300)
   self.assertIn("expectation",item["explanation"])
   self.assertIn("confidence",item["explanation"])
   self.assertIn("freshness",item["explanation"])
   self.assertTrue(1<=len(item["tickets"])<=2)
  self.assertFalse(a["source_jra_authenticated"])
 def test_ranking_to_F12_auto_budget(self):
  a=self.run_ranking()
  b=handoff_f11_to_f12(ranking=a,exposure_target_yen=3500)
  self.assertEqual(b["f12_plan"]["spent_yen"],3500)
  self.assertEqual(b["f12_plan"]["unspent_yen"],6500)
  self.assertEqual(len(b["f12_plan"]["selected"]),3)
  self.assertEqual([r["priority"] for r in b["f12_plan"]["selected"]],[1,2,3])
  self.assertFalse(b["virtual_trade_frozen"])
 def test_manual_select_and_unspent(self):
  a=self.run_ranking()
  b=handoff_f11_to_f12(ranking=a,exposure_target_yen=3500,
        mode="MANUAL",selected_races=[1,3],manual_race_amounts={1:1000,3:300})
  self.assertEqual(b["f12_plan"]["spent_yen"],1300)
  self.assertEqual(b["f12_plan"]["unspent_yen"],8700)
  self.assertEqual([x["race"] for x in b["f12_plan"]["selected"]],[1,3])
 def test_max_four_override(self):
  r=self.run_ranking([self.fixture.report(i,2.0-i/10) for i in range(1,5)],
                      max_races=4,confidence_by_race={i:.9 for i in range(1,5)})
  self.assertEqual(len(r["selected"]),4)
  self.assertEqual(r["max_races"],4)
 def test_all_skip_when_no_positive_ev(self):
  rows=[self.fixture.report(1,-0.5)]
  a=self.run_ranking(rows,confidence_by_race={1:.9})
  self.assertTrue(a["all_skip"])
  self.assertEqual(a["selected"],[])
  b=handoff_f11_to_f12(ranking=a,exposure_target_yen=3500)
  self.assertEqual(b["f12_plan"]["spent_yen"],0)
 def test_confidence_below_threshold_skips(self):
  a=self.run_ranking(min_confidence=.8)
  self.assertTrue(a["all_skip"])
 def test_market_stale_refused(self):
  with self.assertRaises(F11Rejected):
   self.run_ranking(cutoff_utc="2026-11-14T03:30:00Z")
 def test_future_market_refused(self):
  with self.assertRaises(F11Rejected):
   self.run_ranking(observed_utc="2026-11-14T03:06:00Z")
 def test_missing_confidence_refused(self):
  with self.assertRaises(F11Rejected):
   self.run_ranking(confidence_by_race={1:.9})
 def test_nan_confidence_refused(self):
  z={i:.7 for i in range(1,5)};z[1]=float("nan")
  with self.assertRaises(F11Rejected):
   self.run_ranking(confidence_by_race=z)
 def test_bad_utc_refused(self):
  with self.assertRaises(F11Rejected):
   self.run_ranking(observed_utc="2026-11-14T03:00:00")
 def test_P4_original_receipt_tampered_refused(self):
  r=self.comparisons();r[0]["markets"]["QUINELLA"]["research_model_expected_net"][0]["stressed_net_lower"]=9.9
  with self.assertRaises(RankingRejected):
   self.run_ranking(r)
 def test_duplicate_races_refused(self):
  r=self.comparisons();r[-1]["race"]=1
  with self.assertRaises(F11Rejected):
   self.run_ranking(r,confidence_by_race={1:.7,2:.7,3:.7})
 def test_handoff_f11_hash_tamper_refused(self):
  a=self.run_ranking();a["selected"][0]["tickets"][0]["weight"]=0
  with self.assertRaisesRegex(F11Rejected,"f11_receipt_modified"):
   handoff_f11_to_f12(ranking=a,exposure_target_yen=1000)
 def test_handoff_rehashed_live_false_claim_refused(self):
  a=self.run_ranking();a["source_jra_authenticated"]=True
  a["f11_sha256"]=digest({k:v for k,v in a.items() if k!="f11_sha256"})
  with self.assertRaises(F11Rejected):
   handoff_f11_to_f12(ranking=a,exposure_target_yen=1000)
 def test_handoff_more_budget_denied(self):
  a=self.run_ranking()
  with self.assertRaises(F12Rejected):
   handoff_f11_to_f12(ranking=a,exposure_target_yen=10100)
 def test_handoff_market_mismatch_denied(self):
  a=self.run_ranking();a["selected"][0]["ticket_type"]="BRACKET"
  a["f11_sha256"]=digest({k:v for k,v in a.items() if k!="f11_sha256"})
  with self.assertRaises(F11Rejected):
   handoff_f11_to_f12(ranking=a,exposure_target_yen=1000)
 def test_handoff_never_virtual_journal_freeze(self):
  a=self.run_ranking()
  b=handoff_f11_to_f12(ranking=a,exposure_target_yen=1000)
  self.assertEqual(b["scope"],"LAB_RANKING_TO_BUDGET_ONLY_NO_LIVE_FREEZE")
  self.assertFalse(b["actual_purchase_authorized"])
  self.assertFalse(b["virtual_trade_frozen"])
 def test_quinella_and_bracket_distinct(self):
  rows=self.comparisons()
  b=self.run_ranking(rows,ticket_type="BRACKET")
  a=self.run_ranking(rows,ticket_type="QUINELLA")
  self.assertEqual(b["ticket_type"],"BRACKET")
  self.assertNotEqual(b["f11_sha256"],a["f11_sha256"])
  r=handoff_f11_to_f12(ranking=b,exposure_target_yen=500)
  self.assertEqual(r["f12_plan"]["ticket_type"],"BRACKET")
if __name__=="__main__":unittest.main()
