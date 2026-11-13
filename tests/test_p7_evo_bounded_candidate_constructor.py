"""EVO bounded algorithm construction from LAB labels: real formula and blind replays."""
import copy
import hashlib
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from diagnostics.p7_hybrid_model_registry import register_model,read_registry
from diagnostics.p7_hybrid_shadow_evolution_cycle import (
    read_shadow,freeze_lab_pair,settle_lab_pair)
from diagnostics.p7_evo_bounded_candidate_constructor import (
    construct_lab_candidate,forecast_lab_generated,audit_generated_holdout,
    CandidateBuildRejected)
from test_p3_hybrid_prediction_contract import fixture,model

START=datetime(2026,11,1,tzinfo=timezone.utc)
def at(hour):
    return (START+timedelta(hours=hour)).isoformat().replace("+00:00","Z")

class GeneratedEvoCandidateTests(unittest.TestCase):
 def setUp(self):
    tmp=tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    root=Path(tmp.name)
    self.registry=root/"models.jsonl";self.train_path=root/"train.jsonl"
    self.holdout_path=root/"holdout.jsonl"
    register_model(self.registry,model("BASE"))
    register_model(self.registry,model("DUMMY","MODIFY",["BASE"]))
    self.snap,self.baseline=fixture()
 def prep(self,i):
    s=copy.deepcopy(self.snap);s["race_id"]=f"LAB-GEN-RACE-{i:03d}"
    s["cutoff_utc"]=at(i*2)
    s["source_sha256"]=hashlib.sha256(f"LAB-SOURCE-{i}".encode()).hexdigest()
    b=copy.deepcopy(self.baseline);b["cutoff_utc"]=s["cutoff_utc"]
    b["source_sha256"]=s["source_sha256"]
    return s,b
 def add_training(self,winning=[1,2],n=6):
    for i in range(1,n+1):
        s,b=self.prep(i)
        d={**copy.deepcopy(b),"model_id":"DUMMY"}
        freeze_lab_pair(self.train_path,self.registry,s,b,d,freeze_utc=at(i*2-1),
                        expected_head=read_shadow(self.train_path)["head"])
    for i in range(1,n+1):
        settle_lab_pair(self.train_path,f"LAB-GEN-RACE-{i:03d}",winning,
                        outcome_utc=at(i*2+1),
                        expected_head=read_shadow(self.train_path)["head"])
 def generate(self):
    return construct_lab_candidate(self.train_path,self.registry,base_id="BASE",
        new_id="LAB-GEN-FRAME-1",plan_locked_utc=at(15))
 def build_holdout(self,proposal,winning=[1,2],count=12):
    for i in range(20,20+count):
        s,b=self.prep(i)
        pred=forecast_lab_generated(proposal,self.registry,s,b)
        freeze_lab_pair(self.holdout_path,self.registry,s,b,pred,
                        freeze_utc=at(i*2-1),
                        expected_head=read_shadow(self.holdout_path)["head"])
    for i in range(20,20+count):
        settle_lab_pair(self.holdout_path,f"LAB-GEN-RACE-{i:03d}",winning,
                        outcome_utc=at(i*2+1),
                        expected_head=read_shadow(self.holdout_path)["head"])
 def test_fit_and_register_new_model_from_training_only(self):
    self.add_training()
    p=self.generate()
    self.assertTrue(p["candidate_constructed"])
    self.assertEqual(p["configuration"]["formula"],"LAB_FRAME_GROUP_MULTIPLIER_V1")
    self.assertEqual(p["configuration"]["category"],"SAME_FRAME")
    self.assertEqual(p["configuration"]["factor_bps"],3000)
    self.assertGreater(p["training_gain"],0)
    self.assertEqual(read_registry(self.registry)["models"]["LAB-GEN-FRAME-1"]["kind"],"MODIFY")
    self.assertFalse(p["production_model_changed"])
 def test_generated_candidate_beats_baseline_on_unseen_same_frame_labs(self):
    self.add_training();p=self.generate();self.build_holdout(p)
    a=audit_generated_holdout(p,self.train_path,self.holdout_path,self.registry,
                             comparison_count=14)
    self.assertEqual(a["independent_brier_gate"],"LAB_ONLY_PASS")
    self.assertEqual(a["paired_logloss_gate"],"SHADOW_CANDIDATE_ELIGIBLE_FOR_INDEPENDENT_AUDIT")
    self.assertEqual(a["decision"],"LAB_GENERATED_CANDIDATE_FOR_FURTHER_AUDIT")
    self.assertFalse(a["candidate_deployed"])
 def test_generated_candidate_is_rejected_on_opposite_unseen_outcomes(self):
    self.add_training();p=self.generate();self.build_holdout(p,winning=[1,3])
    a=audit_generated_holdout(p,self.train_path,self.holdout_path,self.registry)
    self.assertEqual(a["decision"],"LAB_REJECT_GENERATED_RETAIN_BASELINE")
 def test_no_improvement_retains_baseline_without_register(self):
    self.add_training(winning=[1,3])
    before=read_registry(self.registry)["head"]
    # A cross-frame winner dominates this scenario, so generator may still
    # discover a gain; force a high minimum threshold beyond observed gain.
    result=construct_lab_candidate(self.train_path,self.registry,
        base_id="BASE",new_id="LAB-GEN-FRAME-1",
        plan_locked_utc=at(15),min_improvement=.99)
    self.assertEqual(result["state"],"NO_CANDIDATE_BASELINE_RETAINED")
    self.assertEqual(before,read_registry(self.registry)["head"])
 def test_generated_prediction_both_markets_normalized(self):
    self.add_training();p=self.generate()
    s,b=self.prep(20)
    pred=forecast_lab_generated(p,self.registry,s,b)
    self.assertAlmostEqual(sum(q["probability"] for q in pred["quinella"]),1,places=10)
    self.assertAlmostEqual(sum(q["probability"] for q in pred["bracket"]),1,places=10)
    self.assertEqual(len(pred["quinella"]),6)
    self.assertEqual(len(pred["bracket"]),3)
 def test_cannot_use_future_result_before_training_plan(self):
    self.add_training()
    with self.assertRaisesRegex(CandidateBuildRejected,"training_result_or_plan_lock_invalid"):
        construct_lab_candidate(self.train_path,self.registry,base_id="BASE",
            new_id="LAB-GEN-FRAME-1",plan_locked_utc=at(12))
 def test_unfrozen_training_results_fail(self):
    for i in range(1,7):
        s,b=self.prep(i)
        d={**copy.deepcopy(b),"model_id":"DUMMY"}
        freeze_lab_pair(self.train_path,self.registry,s,b,d,freeze_utc=at(i*2-1),
                        expected_head=read_shadow(self.train_path)["head"])
    with self.assertRaises(Exception):
        self.generate()
 def test_unchanged_proposal_replay_is_deterministic(self):
    self.add_training();p=self.generate()
    s,b=self.prep(20)
    self.assertEqual(forecast_lab_generated(p,self.registry,s,b),
                     forecast_lab_generated(p,self.registry,s,b))
 def test_changed_prediction_formula_config_refused(self):
    self.add_training();p=self.generate();p["configuration"]["factor_bps"]=500
    s,b=self.prep(20)
    with self.assertRaisesRegex(CandidateBuildRejected,"proposal_modified"):
        forecast_lab_generated(p,self.registry,s,b)
 def test_after_proposal_registry_modification_refused(self):
    self.add_training();p=self.generate()
    register_model(self.registry,model("NEW-OTHER","ADD",["BASE"]))
    s,b=self.prep(20)
    with self.assertRaisesRegex(CandidateBuildRejected,"generated_registry_version_drift"):
        forecast_lab_generated(p,self.registry,s,b)
 def test_holdout_winner_labels_not_accepted_as_prediction_input(self):
    self.add_training();p=self.generate()
    s,b=self.prep(20);s["winning_pair"]=[1,2]
    with self.assertRaises(Exception):
        forecast_lab_generated(p,self.registry,s,b)
 def test_forecast_must_follow_locked_plan(self):
    self.add_training();p=self.generate()
    s,b=self.prep(7)
    with self.assertRaisesRegex(CandidateBuildRejected,"holdout_not_after_plan_lock"):
        forecast_lab_generated(p,self.registry,s,b)
 def test_audit_requires_disjoint_ten_races(self):
    self.add_training();p=self.generate();self.build_holdout(p,count=9)
    with self.assertRaisesRegex(CandidateBuildRejected,"disjoint_complete_holdout_required"):
        audit_generated_holdout(p,self.train_path,self.holdout_path,self.registry)
 def test_audit_rederives_frozen_holdout_prediction(self):
    self.add_training();p=self.generate();self.build_holdout(p)
    from diagnostics.p7_hybrid_model_registry import _hash
    raw=[__import__("json").loads(x) for x in self.holdout_path.read_text().splitlines()]
    first=raw[0]
    first["data"]["predictions"][1]["quinella"][0]["probability"]+=.002
    first["event_sha256"]=_hash({k:v for k,v in first.items() if k!="event_sha256"})
    # Continuing hash chain is deliberately not repaired: corrupted source
    # should be rejected before model selection either way.
    self.holdout_path.write_text("\n".join(__import__("json").dumps(x,ensure_ascii=False)
        for x in raw)+"\n")
    with self.assertRaises(Exception):
        audit_generated_holdout(p,self.train_path,self.holdout_path,self.registry)
 def test_research_not_official_or_automatic(self):
    self.add_training();p=self.generate();self.build_holdout(p)
    a=audit_generated_holdout(p,self.train_path,self.holdout_path,self.registry)
    self.assertFalse(a["genuine_JRA_evidence_authenticated"])
    self.assertFalse(a["real_bet_authorized"])
    self.assertFalse(p["independent_audit_passed"])
if __name__=="__main__":unittest.main()
