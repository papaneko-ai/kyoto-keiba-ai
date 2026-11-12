"""F17 all 8 approved EVO capabilities integrated to true pinned F18 LAB receipt."""
import copy,unittest
from diagnostics.kyoto_f17_evo_eight_integrated_research import integrate,F17Rejected,dig
from diagnostics.kyoto_f18_offline_shadow_rollback_contract import research_shadow_evolution
from tests.test_kyoto_f18_offline_shadow_rollback_contract import fixture
from pathlib import Path

RUBRIC=Path("docs/diagnostics/kyoto_final_completion_criteria_v1.json").read_bytes()

def original_f18_lab():
    p,h,m=fixture()
    return {
      "schema":"kyoto_F18_first_lab_witness.v1",
      "ci_run_id":"43144148977","ci_sha":"5824eaf63217f94d1980472826c0d7faf8add030",
      "source_scope":"SYNTHETIC_LAB_HOLDOUT_NOT_REAL_JRA",
      "plan":p,"holdout":h,"forward_monitoring":m,
      "decision":research_shadow_evolution(p,h,m),
      "production_model_changed":False,"real_jra_calibration_proven":False
    }

def sample():
    f=original_f18_lab()
    score=f["decision"]["holdout_scores"]
    inp={
      "EVO-01":{"source_cost":2,"source_coverage":.95,"value_gain":5},
      "EVO-02":{"failure_category":"LAB_LONGSHOT_BUCKET","baseline_loss":.6,
                "candidate_loss":.3},
      "EVO-03":{"paired_races":10,"champion_loss":score["champion_mean_log_loss"],
                "shadow_loss":score["candidate_mean_log_loss"]},
      "EVO-04":{"preregistered_portfolios":2,"matched_races":10,"drawdown":.2},
      "EVO-05":{"baseline_drift":.6,"current_drift":.2,"monitor_windows":3},
      "EVO-06":{"research_budget":10,"experiment_count":3,"holdout_unused":True},
      "EVO-07":{"audit_plan_sha256":f["plan"]["sealed_plan_sha256"],
                "independent_holdout":True,"certifier_independent":True},
      "EVO-08":{"surprise_metric":.15,"counterexamples":2,"independent_retest":True}
    }
    research={
      "sources":[
          {"id":"OFFICIAL-HISTORY","cost":2,"value":5,"coverage":.95},
          {"id":"SUPPLEMENT-1","cost":2,"value":4,"coverage":.93},
          {"id":"SUPPLEMENT-2","cost":3,"value":3.5,"coverage":.92}],
      "weaknesses":[{"race_id":r["race_id"],
          "category":"LAB_LONGSHOT_BUCKET","baseline_loss":.6,
          "candidate_loss":.3} for r in f["holdout"]],
      "portfolios":[
          {"id":"LAB-BASE","race_ids":[r["race_id"] for r in f["holdout"]],
            "net_returns_per_unit":[.1,-.2]+[0]*8},
          {"id":"LAB-STRESSED","race_ids":[r["race_id"] for r in f["holdout"]],
            "net_returns_per_unit":[.2,-.1]+[0]*8}],
      "experiments":[{"id":"LAB-EX-A","cost":4,"lab_gain":9},
                     {"id":"LAB-EX-B","cost":3,"lab_gain":7},
                     {"id":"LAB-EX-C","cost":3,"lab_gain":6},
                     {"id":"LAB-EX-D","cost":2,"lab_gain":1}],
      "surprises":[{"id":"LAB-COUNTEREXAMPLE-01",
          "predicted_probability":.85,"outcome":1},
         {"id":"LAB-COUNTEREXAMPLE-02",
          "predicted_probability":.15,"outcome":0}],
      "drift_windows":[{"id":"BASELINE","rate":.6},
                       {"id":"FORWARD-01","rate":.4},
                       {"id":"FORWARD-02","rate":.2}]}
    pkt={"schema":"kyoto_F17_eight_capabilities_lab_input.v1",
         "scope":"LAB_SYNTHETIC_ONLY",
         "research_streams":research,
         "plan_lock_sha256":f["plan"]["sealed_plan_sha256"],
         "race_cutoffs":[r["race_id"] for r in f["holdout"]],
         "evo_inputs":inp,
         "policy":{"source_gain_per_cost_min":1.0,"max_counterfactual_drawdown":.25,
                   "min_retest_counterexamples":1,"max_research_experiments":4,
                   "real_jra_enabled":False,"production_update_enabled":False}}
    pkt["source_sha256"]=dig(pkt)
    return pkt,f

def resign(p):
    p["source_sha256"]=dig({k:v for k,v in p.items() if k!="source_sha256"})

