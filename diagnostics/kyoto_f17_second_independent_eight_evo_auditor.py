"""Second independent F17 EVO 01..08 auditor, no import of target F17 engine.

Recomputes each numeric output, original manifest screening SHA, links to
F18 separately audited original holdout and rollback evidence. Rejects
rehashed fake EVO results and any unwarranted real-world certification.
"""
import hashlib,json,math
from pathlib import Path
from diagnostics.kyoto_f18_second_independent_shadow_auditor import verify as verify_f18
class F17SecondRejected(ValueError):pass
RUN="43148780887"
HEAD="a078afcc3fa4662f53b820ce6459864de38df621"
MANIFEST=Path(__file__).resolve().parents[1]/"docs/diagnostics/kyoto_ai_evolution_requirements_manifest_20261106.json"
NAMES=["EVO-%02d"%i for i in range(1,9)]
FIELDS=[
 ("source_cost","source_coverage","value_gain"),
 ("failure_category","baseline_loss","candidate_loss"),
 ("paired_races","champion_loss","shadow_loss"),
 ("preregistered_portfolios","matched_races","drawdown"),
 ("baseline_drift","current_drift","monitor_windows"),
 ("research_budget","experiment_count","holdout_unused"),
 ("audit_plan_sha256","independent_holdout","certifier_independent"),
 ("surprise_metric","counterexamples","independent_retest")]
