"""F18 synthetic sealed study fixture and destructive forward rollback tests."""
import copy,unittest
from datetime import datetime,timezone,timedelta
from diagnostics.kyoto_f18_offline_shadow_rollback_contract import (
    research_shadow_evolution,F18Rejected,_hash
)

def rows(prefix,month,*,candidate=.75,champion=.35,baseline=.5):
    out=[]
    for i in range(10):
        date=f"2026-{month:02d}-{i+1:02d}"
        out.append({
          "race_id":prefix+f"-{i:02d}",
          "frozen_utc":date+"T04:00:00Z",
          "result_utc":date+"T05:00:00Z",
          "champion_probability":champion,
          "candidate_probability":candidate,
          "baseline_probability":baseline,
          "outcome":1,
          "source_kind":"LAB_SYNTHETIC_ONLY"})
    return out

def fixture(*,good=True,drift=True):
    holdout=rows("HOLD",2,candidate=.75 if good else .1)
    monitoring=[
        {"window_id":"MONITOR-01","race_ids":[r["race_id"] for r in rows("W1",3)],
         "observations":rows("W1",3)},
        {"window_id":"MONITOR-02","race_ids":[r["race_id"] for r in rows("W2",4,candidate=.1 if drift else .75)],
         "observations":rows("W2",4,candidate=.1 if drift else .75)}
    ]
    plan={"champion":"LAB-CHAMPION-v1","candidate":"LAB-CHALLENGER-v2",
          "baseline":"LAB-BASELINE-v0",
          "researcher_id":"LAB-MODEL-CONSTRUCTOR",
          "auditor_id":"INDEPENDENT-LAB-SCORER",
          "training_end_utc":"2026-01-01T00:00:00Z",
          "plan_locked_utc":"2026-01-02T00:00:00Z",
          "min_races":8,"min_mean_improvement":.01,
          "min_win_fraction":.8,"comparison_count":2,
          "holdout_race_ids":[r["race_id"] for r in holdout],
          "source_scope":"LAB_SYNTHETIC_ONLY",
          "monitoring_window_min_races":10,
          "declared_drift_max_loss_delta":.03,
          "decision_review":"SHADOW_ONLY_EXPLICIT_RESEARCH_REVIEW"}
    plan["sealed_plan_sha256"]=_hash(plan)
    return plan,holdout,monitoring

