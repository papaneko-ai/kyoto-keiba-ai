"""Shared prediction contract: deterministic pair normalization, framing, rejection."""
import copy
import itertools
import tempfile
import unittest
from pathlib import Path
from diagnostics.p7_hybrid_model_registry import register_model
from diagnostics.p3_hybrid_prediction_contract import (
    check_lab_prediction,PredictionContractRejected)

A="a"*64
B="b"*64

def model(mid,kind="BASELINE",parents=None,weights=None):
    return {"model_id":mid,"kind":kind,"parents":parents or [],
            "feature_schema_sha256":A,"code_sha256":B,
            "configuration_sha256":"c"*64,"training_end_utc":None,
            "source_scope":"LAB_RESEARCH_ONLY","weights_bps":weights or []}

def fixture():
    runners=[{"horse_number":1,"frame_number":1},
             {"horse_number":2,"frame_number":1},
             {"horse_number":3,"frame_number":2},
             {"horse_number":4,"frame_number":2}]
    numbers=[r["horse_number"] for r in runners]
    qp=[{"pair":list(pair),"probability":1/6}
        for pair in itertools.combinations(numbers,2)]
    agg={}
    f={r["horse_number"]:r["frame_number"] for r in runners}
    for q in qp:
        pair=tuple(sorted(f[x] for x in q["pair"]))
        agg[pair]=agg.get(pair,0)+q["probability"]
    bp=[{"pair":list(p),"probability":v} for p,v in sorted(agg.items())]
    snapshot={"race_id":"LAB-KYOTO-01",
              "source_scope":"LAB_SYNTHETIC_ONLY",
              "source_sha256":"d"*64,
              "feature_schema_sha256":A,
              "cutoff_utc":"2026-11-13T04:00:00Z",
              "runners":runners}
    output={"model_id":"BASE","source_sha256":snapshot["source_sha256"],
            "feature_schema_sha256":A,
            "cutoff_utc":snapshot["cutoff_utc"],
            "quinella":qp,"bracket":bp}
    return snapshot,output

class HybridPredictionContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"registry.jsonl"
        register_model(self.path,model("BASE"))
        self.snap,self.out=fixture()

    def test_base_normalized_both_markets(self):
        r=check_lab_prediction(self.path,self.snap,self.out)
        self.assertEqual(r["quinella_pairs"],6)
        self.assertEqual(r["bracket_pairs"],3)
        self.assertTrue(r["same_frame_bracket_supported"])
        self.assertFalse(r["real_JRA_source_authenticated"])
        self.assertFalse(r["independently_certified"])

    def test_modify_add_ensemble_share_same_contract(self):
        register_model(self.path,model("MOD","MODIFY",["BASE"]))
        register_model(self.path,model("ADD","ADD",["BASE"]))
        register_model(self.path,model("MIX","ENSEMBLE",["MOD","ADD"],[6000,4000]))
        for mid in ["BASE","MOD","ADD","MIX"]:
            v={**self.out,"model_id":mid}
            r=check_lab_prediction(self.path,self.snap,v)
            self.assertEqual(r["model_kind"],{
                "BASE":"BASELINE","MOD":"MODIFY",
                "ADD":"ADD","MIX":"ENSEMBLE"}[mid])
            self.assertFalse(r["production_model_changed"])

    def test_repeat_determinism(self):
        self.assertEqual(check_lab_prediction(self.path,self.snap,self.out),
                         check_lab_prediction(self.path,self.snap,self.out))

    def test_unknown_model_fails(self):
        with self.assertRaises(ValueError):
            check_lab_prediction(self.path,self.snap,{**self.out,"model_id":"UNKNOWN"})

    def test_source_hash_mismatch_fails(self):
        with self.assertRaisesRegex(PredictionContractRejected,"model_or_source_mismatch"):
            check_lab_prediction(self.path,self.snap,{**self.out,"source_sha256":"0"*64})

    def test_changed_feature_schema_fails(self):
        with self.assertRaisesRegex(PredictionContractRejected,"model_or_source_mismatch"):
            check_lab_prediction(self.path,{**self.snap,"feature_schema_sha256":"b"*64},self.out)

    def test_different_cutoff_fails(self):
        with self.assertRaisesRegex(PredictionContractRejected,"cutoff_mismatch"):
            check_lab_prediction(self.path,self.snap,{**self.out,"cutoff_utc":"2026-11-13T04:05:00Z"})

    def test_duplicate_pair_fails(self):
        x=copy.deepcopy(self.out)
        x["quinella"][1]["pair"]=x["quinella"][0]["pair"]
        with self.assertRaisesRegex(PredictionContractRejected,"pair_invalid_or_duplicate"):
            check_lab_prediction(self.path,self.snap,x)

    def test_not_normalized_probability_fails(self):
        x=copy.deepcopy(self.out)
        x["quinella"][0]["probability"]=0.2
        with self.assertRaisesRegex(PredictionContractRejected,"normalization_invalid"):
            check_lab_prediction(self.path,self.snap,x)

    def test_wrong_bracket_aggregation_fails(self):
        x=copy.deepcopy(self.out)
        x["bracket"][0]["probability"]+=.05
        x["bracket"][1]["probability"]-=.05
        with self.assertRaisesRegex(PredictionContractRejected,"bracket_not_derived"):
            check_lab_prediction(self.path,self.snap,x)

    def test_missing_bracket_market_pair_fails(self):
        x=copy.deepcopy(self.out)
        x["bracket"].pop()
        with self.assertRaisesRegex(PredictionContractRejected,"market_not_complete"):
            check_lab_prediction(self.path,self.snap,x)

    def test_result_label_cannot_be_supplied(self):
        x=copy.deepcopy(self.snap)
        x["official_winner"]=2
        with self.assertRaisesRegex(PredictionContractRejected,"snapshot_schema_invalid"):
            check_lab_prediction(self.path,x,self.out)

    def test_real_jra_authenticity_claim_not_accepted(self):
        x=copy.deepcopy(self.snap)
        x["source_scope"]="OFFICIAL_JRA"
        with self.assertRaisesRegex(PredictionContractRejected,"model_or_source_mismatch"):
            check_lab_prediction(self.path,x,self.out)

    def test_true_boolean_probability_rejected(self):
        x=copy.deepcopy(self.out)
        x["quinella"][0]["probability"]=True
        with self.assertRaisesRegex(PredictionContractRejected,"probability_invalid"):
            check_lab_prediction(self.path,self.snap,x)

    def test_frame_number_change_changes_bracket_check(self):
        x=copy.deepcopy(self.snap)
        x["runners"][1]["frame_number"]=3
        with self.assertRaises(PredictionContractRejected):
            check_lab_prediction(self.path,x,self.out)

if __name__=="__main__":
    unittest.main()
