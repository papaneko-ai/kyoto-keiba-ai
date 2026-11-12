"""End-to-end original-byte LAB P4/P5 risk --> P6 frozen funds --> P6 result.

Synthetic/JRA-shaped source ONLY. No pre-race JRA authenticity and no bet.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from test_p5_p6_risk_allocated_freeze_bridge import RiskToFreezeTests,POLICY
from test_p6_final_html_settlement_lab import html
from diagnostics.p6_final_html_settlement_lab import settle_ranked_lab_results,FinalResultRejected
from diagnostics.p6_fixture_durable_ledger import read_journal

class RiskToFinalSettlementTests(unittest.TestCase):
 def setUp(self):
  self.fx=RiskToFreezeTests(methodName="test_recomputed_capital_freezes_identical_stakes")
  self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.frozen=self.fx.freeze()
  self.prior=self.fx.root/"risk-freeze"
  self.result=self.fx.root/"result"
  self.captures={str(x["race"]):{
    "raw":html(500,race=x["race"]),
    "captured_utc":"2026-11-14T05:10:00Z",
    "declared_scope":"LAB_RESULT_FIXTURE_ONLY"
  } for x in self.frozen["journals"]}
 def settle(self,**changes):
  args={"prior_directory":self.prior,"destination":self.result,
        "result_captures":self.captures,"version":1,
        "expected_prior_manifest_sha256":hashlib.sha256(
            (self.prior/"manifest.json").read_bytes()).hexdigest()}
  args.update(changes)
  return settle_ranked_lab_results(**args)
 def test_original_bound_capital_survives_final_settlement(self):
  result=self.settle()
  self.assertEqual(result["research_spent_yen"],self.fx.capital["research_spent_yen"])
  self.assertEqual(result["capital_receipt_sha256"],self.fx.capital["capital_sha256"])
  self.assertEqual(result["allocation_source"],"P5_RECOMPUTED_BOUNDED_RISK_CAPITAL")
  self.assertFalse(result["official_results_verified"])
  self.assertFalse(result["real_race_paper_trade_settled"])
  paid=0
  for item in result["journals"]:
   journal=read_journal(self.result/item["file"],expected_head=item["journal_head_sha256"])
   paid+=journal["result"]["payout_yen"]
   self.assertEqual(journal["result"]["status"],"FINAL_FIXTURE_ONLY")
  self.assertEqual(result["settled_fixture_payout_yen"],paid)
  self.assertEqual(result["settled_fixture_profit_yen"],paid-self.fx.capital["research_spent_yen"])
 def test_versioned_correction_preserves_original_frozen_capital(self):
  first=self.settle()
  second=self.settle(prior_directory=self.result,
   destination=self.fx.root/"corrected",
   expected_prior_manifest_sha256=hashlib.sha256((self.result/"manifest.json").read_bytes()).hexdigest(),
   version=2,result_captures={k:{**v,"raw":html(300)} for k,v in self.captures.items()})
  self.assertEqual(first["capital_receipt_sha256"],second["capital_receipt_sha256"])
  self.assertEqual(first["research_spent_yen"],second["research_spent_yen"])
  self.assertEqual(len(read_journal(self.prior/"race-01.jsonl")["entries"]),1)
 def test_tamper_manifest_stake_total_rejected_no_settlement(self):
  prior=self.prior/"manifest.json"
  content=json.loads(prior.read_text(encoding="utf8"))
  content["research_spent_yen"]+=100
  prior.write_text(json.dumps(content,ensure_ascii=False),encoding="utf8")
  with self.assertRaisesRegex(FinalResultRejected,"frozen_stakes_do_not_match_manifest_budget"):
   self.settle()
  self.assertFalse(self.result.exists())
 def test_forged_capital_provenance_blocked(self):
  prior=self.prior/"manifest.json"
  data=json.loads(prior.read_text(encoding="utf8"))
  data["capital_receipt_sha256"]="0"*63+"z"
  prior.write_text(json.dumps(data,ensure_ascii=False),encoding="utf8")
  with self.assertRaisesRegex(FinalResultRejected,"risk_capital_provenance_invalid"):
   self.settle()
  self.assertFalse(self.result.exists())
 def test_result_before_cutoff_fails_without_writes(self):
  bad={k:{**v,"captured_utc":"2026-11-14T04:20:00Z"} for k,v in self.captures.items()}
  with self.assertRaises(FinalResultRejected):
   self.settle(result_captures=bad)
  self.assertFalse(self.result.exists())
 def test_zero_capital_no_fictional_payout_or_profit(self):
  from diagnostics.p4_source_bound_model_ev_research import compare_source_market_to_frozen_model
  from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races
  from diagnostics.p5_bounded_risk_capital_lab import research_capital_control
  zero=rank_lab_research_races([compare_source_market_to_frozen_model(**self.fx.source)],daily_budget_yen=0)
  cap=research_capital_control(zero,**POLICY)
  prior=self.fx.root/"zero"
  f=self.fx.freeze(ranking=zero,capital_receipt=cap,destination=prior)
  receipt=settle_ranked_lab_results(prior_directory=prior,
    destination=self.fx.root/"zero_final",result_captures={},
    expected_prior_manifest_sha256=hashlib.sha256((prior/"manifest.json").read_bytes()).hexdigest(),version=1)
  self.assertEqual(f["research_spent_yen"],0)
  self.assertEqual(receipt["research_spent_yen"],0)
  self.assertEqual(receipt["settled_fixture_payout_yen"],0)
  self.assertEqual(receipt["settled_fixture_profit_yen"],0)

if __name__=="__main__":unittest.main()