class F18ShadowRollbackTests(unittest.TestCase):
 def valid(self,**kwargs):
    p,h,m=fixture(**kwargs)
    return research_shadow_evolution(p,h,m)
 def test_sealed_champion_baseline_candidate_and_independent_admission(self):
    x=self.valid()
    self.assertEqual(x["first_independent_gate"],"LAB_ONLY_PASS")
    self.assertTrue(x["initial_shadow_admitted"])
    self.assertTrue(x["baseline_scored_on_same_holdout"])
    self.assertEqual(x["unique_holdout_monitor_races"],30)
 def test_forward_window_retains_shadow_when_improving(self):
    x=self.valid()
    self.assertEqual(x["forward_windows"][0]["state_after"],"SHADOW_CANDIDATE_UNDER_TEST")
 def test_drift_revokes_shadow_without_actual_model_mutation(self):
    x=self.valid()
    self.assertEqual(x["final_state"],"SHADOW_REVOKED_ROLLBACK_TO_CHAMPION")
    self.assertEqual(x["retained_production_champion"],"LAB-CHAMPION-v1")
    self.assertFalse(x["production_model_changed"])
    self.assertFalse(x["auto_deployed"])
 def test_no_drift_remains_shadow_only_never_prod(self):
    x=self.valid(drift=False)
    self.assertEqual(x["final_state"],"SHADOW_CANDIDATE_UNDER_TEST")
    self.assertFalse(x["production_model_changed"])
 def test_bad_candidate_never_admitted_or_alternate_promoted(self):
    x=self.valid(good=False)
    self.assertEqual(x["first_independent_gate"],"LAB_ONLY_REJECT")
    self.assertFalse(x["initial_shadow_admitted"])
    self.assertEqual(x["final_state"],"RETAINED_CHAMPION_NOT_ELIGIBLE")
    self.assertFalse(x["alternate_auto_promoted"])
 def test_same_inputs_same_receipt(self):
    self.assertEqual(self.valid(),self.valid())
 def test_holdout_overlap_rejected(self):
    p,h,m=fixture()
    m[0]["race_ids"][0]=h[0]["race_id"]
    m[0]["observations"][0]["race_id"]=h[0]["race_id"]
    with self.assertRaises(F18Rejected):research_shadow_evolution(p,h,m)
 def test_monitor_epoch_overlap_rejected(self):
    p,h,m=fixture()
    m[1]["observations"][0]["frozen_utc"]=m[0]["observations"][-1]["frozen_utc"]
    with self.assertRaises(F18Rejected):research_shadow_evolution(p,h,m)
 def test_forward_monitor_lucky_one_race_not_enough_to_hide_loss(self):
    p,h,m=fixture()
    m[1]["observations"][0]["candidate_probability"]=.75
    x=research_shadow_evolution(p,h,m)
    self.assertEqual(x["final_state"],"SHADOW_REVOKED_ROLLBACK_TO_CHAMPION")
 def test_unsealed_plan_rejected(self):
    p,h,m=fixture();p["comparison_count"]=1
    with self.assertRaisesRegex(F18Rejected,"plan_sha_invalid"):
        research_shadow_evolution(p,h,m)
 def test_loss_threshold_tamper_rejected(self):
    p,h,m=fixture()
    p["declared_drift_max_loss_delta"]=100
    p["sealed_plan_sha256"]=_hash({k:v for k,v in p.items() if k!="sealed_plan_sha256"})
    with self.assertRaisesRegex(F18Rejected,"unregistered_thresholds"):
        research_shadow_evolution(p,h,m)
 def test_future_labels_not_in_frozen_scores(self):
    p,h,m=fixture()
    h[0]["result_utc"]=h[0]["frozen_utc"]
    with self.assertRaises(Exception):research_shadow_evolution(p,h,m)
 def test_after_holdout_cannot_move_lock(self):
    p,h,m=fixture()
    p["plan_locked_utc"]="2026-03-01T00:00:00Z"
    p["sealed_plan_sha256"]=_hash({k:v for k,v in p.items() if k!="sealed_plan_sha256"})
    with self.assertRaises(Exception):research_shadow_evolution(p,h,m)
 def test_baseline_must_be_independent(self):
    p,h,m=fixture()
    p["baseline"]="LAB-CHALLENGER-v2"
    p["sealed_plan_sha256"]=_hash({k:v for k,v in p.items() if k!="sealed_plan_sha256"})
    with self.assertRaisesRegex(F18Rejected,"three_distinct"):
        research_shadow_evolution(p,h,m)
 def test_monitor_source_origin_cannot_be_fake_real_jra(self):
    p,h,m=fixture()
    m[1]["observations"][0]["source_kind"]="JRA_AUTHENTICATED"
    with self.assertRaisesRegex(F18Rejected,"source_or_order_changed"):
        research_shadow_evolution(p,h,m)
 def test_cannot_enable_real_deployment(self):
    p,h,m=fixture()
    with self.assertRaisesRegex(F18Rejected,"real_deployment_not_authorized"):
        research_shadow_evolution(p,h,m,lab_only=False)
 def test_no_real_bets_or_true_model_improvement_claim(self):
    x=self.valid()
    self.assertFalse(x["actual_bet_authorized"])
    self.assertFalse(x["real_jra_model_improvement_verified"])
 def test_forward_chain_changes_on_later_labels_only(self):
    p,h,m=fixture()
    before=research_shadow_evolution(p,h,m)
    m[1]["observations"][0]["candidate_probability"]=.15
    after=research_shadow_evolution(p,h,m)
    self.assertEqual(before["forward_windows"][0],after["forward_windows"][0])
    self.assertNotEqual(before["monitor_chain_head"],after["monitor_chain_head"])
 def test_duplicate_forward_race_rejected(self):
    p,h,m=fixture()
    m[1]["race_ids"][0]=m[0]["race_ids"][0]
    m[1]["observations"][0]["race_id"]=m[0]["race_ids"][0]
    with self.assertRaisesRegex(F18Rejected,"holdout_or_monitoring_reused"):
        research_shadow_evolution(p,h,m)
 def test_unauthorized_extra_monitor_fields_rejected(self):
    p,h,m=fixture()
    m[0]["observations"][0]["after_result_price"]=1.0
    with self.assertRaisesRegex(F18Rejected,"window_schema_invalid"):
        research_shadow_evolution(p,h,m)
if __name__=="__main__":unittest.main()