class F17EightIntegrationTests(unittest.TestCase):
 def run_case(self):
    p,f=sample()
    return integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_eight_distinct_executed(self):
    r=self.run_case()
    self.assertEqual(len(r["EVO_results"]),8)
    self.assertEqual(r["evaluated_capabilities"],8)
 def test_evo01_acquisition_prioritization(self):
    self.assertEqual(self.run_case()["EVO_results"]["EVO-01"]["net_research_value"],3.)
 def test_evo02_error_weakness(self):
    self.assertAlmostEqual(self.run_case()["EVO_results"]["EVO-02"]["loss_reduction"],.3)
 def test_evo03_exact_f18_paired(self):
    p,f=sample()
    r=integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
    self.assertAlmostEqual(r["EVO_results"]["EVO-03"]["mean_log_loss_improvement"],
              f["decision"]["holdout_scores"]["candidate_gain_vs_champion_log_loss"])
 def test_evo04_portfolio_cap(self):
    self.assertEqual(self.run_case()["EVO_results"]["EVO-04"]["portfolio_drawdown"],.2)
 def test_evo05_forward_revocation(self):
    self.assertEqual(self.run_case()["EVO_results"]["EVO-05"]["observed_F18_last_state"],
                     "SHADOW_REVOKED_ROLLBACK_TO_CHAMPION")
 def test_evo06_bounded_experiments_executed_only_in_lab(self):
    r=self.run_case()["EVO_results"]["EVO-06"]
    self.assertEqual(r["experiments_run"],3)
    self.assertEqual(set(r["experiments_executed_in_sandbox"]),{"LAB-EX-A","LAB-EX-B","LAB-EX-C"})
    self.assertTrue(r["no_external_research_job_executed"])
 def test_evo07_f18_source_anchor(self):
    p,f=sample()
    self.assertEqual(integrate(p,f18_witness=f,rubric_bytes=RUBRIC)["EVO_results"]["EVO-07"]["plan_sha256"],
                     f["plan"]["sealed_plan_sha256"])
 def test_evo08_requires_counterexample(self):
    self.assertTrue(self.run_case()["EVO_results"]["EVO-08"]["research_hypothesis_only"])
 def test_deterministic(self):
    self.assertEqual(self.run_case(),self.run_case())
 def test_missing_capability_refused(self):
    p,f=sample();del p["evo_inputs"]["EVO-06"];resign(p)
    with self.assertRaisesRegex(F17Rejected,"eight_evo"):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_extra_evo_refused(self):
    p,f=sample();p["evo_inputs"]["EVO-09"]={};resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_mutated_unsealed_refused(self):
    p,f=sample();p["evo_inputs"]["EVO-01"]["source_cost"]=200
    with self.assertRaisesRegex(F17Rejected,"sealed_source_digest"):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_resealed_unprofitable_source_refused(self):
    p,f=sample();p["evo_inputs"]["EVO-01"]["source_cost"]=6;resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_same_races_required_for_shadow(self):
    p,f=sample();p["race_cutoffs"][0]="LAB-WRONG";resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_fake_other_plan_refused(self):
    p,f=sample();p["evo_inputs"]["EVO-07"]["audit_plan_sha256"]="f"*64;resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_unauthorized_expanded_budget_refused(self):
    p,f=sample();p["evo_inputs"]["EVO-06"]["experiment_count"]=9;resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_counterfactual_overdrawdown_refused(self):
    p,f=sample();p["evo_inputs"]["EVO-04"]["drawdown"]=.9;resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_surprise_without_retest_refused(self):
    p,f=sample();p["evo_inputs"]["EVO-08"]["independent_retest"]=False;resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_real_JRA_impersonation_refused(self):
    p,f=sample();p["scope"]="ACTUAL_JRA";resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_incorrect_original_CI_refused(self):
    p,f=sample();f["ci_run_id"]="wrong"
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_unapproved_policy_rewrite_refused(self):
    p,f=sample();p["policy"]["max_counterfactual_drawdown"]=.99;resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_rubric_tamper_refused(self):
    p,f=sample()
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC+b" ")
 def test_resealed_source_summary_without_raw_evidence_refused(self):
    p,f=sample()
    p["evo_inputs"]["EVO-01"]["source_cost"]=1
    resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_resealed_raw_loss_history_mismatch_refused(self):
    p,f=sample()
    p["research_streams"]["weaknesses"][2]["baseline_loss"]=.1
    resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_resealed_raw_counterfactual_change_refused(self):
    p,f=sample()
    p["research_streams"]["portfolios"][0]["net_returns_per_unit"][1]=-.7
    resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_resealed_surprise_counterexample_missing_refused(self):
    p,f=sample()
    p["research_streams"]["surprises"][1]["predicted_probability"]=.01
    resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_resealed_experiment_budget_break_refused(self):
    p,f=sample()
    p["research_streams"]["experiments"][0]["cost"]=7
    resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
 def test_no_real_operations_allowed(self):
    r=self.run_case()
    for k in ("real_JRA_EVO_certification","models_deployed",
              "external_collection_performed","real_bets_authorized"):
        self.assertFalse(r[k])
 def test_evo05_false_shadow_improvement_refused(self):
    p,f=sample();p["evo_inputs"]["EVO-05"]["current_drift"]=.9;resign(p)
    with self.assertRaises(F17Rejected):integrate(p,f18_witness=f,rubric_bytes=RUBRIC)
if __name__=="__main__":unittest.main()
