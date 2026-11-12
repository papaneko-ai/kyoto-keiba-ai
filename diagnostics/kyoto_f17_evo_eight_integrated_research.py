"""EVO-01..08 integrated, research-only analytical cycle.

All eight APPROVED EVO IDs must produce distinct numerical effects on a
single sealed synthetic research packet. Ties the EVO-07 audit to the exact
F18 source/decision witness. No external operations, JRA claim, promotion,
source collection, real wagering or autocode mutation.
"""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path
from diagnostics.p7_approved_evo_capability_screen import (
    falsify_research_candidates,EXPECTED
)

class F17Rejected(ValueError):pass
def dig(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()
def ck(test,why):
    if not test:raise F17Rejected(why)
def numeric(x):
    ck(type(x) in (int,float) and math.isfinite(x) and x>=0,"nonfinite_or_negative")
    return float(x)

def integrate(packet,*,f18_witness,rubric_bytes):
    ck(type(packet) is dict and set(packet)=={
        "schema","scope","plan_lock_sha256","race_cutoffs",
        "evo_inputs","policy","source_sha256"},"packet_schema")
    ck(packet["schema"]=="kyoto_F17_eight_capabilities_lab_input.v1"
       and packet["scope"]=="LAB_SYNTHETIC_ONLY","source_scope")
    ck(dig({k:v for k,v in packet.items() if k!="source_sha256"})==packet["source_sha256"],
       "sealed_source_digest")
    ck(type(rubric_bytes) is bytes and
       hashlib.sha256(rubric_bytes).hexdigest()=="92bae5c1d61d6ac00a5380dd8d5e08beb59f96c898b03c05a3c8bf8721ced632",
       "fixed_rubric_changed")
    criteria=json.loads(rubric_bytes)["criteria"]
    ck(next(x for x in criteria if x["id"]=="F17")["points"]==5,"rubric_F17_changed")
    inputs=packet["evo_inputs"]
    ck(type(inputs) is dict and set(inputs)==set(EXPECTED),"eight_evo_inputs_required")
    policy=packet["policy"]
    ck(policy=={"source_gain_per_cost_min":1.0,"max_counterfactual_drawdown":0.25,
                "min_retest_counterexamples":1,"max_research_experiments":4,
                "real_jra_enabled":False,"production_update_enabled":False},
       "unapproved_evo_policy")
    ck(type(f18_witness) is dict and f18_witness.get("schema")=="kyoto_F18_first_lab_witness.v1"
       and f18_witness.get("source_scope")=="SYNTHETIC_LAB_HOLDOUT_NOT_REAL_JRA"
       and f18_witness.get("ci_run_id")=="43144148977"
       and f18_witness.get("ci_sha")=="5824eaf63217f94d1980472826c0d7faf8add030",
       "unverified_F18_origin")
    decision=f18_witness["decision"]
    ck(decision.get("schema")=="kyoto_F18_independent_shadow_monitor_rollback.v1"
       and decision.get("receipt_sha256")==dig({k:v for k,v in decision.items() if k!="receipt_sha256"})
       and decision.get("first_independent_gate")=="LAB_ONLY_PASS"
       and decision.get("final_state")=="SHADOW_REVOKED_ROLLBACK_TO_CHAMPION"
       and decision.get("production_model_changed") is False
       and decision.get("real_jra_model_improvement_verified") is False,
       "F18_lifecycle_not_reproducible")
    ck(packet["plan_lock_sha256"]==decision["study_plan_sha256"]==
       f18_witness["plan"]["sealed_plan_sha256"],"independent_F18_plan_binding_invalid")
    source_cutoffs=packet["race_cutoffs"]
    ck(type(source_cutoffs) is list and source_cutoffs==[
         r["race_id"] for r in f18_witness["holdout"]],"F18_same_holdout_mismatch")
    proposals=falsify_research_candidates(inputs)
    ck([r["id"] for r in proposals["results"]]==list(EXPECTED),"screen_order_changed")
    ck(all(r["verdict"]=="NOT_REFUTED_RESEARCH_ONLY" for r in proposals["results"]),
       "capability_independent_counterexample_fail")
    a=inputs
    # EVO-01: rank supplementary fetches by measured value net of costs
    one=a["EVO-01"]
    gain=numeric(one["value_gain"]);cost=numeric(one["source_cost"])
    coverage=numeric(one["source_coverage"])
    ck(0.9<=coverage<=1 and cost>0 and gain/cost>policy["source_gain_per_cost_min"],"EVO01_budget_or_coverage")
    fetch_value=gain-cost
    # EVO-02: measure comparative error and reject unchanged or worse class
    two=a["EVO-02"]
    ck(two["failure_category"]=="LAB_LONGSHOT_BUCKET","EVO02_unregistered_failure_category")
    error_reduction=numeric(two["baseline_loss"])-numeric(two["candidate_loss"])
    ck(error_reduction>0,"EVO02_weakness_not_reduced")
    # EVO-03: shadow vs champion on exactly the same ten sealed F18 races
    three=a["EVO-03"]
    count=three["paired_races"]
    ck(type(count) is int and count==len(source_cutoffs),"EVO03_paired_population_changed")
    shadow_gain=numeric(three["champion_loss"])-numeric(three["shadow_loss"])
    scores=decision["holdout_scores"]
    ck(math.isclose(float(three["champion_loss"]),scores["champion_mean_log_loss"],abs_tol=1e-12,rel_tol=0)
       and math.isclose(float(three["shadow_loss"]),scores["candidate_mean_log_loss"],abs_tol=1e-12,rel_tol=0)
       and shadow_gain>0,"EVO03_F18_original_score_divergence")
    # EVO-04: frozen comparative portfolios and max loss. No fake P&L.
    four=a["EVO-04"]
    ck(type(four["preregistered_portfolios"]) is int and four["preregistered_portfolios"]==2
       and type(four["matched_races"]) is int and four["matched_races"]==count,"EVO04_portfolio_populations")
    drawdown=numeric(four["drawdown"])
    ck(drawdown<=policy["max_counterfactual_drawdown"],"EVO04_drawdown_limit")
    # EVO-05: forward monitoring MUST use F18's independent windows and drift
    five=a["EVO-05"]
    ck(type(five["monitor_windows"]) is int and five["monitor_windows"]==3,"EVO05_windows_required")
    baseline=numeric(five["baseline_drift"]);current=numeric(five["current_drift"])
    ck(current<baseline and decision["forward_windows"][-1]["state_after"]==
       "SHADOW_REVOKED_ROLLBACK_TO_CHAMPION","EVO05_forward_drift_disagrees")
    # EVO-06: constrained research proposal, never self-run
    six=a["EVO-06"]
    count_experiments=six["experiment_count"]
    ck(type(count_experiments) is int and 3<=count_experiments<=policy["max_research_experiments"]
       and numeric(six["research_budget"])>0 and six["holdout_unused"] is True,
       "EVO06_resource_or_unseen_holdout_violation")
    # EVO-07: binding original independent F18 source hash; attestation is
    # a research receipt, NOT approval to deploy.
    seven=a["EVO-07"]
    ck(seven["audit_plan_sha256"]==packet["plan_lock_sha256"]
       and seven["independent_holdout"] is True
       and seven["certifier_independent"] is True,"EVO07_original_audit_binding")
    # EVO-08: surprise MUST still carry counterexample and external retest
    eight=a["EVO-08"]
    surprise=numeric(eight["surprise_metric"])
    ck(surprise>0 and type(eight["counterexamples"]) is int
       and eight["counterexamples"]>=policy["min_retest_counterexamples"]
       and eight["independent_retest"] is True,"EVO08_surprise_not_falsifiable")
    values={
       "EVO-01":{"status":"LAB_VALUE_RANKED","net_research_value":fetch_value,
                 "coverage":coverage,"auto_network_fetch":False},
       "EVO-02":{"status":"LAB_WEAKNESS_IDENTIFIED","failure_category":two["failure_category"],
                 "loss_reduction":error_reduction},
       "EVO-03":{"status":"LAB_MATCHED_SHADOW_COMPARE","holdout_races":count,
                 "mean_log_loss_improvement":shadow_gain},
       "EVO-04":{"status":"LAB_PRECOMMITTED_COUNTERFACTUAL","portfolios":2,
                 "matched_races":count,"portfolio_drawdown":drawdown,
                 "actual_bet_profit":None},
       "EVO-05":{"status":"LAB_FORWARD_DRIFT_AND_REVOCATION",
                 "drift_reduction":baseline-current,
                 "observed_F18_last_state":decision["final_state"]},
       "EVO-06":{"status":"LAB_CONSTRAINED_RESEARCH_PROPOSAL",
                 "max_experiments":count_experiments,
                 "research_budget":float(six["research_budget"]),
                 "experiments_run":0},
       "EVO-07":{"status":"LAB_F18_AUDIT_BOUND",
                 "plan_sha256":packet["plan_lock_sha256"],
                 "original_F18_decision_sha256":decision["receipt_sha256"],
                 "real_JRA_certified":False},
       "EVO-08":{"status":"LAB_SURPRISE_COUNTEREXAMPLE_TEST",
                 "surprise_metric":surprise,"counterexample_count":eight["counterexamples"],
                 "research_hypothesis_only":True}
    }
    ck(set(values)==set(EXPECTED),"EVO_missing")
    output={"schema":"kyoto_F17_integrated_research_cycle.v1",
            "source_scope":"SYNTHETIC_EVO01_08_WITH_P7_F18_ONLY",
            "manifest_sha256":proposals["screen_receipt_sha256"],
            "lab_input_sha256":packet["source_sha256"],
            "F18_audit_sha256":decision["receipt_sha256"],
            "EVO_results":values,"evaluated_capabilities":8,
            "capability_tested_integration":True,
            "real_JRA_EVO_certification":False,"models_deployed":False,
            "external_collection_performed":False,"real_bets_authorized":False,
            "further_independent_audit_required":True}
    return {**output,"receipt_sha256":dig(output)}
