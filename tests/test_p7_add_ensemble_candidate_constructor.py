"""P7 generated ADD/ENSEMBLE LAB: deterministic, adversarial, and blinded holdout."""
import copy,hashlib,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from diagnostics.p7_hybrid_model_registry import register_model,read_registry
from diagnostics.p7_hybrid_shadow_evolution_cycle import read_shadow,freeze_lab_pair,settle_lab_pair
from diagnostics.p7_add_ensemble_candidate_constructor import (
    construct_add_ensemble,forecast_add_ensemble,audit_add_ensemble_holdout,
    CandidateBuildRejected,TRIAL_COUNT)
from test_p3_hybrid_prediction_contract import fixture,model
START=datetime(2026,11,1,tzinfo=timezone.utc)
def at(h):return (START+timedelta(hours=h)).isoformat().replace("+00:00","Z")
class AddEnsembleResearchTests(unittest.TestCase):
 def setUp(self):
    t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
    root=Path(t.name);self.registry=root/"models.jsonl"
    self.training=root/"train.jsonl";self.holdout=root/"hold.jsonl"
    register_model(self.registry,model("BASE"))
    register_model(self.registry,model("DUMMY","MODIFY",["BASE"]))
 def prep(self,i):
    s,b=fixture();s=copy.deepcopy(s);b=copy.deepcopy(b)
    s["race_id"]=f"LAB-ADD-{i:03d}";s["cutoff_utc"]=at(i*2)
    s["source_sha256"]=hashlib.sha256(str(i).encode()).hexdigest()
    b["source_sha256"]=s["source_sha256"];b["cutoff_utc"]=s["cutoff_utc"]
    ps=[.55,.09,.09,.09,.09,.09]
    for q,p in zip(b["quinella"],ps):q["probability"]=p
    frames={x["horse_number"]:x["frame_number"] for x in s["runners"]}
    groups={}
    for q in b["quinella"]:
        key=tuple(sorted(frames[x] for x in q["pair"]))
        groups[key]=groups.get(key,0)+q["probability"]
    b["bracket"]=[{"pair":list(k),"probability":p} for k,p in sorted(groups.items())]
    return s,b
 def train(self):
    for i in range(1,7):
        s,b=self.prep(i)
        freeze_lab_pair(self.training,self.registry,s,b,{**b,"model_id":"DUMMY"},
            freeze_utc=at(i*2-1),expected_head=read_shadow(self.training)["head"])
    for i in range(1,7):
        settle_lab_pair(self.training,f"LAB-ADD-{i:03d}",[1,2],
            outcome_utc=at(i*2+1),expected_head=read_shadow(self.training)["head"])
 def construct(self,**kw):
    return construct_add_ensemble(self.training,self.registry,base_id="BASE",
        add_id="LAB-ADD-GENERATED",ensemble_id="LAB-ENS-GENERATED",
        plan_locked_utc=at(15),**kw)
 def hold(self,p,win=[1,2],n=12):
    for i in range(20,20+n):
        s,b=self.prep(i);new=forecast_add_ensemble(p,self.registry,s,b)
        freeze_lab_pair(self.holdout,self.registry,s,b,new,
            freeze_utc=at(i*2-1),expected_head=read_shadow(self.holdout)["head"])
    for i in range(20,20+n):
        settle_lab_pair(self.holdout,f"LAB-ADD-{i:03d}",win,
            outcome_utc=at(i*2+1),expected_head=read_shadow(self.holdout)["head"])
 def test_add_and_ensemble_are_registered(self):
    self.train();p=self.construct();m=read_registry(self.registry)["models"]
    self.assertEqual(m[p["add_id"]]["kind"],"ADD")
    self.assertEqual(m[p["ensemble_id"]]["kind"],"ENSEMBLE")
    self.assertEqual(sum(m[p["ensemble_id"]]["weights_bps"]),10000)
    self.assertEqual(p["trial_count"],TRIAL_COUNT)
    self.assertFalse(p["production_model_changed"])
 def test_blind_holdout_improves_both_scores(self):
    self.train();p=self.construct();self.hold(p)
    a=audit_add_ensemble_holdout(p,self.training,self.holdout,self.registry)
    self.assertEqual(a["decision"],"LAB_ONLY_FURTHER_AUDIT")
    self.assertFalse(a["real_JRA_certified"])
 def test_opposite_holdout_winners_rejected(self):
    self.train();p=self.construct();self.hold(p,win=[3,4])
    a=audit_add_ensemble_holdout(p,self.training,self.holdout,self.registry)
    self.assertEqual(a["decision"],"LAB_REJECT_BASELINE_RETAINED")
 def test_market_probabilities(self):
    self.train();p=self.construct();s,b=self.prep(20)
    q=forecast_add_ensemble(p,self.registry,s,b)
    self.assertAlmostEqual(sum(x["probability"] for x in q["quinella"]),1)
    self.assertAlmostEqual(sum(x["probability"] for x in q["bracket"]),1)
 def test_training_no_gain_preserves_registry(self):
    self.train();before=read_registry(self.registry)["head"]
    p=self.construct(min_improvement=.99)
    self.assertFalse(p["registered"])
    self.assertEqual(before,read_registry(self.registry)["head"])
 def test_short_holdout_refused(self):
    self.train();p=self.construct();self.hold(p,n=9)
    with self.assertRaisesRegex(CandidateBuildRejected,"disjoint_complete_holdout_required"):
        audit_add_ensemble_holdout(p,self.training,self.holdout,self.registry)
 def test_understated_trial_count_refused(self):
    self.train();p=self.construct();self.hold(p)
    with self.assertRaisesRegex(CandidateBuildRejected,"multiplicity_understated"):
        audit_add_ensemble_holdout(p,self.training,self.holdout,self.registry,comparison_count=1)
 def test_proposal_edit_refused(self):
    self.train();p=self.construct();p["config"]["temperature_bps"]=333
    s,b=self.prep(20)
    with self.assertRaisesRegex(CandidateBuildRejected,"proposal_modified"):
        forecast_add_ensemble(p,self.registry,s,b)
 def test_registry_drift_refused(self):
    self.train();p=self.construct()
    register_model(self.registry,model("DRIFT","MODIFY",["BASE"]))
    s,b=self.prep(20)
    with self.assertRaisesRegex(CandidateBuildRejected,"registry_changed"):
        forecast_add_ensemble(p,self.registry,s,b)
 def test_future_training_labels_refused(self):
    self.train()
    with self.assertRaisesRegex(CandidateBuildRejected,"training_source_or_time_invalid"):
        construct_add_ensemble(self.training,self.registry,base_id="BASE",
            add_id="LAB-ADD-2",ensemble_id="LAB-ENS-2",plan_locked_utc=at(12))
 def test_unfrozen_result_field_refused(self):
    self.train();p=self.construct();s,b=self.prep(20);s["winning_pair"]=[1,2]
    with self.assertRaises(Exception):forecast_add_ensemble(p,self.registry,s,b)
 def test_deterministic_reforecast(self):
    self.train();p=self.construct();s,b=self.prep(20)
    self.assertEqual(forecast_add_ensemble(p,self.registry,s,b),
                     forecast_add_ensemble(p,self.registry,s,b))
 def test_unsettled_holdout_refused(self):
    self.train();p=self.construct();s,b=self.prep(20)
    freeze_lab_pair(self.holdout,self.registry,s,b,
        forecast_add_ensemble(p,self.registry,s,b),freeze_utc=at(39),
        expected_head=read_shadow(self.holdout)["head"])
    with self.assertRaisesRegex(CandidateBuildRejected,"disjoint_complete_holdout_required"):
        audit_add_ensemble_holdout(p,self.training,self.holdout,self.registry)
 def test_rehashing_proposal_cannot_change_code_identity(self):
    from diagnostics.p7_hybrid_model_registry import _hash
    self.train();p=self.construct()
    p["model_specs"][0]["code_sha256"]="0"*64
    p["proposal_sha256"]=_hash({k:v for k,v in p.items() if k!="proposal_sha256"})
    s,b=self.prep(20)
    with self.assertRaises(CandidateBuildRejected):
        forecast_add_ensemble(p,self.registry,s,b)
 def test_holdout_audit_rejects_modified_proposal(self):
    self.train();p=self.construct();self.hold(p)
    p["trial_count"]=1
    with self.assertRaisesRegex(CandidateBuildRejected,"proposal_modified"):
        audit_add_ensemble_holdout(p,self.training,self.holdout,self.registry)
 def test_holdout_source_replay_remains_deterministic(self):
    self.train();p=self.construct();self.hold(p)
    a=audit_add_ensemble_holdout(p,self.training,self.holdout,self.registry)
    b=audit_add_ensemble_holdout(p,self.training,self.holdout,self.registry)
    self.assertEqual(a,b)
if __name__=="__main__":unittest.main()
