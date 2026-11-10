"""P6-03 verify HTML payout replay from immutable P6-02 LAB freeze."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from test_p6_source_bound_ranked_freeze_lab import RankedPreResultFreezeTests
from diagnostics.p6_final_html_settlement_lab import (
    settle_ranked_lab_results,FinalResultRejected)
from diagnostics.p6_fixture_durable_ledger import read_journal,LabRejected

def html(paid=500, date="2026年11月14日",race=1,ambiguous=False):
    row=f"馬連 1-2 {paid:,} 円"+(" 1-2 800 円" if ambiguous else "")
    return (f"<html><body>{date} 京都 {race}レース "
            f"払戻金 単勝 1 100 円 {row} 馬単 1-2 700 円 "
            f"枠連 1-2 400 円 ワイド 1-2 200 円</body></html>").encode("cp932")

class SavedFinalResultTests(unittest.TestCase):
 def setUp(self):
  self.fx=RankedPreResultFreezeTests(methodName="test_pre_result_frozen_and_restart_replay")
  self.fx.setUp()
  self.addCleanup(self.fx.doCleanups)
  self.freeze=self.fx.freeze()
  self.prior=self.fx.root/"study"
  self.target=self.fx.root/"settled"
  self.when="2026-11-14T05:10:00Z"
  self.capture={"1":{"raw":html(),"captured_utc":self.when,
                     "declared_scope":"LAB_RESULT_FIXTURE_ONLY"}}
 def sha(self,path):
  return hashlib.sha256((path/"manifest.json").read_bytes()).hexdigest()
 def settle(self,**kw):
  opts={"prior_directory":self.prior,"destination":self.target,
        "result_captures":self.capture,
        "expected_prior_manifest_sha256":self.sha(self.prior),"version":1}
  opts.update(kw)
  return settle_ranked_lab_results(**opts)
 def test_synthetic_final_html_settles_frozen_ticket(self):
  result=self.settle()
  self.assertEqual(result["settled_fixture_payout_yen"],500)
  self.assertEqual(result["settled_fixture_profit_yen"],400)
  self.assertFalse(result["official_results_verified"])
  self.assertFalse(result["real_race_paper_trade_settled"])
  self.assertFalse(result["actual_purchase_authorized"])
  state=read_journal(self.target/"race-01.jsonl",
                     expected_head=result["journals"][0]["journal_head_sha256"])
  self.assertEqual(state["result"]["status"],"FINAL_FIXTURE_ONLY")
  self.assertEqual(state["result"]["ticket_hits"],1)
  self.assertEqual(len(state["entries"]),2)
  self.assertEqual(len(read_journal(self.prior/"race-01.jsonl")["entries"]),1)
 def test_same_inputs_identical_archives_and_receipts(self):
  a=self.settle()
  b=self.settle(destination=self.fx.root/"second")
  self.assertEqual(a,b)
  self.assertEqual((self.target/"race-01.jsonl").read_bytes(),
                   (self.fx.root/"second"/"race-01.jsonl").read_bytes())
 def test_versioned_correction_replaces_old_payout(self):
  a=self.settle()
  newer={"1":{**self.capture["1"],"raw":html(300)}}
  result=self.settle(prior_directory=self.target,
       destination=self.fx.root/"corrected",result_captures=newer,
       expected_prior_manifest_sha256=self.sha(self.target),version=2)
  self.assertEqual(result["settled_fixture_payout_yen"],300)
  self.assertEqual(result["settled_fixture_profit_yen"],200)
  self.assertEqual(len(read_journal(self.fx.root/"corrected"/"race-01.jsonl")["entries"]),3)
  self.assertEqual(read_journal(self.target/"race-01.jsonl")["result"]["payout_yen"],500)
 def test_same_version_correction_refused(self):
  self.settle()
  with self.assertRaisesRegex(FinalResultRejected,"result_version_not_next"):
   self.settle(prior_directory=self.target,destination=self.fx.root/"again",
               expected_prior_manifest_sha256=self.sha(self.target))
 def test_existing_target_never_overwritten(self):
  self.settle()
  before=(self.target/"race-01.jsonl").read_bytes()
  with self.assertRaisesRegex(FinalResultRejected,"immutable_source_or_target_invalid"):
   self.settle()
  self.assertEqual((self.target/"race-01.jsonl").read_bytes(),before)
 def test_wrong_external_manifest_anchor_rejected(self):
  with self.assertRaisesRegex(FinalResultRejected,"prior_manifest_sha_mismatch"):
   self.settle(expected_prior_manifest_sha256="0"*64)
  self.assertFalse(self.target.exists())
 def test_tampered_frozen_journal_rejected(self):
  p=self.prior/"race-01.jsonl"
  p.write_bytes(p.read_bytes().replace(b"LAB-CANDIDATE",b"LAB-FAKE-----"))
  with self.assertRaises(LabRejected):self.settle()
  self.assertFalse(self.target.exists())
 def test_final_date_mismatch_rejected(self):
  self.capture["1"]["raw"]=html(date="2026年11月15日")
  with self.assertRaisesRegex(FinalResultRejected,"result_meeting_date_mismatch"):
   self.settle()
  self.assertFalse(self.target.exists())
 def test_wrong_race_section_rejected(self):
  self.capture["1"]["raw"]=html(race=2)
  with self.assertRaisesRegex(FinalResultRejected,"result_race_identity_missing"):
   self.settle()
 def test_ambiguous_market_payout_rejected(self):
  self.capture["1"]["raw"]=html(ambiguous=True)
  with self.assertRaisesRegex(FinalResultRejected,"payout_pair_ambiguous"):
   self.settle()
 def test_unproven_official_origin_claim_rejected(self):
  self.capture["1"]["declared_scope"]="OFFICIAL_JRA"
  with self.assertRaisesRegex(FinalResultRejected,"official_result_claim_not_authorized"):
   self.settle()
 def test_result_captured_before_cutoff_rejected(self):
  self.capture["1"]["captured_utc"]="2026-11-14T04:20:00Z"
  with self.assertRaisesRegex(FinalResultRejected,"result_capture_not_after_cutoff"):
   self.settle()
 def test_no_result_and_extra_result_rejected(self):
  with self.assertRaisesRegex(FinalResultRejected,"exact_result_race_coverage_required"):
   self.settle(result_captures={})
  with self.assertRaisesRegex(FinalResultRejected,"exact_result_race_coverage_required"):
   self.settle(result_captures={**self.capture,"2":self.capture["1"]})
 def test_markets_do_not_cross_payouts(self):
  # 400 is a bracket payout, NOT the QUINELLA payout.
  self.assertEqual(self.settle()["settled_fixture_payout_yen"],500)
 def test_payout_without_original_bet_is_zero(self):
  self.capture["1"]["raw"]=html().replace(b"1-2 500",b"1-3 500")
  result=self.settle()
  self.assertEqual(result["settled_fixture_payout_yen"],0)
  self.assertEqual(result["settled_fixture_profit_yen"],-100)
if __name__=="__main__":unittest.main()
