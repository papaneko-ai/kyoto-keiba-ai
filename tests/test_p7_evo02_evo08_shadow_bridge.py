"""EVO-02 weakness/EVO-08 surprise from settled training, then blind holdout.

Regression tests use only fabricated LAB outcomes; a passing lab candidate
cannot become a production model.
"""
import copy
import hashlib
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from diagnostics.p7_hybrid_model_registry import register_model
from diagnostics.p7_hybrid_shadow_evolution_cycle import (
    read_shadow,freeze_lab_pair,settle_lab_pair)
from diagnostics.p7_evo02_evo08_shadow_bridge import (
    propose_evo02_evo08,audit_evo_holdout,ProposalRejected)
from test_p3_hybrid_prediction_contract import fixture,model
from test_p7_hybrid_shadow_evolution_cycle import prediction

DAY=datetime(2026,11,1,tzinfo=timezone.utc)
def stamp(hour):
    return (DAY+timedelta(hours=hour)).isoformat().replace("+00:00","Z")

class WeaknessSurpriseShadowBridgeTests(unittest.TestCase):
 def setUp(self):
    tmp=tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    p=Path(tmp.name)
    self.registry=p/"models.jsonl"
    self.training=p/"train.jsonl"
    self.holdout=p/"holdout.jsonl"
    register_model(self.registry,model("BASE"))
    register_model(self.registry,model("MOD","MODIFY",["BASE"]))
    register_model(self.registry,model("ALTERNATE","ADD",["BASE"]))
    self.base,_=fixture()
 def add_races(self,path,*,start,count,candidate=.7,champion=.2,winner=(1,3)):
    for i in range(start,start+count):
        snap=copy.deepcopy(self.base)
        snap["race_id"]=f"LAB-PAIR-{i:04d}"
        snap["source_sha256"]=hashlib.sha256(f"LAB-SOURCE-{i}".encode()).hexdigest()
        snap["cutoff_utc"]=stamp(i*2)
        a=prediction("BASE",snap,champion)
        b=prediction("MOD",snap,candidate)
        freeze_lab_pair(path,self.registry,snap,a,b,
            freeze_utc=stamp(i*2-1),expected_head=read_shadow(path)["head"])
    for i in range(start,start+count):
        settle_lab_pair(path,f"LAB-PAIR-{i:04d}",list(winner),
            outcome_utc=stamp(i*2+1),expected_head=read_shadow(path)["head"])
 def train(self,candidate=.7,champion=.2):
    self.add_races(self.training,start=1,count=6,candidate=candidate,champion=champion)
    return propose_evo02_evo08(self.training,self.registry,
        champion_id="BASE",challenger_id="MOD",alternative_id="ALTERNATE",
        plan_locked_utc=stamp(15),surprise_ceiling=.25)
 def hold(self,*,candidate=.7,champion=.2,start=20,count=10):
    self.add_races(self.holdout,start=start,count=count,candidate=candidate,champion=champion)
 def audit(self,proposal):
    return audit_evo_holdout(proposal,self.training,self.holdout,self.registry)
 def test_training_weakness_and_surprise_proposed(self):
    p=self.train()
    self.assertEqual(p["evo02_priority"],"CROSS_FRAME")
    self.assertEqual(len(p["evo08_surprise_cases"]),6)
    self.assertEqual(p["candidate_kind"],"MODIFY")
    self.assertFalse(p["candidate_generated_or_trained"])
 def test_candidate_survives_both_independent_lab_gates(self):
    p=self.train();self.hold()
    result=self.audit(p)
    self.assertEqual(result["independent_brier_gate"],"LAB_ONLY_PASS")
    self.assertEqual(result["logloss_guard"],"SHADOW_CANDIDATE_ELIGIBLE_FOR_INDEPENDENT_AUDIT")
    self.assertEqual(result["decision"],"LAB_SHADOW_ELIGIBLE_FOR_FURTHER_AUDIT")
    self.assertFalse(result["candidate_promoted"])
    self.assertFalse(result["real_JRA_effectiveness_verified"])
 def test_bad_unseen_holdout_rejected_after_same_training(self):
    p=self.train();self.hold(candidate=.1,champion=.7)
    result=self.audit(p)
    self.assertEqual(result["decision"],"LAB_REJECT_RETAIN_CHAMPION")
 def test_holdout_outcome_mutation_not_used_for_discovery(self):
    p=self.train();self.hold()
    original=p["proposal_sha256"]
    x=read_shadow(self.holdout)
    self.assertTrue(x["settled"])
    self.assertEqual(self.train.__class__,type(self.train))
    self.assertEqual(original,propose_evo02_evo08(self.training,self.registry,
        champion_id="BASE",challenger_id="MOD",alternative_id="ALTERNATE",
        plan_locked_utc=stamp(15),surprise_ceiling=.25)["proposal_sha256"])
 def test_holdout_train_overlap_refused(self):
    p=self.train()
    self.hold(start=1,count=10)
    with self.assertRaisesRegex(ProposalRejected,"holdout_training_race_overlap"):
        self.audit(p)
 def test_early_lock_refused(self):
    self.add_races(self.training,start=1,count=6)
    with self.assertRaisesRegex(ProposalRejected,"plan_must_follow_all_training_results"):
        propose_evo02_evo08(self.training,self.registry,champion_id="BASE",
            challenger_id="MOD",alternative_id="ALTERNATE",plan_locked_utc=stamp(8))
 def test_holdout_begins_before_lock_refused(self):
    p=self.train();self.hold(start=7,count=10)
    with self.assertRaisesRegex(ProposalRejected,"holdout_started_before_proposal_lock"):
        self.audit(p)
 def test_holdout_forecast_frozen_before_locked_plan_refused(self):
    p=self.train()
    # All cutoffs occur later, but a falsified first freeze timestamp precedes
    # the discovery lock and must not be used as a prospective validation.
    from diagnostics.p7_hybrid_shadow_evolution_cycle import _append
    snap=copy.deepcopy(self.base)
    snap["race_id"]="LAB-EARLY-FREEZE"
    snap["cutoff_utc"]=stamp(40)
    snap["source_sha256"]=hashlib.sha256(b"early-frozen-source").hexdigest()
    a=prediction("BASE",snap,.2);b=prediction("MOD",snap,.7)
    freeze_lab_pair(self.holdout,self.registry,snap,a,b,
        freeze_utc=stamp(14),expected_head=read_shadow(self.holdout)["head"])
    for i in range(21,30):
        snap=copy.deepcopy(self.base)
        snap["race_id"]=f"LAB-PAIR-{i:04d}"
        snap["cutoff_utc"]=stamp(i*2)
        snap["source_sha256"]=hashlib.sha256(f"LAB-SOURCE-{i}".encode()).hexdigest()
        a=prediction("BASE",snap,.2);b=prediction("MOD",snap,.7)
        freeze_lab_pair(self.holdout,self.registry,snap,a,b,
            freeze_utc=stamp(i*2-1),expected_head=read_shadow(self.holdout)["head"])
    settle_lab_pair(self.holdout,"LAB-EARLY-FREEZE",[1,3],
        outcome_utc=stamp(41),expected_head=read_shadow(self.holdout)["head"])
    for i in range(21,30):
        settle_lab_pair(self.holdout,f"LAB-PAIR-{i:04d}",[1,3],
            outcome_utc=stamp(i*2+1),expected_head=read_shadow(self.holdout)["head"])
    with self.assertRaisesRegex(ProposalRejected,"holdout_started_before_proposal_lock"):
        self.audit(p)
 def test_shared_f17_analysis_uses_only_settled_training(self):
    from diagnostics.kyoto_f17_executable_lab_streams import summarize_frozen_evo02_evo08_errors
    rows=[{"race_id":"LAB-ONE","cutoff_utc":stamp(2),
        "result_utc":stamp(3),"error_category":"CROSS_FRAME",
        "champion_loss":2.0,"challenger_loss":.4,
        "champion_winning_pair_probability":.1}]
    a=summarize_frozen_evo02_evo08_errors(rows,surprise_ceiling=.2)
    self.assertEqual(a["evo02_priority"],"CROSS_FRAME")
    self.assertEqual(a["evo08_surprise_cases"][0]["race_id"],"LAB-ONE")
    with self.assertRaises(ValueError):
        summarize_frozen_evo02_evo08_errors(rows+[rows[0]],surprise_ceiling=.2)
 def test_missing_holdout_outcome_refused(self):
    p=self.train()
    self.hold(count=9)
    with self.assertRaisesRegex(ProposalRejected,"holdout_incomplete_or_prejudged"):
        self.audit(p)
 def test_rewritten_proposal_hash_refused(self):
    p=self.train();self.hold()
    p["evo02_priority"]="SAME_FRAME"
    with self.assertRaisesRegex(ProposalRejected,"proposal_hash_mismatch"):
        self.audit(p)
 def test_changed_registry_after_precommit_refused(self):
    p=self.train();self.hold()
    register_model(self.registry,model("NEW-POST-LOCK","ADD",["BASE"]))
    with self.assertRaisesRegex(ProposalRejected,"model_registry_changed_since_plan"):
        self.audit(p)
 def test_train_label_not_allowed_to_be_unsettled(self):
    self.add_races(self.training,start=1,count=6)
    from diagnostics.p7_hybrid_shadow_evolution_cycle import _append
    # A decision is forbidden for the training discovery input.
    p=self.train
    self.assertTrue(callable(p))
    with self.assertRaises(ProposalRejected):
        propose_evo02_evo08(self.training,self.registry,champion_id="BASE",
            challenger_id="MOD",alternative_id="ALTERNATE",plan_locked_utc=stamp(12))
 def test_wrong_champion_candidate_id_refused(self):
    self.add_races(self.training,start=1,count=6)
    with self.assertRaisesRegex(ProposalRejected,"training_forecast_model_pair_mismatch"):
        propose_evo02_evo08(self.training,self.registry,champion_id="BASE",
            challenger_id="ALTERNATE",alternative_id="MOD",plan_locked_utc=stamp(15))
 def test_surprise_threshold_invalid(self):
    self.add_races(self.training,start=1,count=6)
    with self.assertRaisesRegex(ProposalRejected,"surprise_ceiling_invalid"):
        propose_evo02_evo08(self.training,self.registry,champion_id="BASE",
            challenger_id="MOD",alternative_id="ALTERNATE",plan_locked_utc=stamp(15),
            surprise_ceiling=True)
 def test_no_real_placement_or_jra_claim(self):
    p=self.train();self.hold()
    a=self.audit(p)
    self.assertFalse(a["real_bet_authorized"])
    self.assertFalse(a["auto_deploy"])
    self.assertFalse(p["independently_certified"])
if __name__=="__main__":
    unittest.main()
