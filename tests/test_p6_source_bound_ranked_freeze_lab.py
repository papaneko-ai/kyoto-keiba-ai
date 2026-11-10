"""P6-02 original-byte-bound ranked LAB freeze, fail-closed destructive tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from test_p4_source_bound_model_ev_research import SourceBoundMarketResearch
from diagnostics.p4_source_bound_model_ev_research import compare_source_market_to_frozen_model
from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races
from diagnostics.p6_source_bound_ranked_freeze_lab import freeze_ranked_research_day,FrozenRankingRejected
from diagnostics.p6_fixture_durable_ledger import read_journal,LabRejected
from diagnostics.p1_three_original_dual_intake import ThreeOriginalRejected

class RankedPreResultFreezeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  self.fx=SourceBoundMarketResearch(methodName="test_both_markets_original_bound_same_model_comparison")
  self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.input=self.fx.args()
  self.p4=compare_source_market_to_frozen_model(**self.input)
  self.ranking=rank_lab_research_races([self.p4],daily_budget_yen=1000)
  self.when="2026-11-13T04:07:00Z"
 def freeze(self,**kw):
  args={"day_inputs":[self.input],"ranking":self.ranking,
        "destination":self.root/"study","commit_utc":self.when}
  args.update(kw)
  return freeze_ranked_research_day(**args)
 def test_pre_result_frozen_and_restart_replay(self):
  receipt=self.freeze()
  self.assertEqual(receipt["research_spent_yen"],100)
  self.assertEqual(receipt["unspent_yen"],900)
  self.assertEqual(len(receipt["journals"]),1)
  self.assertFalse(receipt["official_origin_authenticated"])
  self.assertFalse(receipt["real_paper_trade_authorized"])
  self.assertFalse(receipt["actual_purchase_authorized"])
  m=json.loads((self.root/"study"/"manifest.json").read_text())
  self.assertEqual(m,receipt)
  j=receipt["journals"][0]
  state=read_journal(self.root/"study"/j["file"],expected_head=j["journal_head_sha256"])
  self.assertEqual(len(state["entries"]),1)
  self.assertEqual(state["result"]["status"],"UNSETTLED")
  frozen=state["entries"][0]["payload"]["record"]["frozen"]
  self.assertEqual(len(frozen["tickets"]),1)
  self.assertEqual(frozen["model_version"],self.input["frozen_model"]["model_version"])
  self.assertEqual(frozen["ledger_type"],"VIRTUAL_FIXTURE_ONLY")
  self.assertFalse("payout_per_100" in json.dumps(frozen))
 def test_independent_runs_produce_identical_receipts_and_journals(self):
  first=self.freeze()
  firstbytes=(self.root/"study"/"race-01.jsonl").read_bytes()
  second=self.freeze(destination=self.root/"study2")
  self.assertEqual(first,second)
  self.assertEqual(firstbytes,(self.root/"study2"/"race-01.jsonl").read_bytes())
 def test_refuses_overwrite_and_preserves_original(self):
  self.freeze()
  old=(self.root/"study"/"race-01.jsonl").read_bytes()
  with self.assertRaisesRegex(FrozenRankingRejected,"immutable_target_must_be_new"):
   self.freeze()
  self.assertEqual((self.root/"study"/"race-01.jsonl").read_bytes(),old)
 def test_wrong_ranking_digest_no_write(self):
  bad=copy.deepcopy(self.ranking);bad["ranking_sha256"]="0"*64
  with self.assertRaisesRegex(FrozenRankingRejected,"p5_ranking_recomputed_receipt_mismatch"):
   self.freeze(ranking=bad)
  self.assertFalse((self.root/"study").exists())
 def test_ranked_pair_price_tamper_no_write(self):
  bad=copy.deepcopy(self.input);bad["snapshot"]["odds"][0]["decimal"]=77.0
  with self.assertRaises(ThreeOriginalRejected):
   self.freeze(day_inputs=[bad])
  self.assertFalse((self.root/"study").exists())
 def test_future_result_or_post_cutoff_cannot_precommit(self):
  with self.assertRaisesRegex(FrozenRankingRejected,"pre_cutoff_commit_required"):
   self.freeze(commit_utc="2026-11-14T04:51:00Z")
  self.assertFalse((self.root/"study").exists())
 def test_missing_p4_capture_no_write(self):
  bad=copy.deepcopy(self.input);bad.pop("bundle")
  with self.assertRaisesRegex(FrozenRankingRejected,"complete_p4_input_required"):
   self.freeze(day_inputs=[bad])
  self.assertFalse((self.root/"study").exists())
 def test_duplicate_race_blocked_before_write(self):
  with self.assertRaisesRegex(FrozenRankingRejected,"duplicate_day_race"):
   self.freeze(day_inputs=[self.input,self.input])
  self.assertFalse((self.root/"study").exists())
 def test_model_mismatch_blocked_before_write(self):
  bad=copy.deepcopy(self.input);bad["frozen_model"]["strengths"]={"1":4.0,"2":1.0}
  with self.assertRaisesRegex(FrozenRankingRejected,"p5_ranking_recomputed_receipt_mismatch"):
   self.freeze(day_inputs=[bad])
  self.assertFalse((self.root/"study").exists())
 def test_false_race_selection_blocks_write(self):
  bad=copy.deepcopy(self.ranking)
  bad["selected"][0]["race"]=2
  with self.assertRaisesRegex(FrozenRankingRejected,"p5_ranking_recomputed_receipt_mismatch"):
   self.freeze(ranking=bad)
  self.assertFalse((self.root/"study").exists())
 def test_missing_journal_anchor_fails_post_restart(self):
  receipt=self.freeze()
  j=receipt["journals"][0]
  with self.assertRaisesRegex(LabRejected,"journal_head_anchor_mismatch"):
   read_journal(self.root/"study"/j["file"],expected_head="0"*64)
 def test_exact_budget_and_no_bet_if_zero(self):
  empty=rank_lab_research_races([self.p4],daily_budget_yen=0)
  receipt=self.freeze(ranking=empty)
  self.assertEqual(receipt["journals"],[])
  self.assertEqual(receipt["research_spent_yen"],0)
  self.assertEqual(sorted(x.name for x in (self.root/"study").iterdir()),["manifest.json"])
 def test_cannot_claim_live_event_from_lab(self):
  bad=copy.deepcopy(self.input)
  bad["frozen_model"]["provenance"]="OFFICIAL"
  with self.assertRaises(ValueError):self.freeze(day_inputs=[bad])
  self.assertFalse((self.root/"study").exists())
if __name__=="__main__": unittest.main()