def dig(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def ck(ok,msg):
 if not ok:raise F17SecondRejected(msg)
def close(a,b):
 ck(type(a) in (int,float) and type(b) in (int,float) and
    math.isfinite(a) and math.isfinite(b) and
    math.isclose(a,b,abs_tol=1e-12,rel_tol=0),"numeric_evo_mismatch")
def verify(w,rubric):
 ck(w.get("schema")=="kyoto_F17_original_eight_evo_lab_receipt.v1"
    and w.get("ci_run_id")==RUN and w.get("ci_head_sha")==HEAD
    and w.get("scope")=="SYNTHETIC_EVO01_08_F18_RESEARCH_ONLY","original_ci_identity")
 p=w["packet"];f=w["original_F18_lab_witness"];r=w["integrated_result"]
 # The target F17 engine is never called; the independent F18 original auditor
 # validates chronology, 10 unseen + 20 forward racing observations.
 try:audited=verify_f18(f,rubric)
 except Exception as e:raise F17SecondRejected("F18_original_holdout_independent_audit_failed") from e
 ck(audited["verified_holdout_races"]==10 and audited["verified_forward_races"]==20
    and audited["verified_final_state"]=="SHADOW_REVOKED_ROLLBACK_TO_CHAMPION",
    "upstream_F18_incomplete")
 ck(p["schema"]=="kyoto_F17_eight_capabilities_lab_input.v1"
    and p["scope"]=="LAB_SYNTHETIC_ONLY"
    and dig({k:v for k,v in p.items() if k!="source_sha256"})==p["source_sha256"],
    "packet_hash_or_lab_scope")
 ck(p["plan_lock_sha256"]==f["plan"]["sealed_plan_sha256"]==audited["plan_sha256"]
    and p["race_cutoffs"]==[x["race_id"] for x in f["holdout"]],
    "original_F18_plan_and_race_binding_changed")
 inp=p["evo_inputs"];got=r["EVO_results"]
 ck(type(inp) is dict and set(inp)==set(NAMES) and type(got) is dict
    and set(got)==set(NAMES),"not_all_eight_capabilities")
 ck(p["policy"]=={"source_gain_per_cost_min":1.0,"max_counterfactual_drawdown":.25,
                 "min_retest_counterexamples":1,"max_research_experiments":4,
                 "real_jra_enabled":False,"production_update_enabled":False},
    "policy_rewritten")
 original=json.loads(MANIFEST.read_text())
 ck(original["schema"]=="kyoto_evolution.v1" and set(original["features"])==set(NAMES),
    "EVO_approved_manifest_changed")
 screen=[{"id":name,"approved_capability":original["features"][name],
          "required_evidence_fields":list(FIELDS[i]),"missing_fields":[],
          "status":"RESEARCH_HYPOTHESIS_ONLY",
          "candidate_for_independent_falsification":True,"certified":False,
          "promoted":False} for i,name in enumerate(NAMES)]
 screen_payload={"schema":"kyoto_p7_approved_evo_capability_screen.v1",
     "manifest_sha256":hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
     "capabilities":screen,"approved_capability_count":8,
     "research_hypothesis_count":8,
     "independent_evolution_certified":False,"auto_promote":False,
     "prediction_ready":False,"real_bet_authorized":False}
 ck(r["manifest_sha256"]==dig(screen_payload),
    "approved_EVO_screen_receipt_not_grounded")
 # Independently recompute all raw EVO research calculations from sealed rows.
 raw=p.get("research_streams")
 ck(type(raw) is dict and set(raw)=={"sources","weaknesses","portfolios",
    "experiments","surprises","drift_windows"},"raw_research_streams_missing")
 calc=r.get("executed_raw_stream_results")
 ck(type(calc) is dict and r.get("executed_raw_stream_sha256")==dig(raw),
    "raw_stream_sha_not_grounded")
 source=raw["sources"]
 ck(type(source) is list and len(source)==3 and
    len({x["id"] for x in source})==3,"raw_source_set")
 ranked=[]
 for x in source:
    ck(set(x)=={"id","cost","value","coverage"} and
       0<x["cost"] and 0<=x["coverage"]<=1,"source_value_format")
    ranked.append({"id":x["id"],"cost":float(x["cost"]),
       "value":float(x["value"]),"coverage":float(x["coverage"]),
       "net":float(x["value"])-float(x["cost"])})
 ranked.sort(key=lambda x:(-x["net"],x["id"]))
 ck(calc["source_ranking"]==ranked and calc["top_source"]==ranked[0],
    "EVO01_raw_ranking_mismatch")
 weakness=raw["weaknesses"]
 ck(len(weakness)==10 and [x["race_id"] for x in weakness]==p["race_cutoffs"],
    "EVO02_raw_races_wrong")
 groups={}
 for x in weakness:
    ck(set(x)=={"race_id","category","baseline_loss","candidate_loss"},
       "EVO02_raw_row_shape")
    groups.setdefault(x["category"],[]).append(x)
 recomputed=[]
 for label,subset in groups.items():
    recomputed.append({"category":label,"races":len(subset),
       "baseline_loss":math.fsum(z["baseline_loss"] for z in subset)/len(subset),
       "candidate_loss":math.fsum(z["candidate_loss"] for z in subset)/len(subset)})
 recomputed.sort(key=lambda x:(-x["baseline_loss"],x["category"]))
 ck(len(recomputed)==len(calc["weakness_groups"]) and len(recomputed)>0,
    "EVO02_group_shape")
 for expected,observed in zip(recomputed,calc["weakness_groups"]):
    ck(expected["category"]==observed["category"] and
       expected["races"]==observed["races"],"EVO02_group_identity")
    close(expected["baseline_loss"],observed["baseline_loss"])
    close(expected["candidate_loss"],observed["candidate_loss"])
 ck(calc["top_weakness"]==calc["weakness_groups"][0],"EVO02_wrong_weakest_bucket")
 portfolios=raw["portfolios"]
 ck(type(portfolios) is list and len(portfolios)==2,"EVO04_two_strategies")
 sims=[]
 for x in portfolios:
    ck(set(x)=={"id","race_ids","net_returns_per_unit"} and
       x["race_ids"]==p["race_cutoffs"] and len(x["net_returns_per_unit"])==10,
       "EVO04_raw_matched_population")
    total=peak=dd=0.
    for change in x["net_returns_per_unit"]:
        ck(type(change) in (float,int) and math.isfinite(change),"EVO04_raw_numeric")
        total+=change
        peak=max(peak,total)
        dd=max(dd,peak-total)
    sims.append({"id":x["id"],"max_drawdown":dd,"total_net_return":total})
 ck(len(sims)==len(calc["portfolio_simulations"]),"EVO04_simulations_missing")
 for e,o in zip(sims,calc["portfolio_simulations"]):
    ck(e["id"]==o["id"],"EVO04_simulation_identity")
    close(e["max_drawdown"],o["max_drawdown"])
    close(e["total_net_return"],o["total_net_return"])
 close(calc["computed_portfolio_drawdown"],max(x["max_drawdown"] for x in sims))
 drift=raw["drift_windows"]
 ck(len(drift)==3 and [x["id"] for x in drift]==
    ["BASELINE","FORWARD-01","FORWARD-02"],"EVO05_wrong_raw_window")
 ck(calc["drift_observations"]==[x["rate"] for x in drift],
    "EVO05_raw_drifts_disagree")
 experiments=raw["experiments"]
 ck(len(experiments)==4 and len({x["id"] for x in experiments})==4,
    "EVO06_raw_experiments")
 for e in experiments:
    ck(set(e)=={"id","cost","lab_gain"} and e["cost"]>0 and
       e["lab_gain"]>=0,"EVO06_invalid_experiment")
 order=sorted(experiments,key=lambda x:(-x["lab_gain"]/x["cost"],x["id"]))
 budget=10.
 selected=[]
 for e in order:
    if len(selected)>=4:break
    if e["cost"]<=budget:
        budget-=e["cost"];selected.append(e["id"])
 ck(calc["experiment_priority"]==[x["id"] for x in order]
    and calc["executed_lab_experiment_ids"]==selected
    and len(selected)==3,"EVO06_incorrect_experiment_selection")
 close(calc["spent_lab_budget"],10.-budget)
 ck(got["EVO-06"].get("experiments_run")==len(selected)
    and got["EVO-06"].get("experiments_executed_in_sandbox")==selected
    and got["EVO-06"].get("no_external_research_job_executed") is True,
    "EVO06_witness_falsified")
 surprise=raw["surprises"]
 ck(len(surprise)==2 and len({x["id"] for x in surprise})==2,
    "EVO08_raw_counterexamples")
 errors=[]
 counter=[]
 for e in surprise:
    ck(set(e)=={"id","predicted_probability","outcome"}
       and 0<e["predicted_probability"]<1
       and type(e["outcome"]) is int and e["outcome"] in (0,1),
       "EVO08_raw_prediction")
    err=abs(e["predicted_probability"]-e["outcome"])
    errors.append(err)
    if err>=.1:counter.append(e["id"])
 ck(calc["surprise_counterexample_ids"]==counter
    and len(counter)>=1,"EVO08_counterexample_source_missing")
 ck(len(calc["surprise_errors"])==len(errors),"EVO08_error_count")
 for x,y in zip(errors,calc["surprise_errors"]):close(x,y)
 close(calc["surprise_mean_error"],math.fsum(errors)/len(errors))
 # Reconcile independently computed raw observations with all 8 summary values.
 close(got["EVO-01"]["net_research_value"],ranked[0]["net"])
 close(got["EVO-02"]["loss_reduction"],
       recomputed[0]["baseline_loss"]-recomputed[0]["candidate_loss"])
 close(got["EVO-04"]["portfolio_drawdown"],max(x["max_drawdown"] for x in sims))
 close(got["EVO-05"]["drift_reduction"],drift[0]["rate"]-drift[-1]["rate"])
 close(got["EVO-08"]["surprise_metric"],math.fsum(errors)/len(errors))
 ck(got["EVO-08"]["counterexample_count"]==len(counter),"EVO08_count_wrong")
 for i,name in enumerate(NAMES):
    ck(set(inp[name])==set(FIELDS[i]),"EVO_field_schema_changed")
 one=inp["EVO-01"];two=inp["EVO-02"];three=inp["EVO-03"]
 four=inp["EVO-04"];five=inp["EVO-05"];six=inp["EVO-06"]
 seven=inp["EVO-07"];eight=inp["EVO-08"]
 ck(one["source_coverage"]>=.9 and one["source_coverage"]<=1
    and one["source_cost"]>0 and one["value_gain"]>one["source_cost"],"source_value_not_justified")
 close(got["EVO-01"]["net_research_value"],one["value_gain"]-one["source_cost"])
 close(got["EVO-01"]["coverage"],one["source_coverage"])
 ck(got["EVO-01"]["status"]=="LAB_VALUE_RANKED" and got["EVO-01"]["auto_network_fetch"] is False,"EVO01_activity")
 ck(two["failure_category"]=="LAB_LONGSHOT_BUCKET" and two["baseline_loss"]>two["candidate_loss"]
    and got["EVO-02"]["failure_category"]==two["failure_category"]
    and got["EVO-02"]["status"]=="LAB_WEAKNESS_IDENTIFIED","EVO02_evidence")
 close(got["EVO-02"]["loss_reduction"],two["baseline_loss"]-two["candidate_loss"])
 s=f["decision"]["holdout_scores"]
 ck(three["paired_races"]==10 and got["EVO-03"]["holdout_races"]==10
    and got["EVO-03"]["status"]=="LAB_MATCHED_SHADOW_COMPARE","EVO03_race_count")
 close(three["champion_loss"],s["champion_mean_log_loss"])
 close(three["shadow_loss"],s["candidate_mean_log_loss"])
 close(got["EVO-03"]["mean_log_loss_improvement"],
       three["champion_loss"]-three["shadow_loss"])
 ck(four["preregistered_portfolios"]==2 and four["matched_races"]==10
    and 0<=four["drawdown"]<=.25 and got["EVO-04"]["portfolios"]==2
    and got["EVO-04"]["matched_races"]==10
    and got["EVO-04"]["actual_bet_profit"] is None
    and got["EVO-04"]["status"]=="LAB_PRECOMMITTED_COUNTERFACTUAL","EVO04_false_portfolio")
 close(got["EVO-04"]["portfolio_drawdown"],four["drawdown"])
 ck(five["monitor_windows"]==3 and five["baseline_drift"]>five["current_drift"]>=0
    and got["EVO-05"]["observed_F18_last_state"]==audited["verified_final_state"]
    and got["EVO-05"]["status"]=="LAB_FORWARD_DRIFT_AND_REVOCATION","EVO05_drift")
 close(got["EVO-05"]["drift_reduction"],five["baseline_drift"]-five["current_drift"])
 ck(3<=six["experiment_count"]<=4 and six["research_budget"]>0
    and six["holdout_unused"] is True and got["EVO-06"]["experiments_run"]==3
    and got["EVO-06"]["max_experiments"]==six["experiment_count"]
    and got["EVO-06"]["status"]=="LAB_CONSTRAINED_RESEARCH_PROPOSAL","EVO06_budget")
 close(got["EVO-06"]["research_budget"],six["research_budget"])
 ck(seven["audit_plan_sha256"]==audited["plan_sha256"]
    and seven["independent_holdout"] is True and seven["certifier_independent"] is True
    and got["EVO-07"]["plan_sha256"]==audited["plan_sha256"]
    and got["EVO-07"]["original_F18_decision_sha256"]==f["decision"]["receipt_sha256"]
    and got["EVO-07"]["real_JRA_certified"] is False
    and got["EVO-07"]["status"]=="LAB_F18_AUDIT_BOUND","EVO07_F18_binding")
 ck(eight["surprise_metric"]>0 and eight["counterexamples"]>=1
    and eight["independent_retest"] is True
    and got["EVO-08"]["counterexample_count"]==eight["counterexamples"]
    and got["EVO-08"]["research_hypothesis_only"] is True
    and got["EVO-08"]["status"]=="LAB_SURPRISE_COUNTEREXAMPLE_TEST",
    "EVO08_falsifiability")
 close(got["EVO-08"]["surprise_metric"],eight["surprise_metric"])
 ck(r.get("schema")=="kyoto_F17_integrated_research_cycle.v1"
    and r.get("source_scope")=="SYNTHETIC_EVO01_08_WITH_P7_F18_ONLY"
    and r.get("lab_input_sha256")==p["source_sha256"]
    and r.get("F18_audit_sha256")==f["decision"]["receipt_sha256"]
    and r.get("evaluated_capabilities")==8
    and r.get("capability_tested_integration") is True
    and r.get("further_independent_audit_required") is True
    and r.get("receipt_sha256")==dig({k:v for k,v in r.items() if k!="receipt_sha256"}),
    "F17_report_sha_or_semantics")
 for key in ("real_JRA_EVO_certification","models_deployed",
             "external_collection_performed","real_bets_authorized"):
    ck(r.get(key) is False,"false_live_claim")
 return {"schema":"kyoto_F17_second_independent_eight_evo_audit.v1",
         "gate":"F17","scoped_offline_functional_credit":5,
         "first_ci_run_id":int(RUN),"first_ci_head":HEAD,
         "independently_recomputed_capabilities":NAMES,
         "original_packet_sha256":p["source_sha256"],
         "first_F17_receipt_sha256":r["receipt_sha256"],
         "independent_F18_verified_unique_races":30,
         "actual_JRA_evolution_verified":False,
         "production_model_changed":False,
         "real_bet_authorized":False}
