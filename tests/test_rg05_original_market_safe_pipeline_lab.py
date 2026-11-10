"""RG05B strict P1 original bytes -> dual-market risk -> immutable LAB P6."""
import copy
import unittest
from pathlib import Path
from test_p1_three_original_content_binding import (
    StrictThreeOriginalContentTests,market_html,NOW
)
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.p1_three_original_dual_intake import ThreeOriginalRejected
from diagnostics.rg05_original_market_safe_pipeline_lab import (
    guarded_lab_freeze,guarded_lab_settlement,SafePipelineRejected
)
from diagnostics.p6_fixture_durable_ledger import read_journal,LabRejected

class OriginalToJournalSafety(unittest.TestCase):
    def setUp(self):
        self.fixt=StrictThreeOriginalContentTests(methodName="test_all_three_originals_match")
        self.fixt.setUp()
        self.addCleanup(self.fixt.doCleanups)
        self.path=self.fixt.root/"study.jsonl"
    def inputs(self,**kw):
        values={"journal_path":self.path,
           "bundle":export_bundle(self.fixt.manifest,self.fixt.root,observed_utc=NOW),
           "snapshot":copy.deepcopy(self.fixt.snapshot),"observed_utc":NOW,
           "channel":"PC","strengths":{1:2.0,2:1.0},
           "scenario_id":"LAB-P1-TO-P6-01",
           "frozen_utc":"2026-11-13T05:05:00Z"}
        values.update(kw)
        return values
    def freeze(self,**kw):
        return guarded_lab_freeze(**self.inputs(**kw))
    def test_strict_p1_p4_p6_finish_before_journal(self):
        r=self.freeze()
        self.assertTrue(r["journal_written"])
        self.assertFalse(r["independent_official_origin_authenticated"])
        self.assertFalse(r["real_paper_trade"])
        self.assertEqual(r["network_requests"],0)
        key="-".join(map(str,r["lab_freeze"]["chosen_pair"]))
        done=guarded_lab_settlement(self.path,frozen_report=r,
            expected_head=r["lab_freeze"]["journal_head_sha256"],
            payout_per_100={key:450},refunded_pairs=[],
            event_utc="2026-11-14T06:00:00Z")
        self.assertEqual(done["state"],"FINAL_FIXTURE_ONLY")
        self.assertEqual(done["result"]["payout_yen"],450)
        self.assertEqual(len(read_journal(self.path)["entries"]),2)
    def test_repeatability_on_separate_immutable_journal(self):
        r=self.freeze()
        other=self.fixt.root/"other.jsonl"
        x=self.freeze(journal_path=other)
        self.assertEqual(r["lab_freeze"]["frozen_prediction_sha256"],
                         x["lab_freeze"]["frozen_prediction_sha256"])
        self.assertEqual(r["lab_freeze"]["journal_head_sha256"],
                         x["lab_freeze"]["journal_head_sha256"])
    def test_fake_quinella_price_no_write(self):
        snapshot=copy.deepcopy(self.fixt.snapshot)
        snapshot["odds"][0]["decimal"]=88.0
        with self.assertRaisesRegex(ThreeOriginalRejected,"odds_original_prices_disagree"):
            self.freeze(snapshot=snapshot)
        self.assertFalse(self.path.exists())
    def test_fake_bracket_price_no_write(self):
        snapshot=copy.deepcopy(self.fixt.snapshot)
        snapshot["bracket_odds"][0]["decimal"]=88.0
        with self.assertRaisesRegex(ThreeOriginalRejected,"bracket_odds_original_prices_disagree"):
            self.freeze(snapshot=snapshot)
        self.assertFalse(self.path.exists())
    def test_missing_bracket_market_no_write(self):
        snapshot=copy.deepcopy(self.fixt.snapshot)
        snapshot["bracket_odds"]=[]
        with self.assertRaises(ThreeOriginalRejected):
            self.freeze(snapshot=snapshot)
        self.assertFalse(self.path.exists())
    def test_original_sha_tamper_no_write(self):
        self.fixt.manifest["sources"][0]["sha256"]="0"*64
        with self.assertRaises(Exception):self.freeze()
        self.assertFalse(self.path.exists())
    def test_final_odds_mislabeled_prerace_no_write(self):
        self.fixt.set_original(1,market_html("馬連オッズ","umaren",["1 2 3.1"],final=True))
        with self.assertRaisesRegex(ThreeOriginalRejected,"historical_final_forbidden"):
            self.freeze()
        self.assertFalse(self.path.exists())
    def test_withdrawn_runner_never_writes(self):
        snap=copy.deepcopy(self.fixt.snapshot)
        snap["runners"][1]["status"]="WITHDRAWN"
        with self.assertRaises(Exception):self.freeze(snapshot=snap)
        self.assertFalse(self.path.exists())
    def test_sales_suspended_no_write(self):
        snap=copy.deepcopy(self.fixt.snapshot)
        snap["market_states"]["bracket"]["sales"]="SUSPENDED"
        with self.assertRaises(ThreeOriginalRejected):self.freeze(snapshot=snap)
        self.assertFalse(self.path.exists())
    def test_future_market_no_write(self):
        snap=copy.deepcopy(self.fixt.snapshot)
        snap["sources"]["odds"]["captured_utc"]="2026-11-14T05:00:00Z"
        with self.assertRaises(Exception):self.freeze(snapshot=snap)
        self.assertFalse(self.path.exists())
    def test_wrong_model_roster_no_write(self):
        with self.assertRaisesRegex(SafePipelineRejected,"prediction_roster_mismatch"):
            self.freeze(strengths={1:2.0,3:1.0})
        self.assertFalse(self.path.exists())
    def test_bad_model_probabilities_no_write(self):
        with self.assertRaises(Exception):self.freeze(strengths={1:float("nan"),2:1.0})
        self.assertFalse(self.path.exists())
    def test_wrong_lab_marker_no_write(self):
        with self.assertRaisesRegex(SafePipelineRejected,"lab_only_strengths"):
            self.freeze(scenario_id="REAL-KYOTO-01")
        self.assertFalse(self.path.exists())
    def test_invalid_risk_parameter_no_write(self):
        with self.assertRaises(Exception):self.freeze(odds_drift_fraction=1.2)
        self.assertFalse(self.path.exists())
    def test_no_clobber_existing_journal(self):
        r=self.freeze()
        before=self.path.read_bytes()
        with self.assertRaisesRegex(SafePipelineRejected,"immutable_journal_target"):
            self.freeze()
        self.assertEqual(before,self.path.read_bytes())
    def test_result_cannot_attach_wrong_freeze(self):
        r=self.freeze()
        before=self.path.read_bytes()
        with self.assertRaisesRegex(SafePipelineRejected,"original_research_freeze_anchor"):
            guarded_lab_settlement(self.path,frozen_report=r,
                 expected_head="0"*64,payout_per_100={},refunded_pairs=[],
                 event_utc="2026-11-14T06:00:00Z")
        self.assertEqual(before,self.path.read_bytes())
    def test_no_double_settlement(self):
        r=self.freeze()
        head=r["lab_freeze"]["journal_head_sha256"]
        guarded_lab_settlement(self.path,frozen_report=r,expected_head=head,
                 payout_per_100={},refunded_pairs=[],event_utc="2026-11-14T06:00:00Z")
        before=self.path.read_bytes()
        with self.assertRaises(LabRejected):
            guarded_lab_settlement(self.path,frozen_report=r,expected_head=head,
                 payout_per_100={},refunded_pairs=[],event_utc="2026-11-14T06:00:00Z")
        self.assertEqual(before,self.path.read_bytes())

if __name__=="__main__": unittest.main()
