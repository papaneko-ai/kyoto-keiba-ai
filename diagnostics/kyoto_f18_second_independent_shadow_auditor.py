"""Independent F18 witness auditor without importing the target evolution engine.

Input is an original GitHub CI artifact, pinned by run/head and source bytes.
Recomputes sealed plan, 30 chronological LAB outcomes, tri-model scores,
Bonferroni evidence and two forward-stage SHA-linked shadow decisions.
Rejects rehashed malicious stage reports and false real deployment claims.
This cannot certify improvements on real JRA races.
"""
from __future__ import annotations
import hashlib,json,math
from datetime import datetime,timezone
from math import comb

class F18IndependentRejected(ValueError):pass
RUN="43144148977"
HEAD="5824eaf63217f94d1980472826c0d7faf8add030"
RUBRIC_SHA="92bae5c1d61d6ac00a5380dd8d5e08beb59f96c898b03c05a3c8bf8721ced632"

def digest(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,
                separators=(",",":"),allow_nan=False).encode()).hexdigest()
def require(ok,why):
    if not ok:raise F18IndependentRejected(why)
def clock(t):
    try:x=datetime.fromisoformat(t.replace("Z","+00:00"))
    except (TypeError,ValueError,AttributeError):raise F18IndependentRejected("bad_utc") from None
    require(type(t) is str and t.endswith("Z") and x.utcoffset()==timezone.utc.utcoffset(None),
            "non_utc")
    return x
def scores(rows):
    out={}
    for col in ("champion","candidate","baseline"):
        b=[(r[col+"_probability"]-r["outcome"])**2 for r in rows]
        ll=[-math.log(r[col+"_probability"] if r["outcome"] else
                  1-r[col+"_probability"]) for r in rows]
        out[col+"_brier"]=math.fsum(b)/len(b)
        out[col+"_mean_log_loss"]=math.fsum(ll)/len(ll)
    out["candidate_gain_vs_champion_log_loss"]=out["champion_mean_log_loss"]-out["candidate_mean_log_loss"]
    out["candidate_gain_vs_baseline_log_loss"]=out["baseline_mean_log_loss"]-out["candidate_mean_log_loss"]
    out["candidate_paired_better"]=sum(
      (r["candidate_probability"]-r["outcome"])**2 <
      (r["champion_probability"]-r["outcome"])**2 for r in rows)
    return out
def close_scores(left,right):
    require(set(left)==set(right),"changed_score_schema")
    for k in left:
        require(type(left[k]) in (int,float) and type(right[k]) in (int,float)
           and math.isclose(left[k],right[k],rel_tol=0,abs_tol=1e-12),
           "score_mismatch:"+k)

def verify(witness,rubric):
    require(hashlib.sha256(rubric).hexdigest()==RUBRIC_SHA,"rubric_hash_changed")
    rule=next(x for x in json.loads(rubric)["criteria"] if x["id"]=="F18")
    require(rule["points"]==5 and rule["title"]=="進化認定・安全採否・復帰",
            "fixed_f18_rule_changed")
    require(witness.get("schema")=="kyoto_F18_first_lab_witness.v1"
       and witness.get("ci_run_id")==RUN and witness.get("ci_sha")==HEAD
       and witness.get("source_scope")=="SYNTHETIC_LAB_HOLDOUT_NOT_REAL_JRA"
       and witness.get("production_model_changed") is False
       and witness.get("real_jra_calibration_proven") is False,
       "wrong_original_source_or_fake_live")
    p=witness["plan"];hold=witness["holdout"];stages=witness["forward_monitoring"];decision=witness["decision"]
    plan_hash=p.get("sealed_plan_sha256")
    require(plan_hash==digest({k:v for k,v in p.items() if k!="sealed_plan_sha256"}),
            "sealed_plan_changed")
    require(p.get("baseline")=="LAB-BASELINE-v0"
            and p.get("champion")=="LAB-CHAMPION-v1"
            and p.get("candidate")=="LAB-CHALLENGER-v2"
            and p.get("source_scope")=="LAB_SYNTHETIC_ONLY"
            and p.get("monitoring_window_min_races")==10
            and p.get("declared_drift_max_loss_delta")==.03
            and p.get("comparison_count")==2
            and p.get("decision_review")=="SHADOW_ONLY_EXPLICIT_RESEARCH_REVIEW",
            "fixed_baseline_or_threshold_changed")
    require(len(hold)==10 and len(stages)==2 and
            len(p["holdout_race_ids"])==10,"wrong_original_windows")
    used=set();last=clock(p["plan_locked_utc"])
    def window(rows,ids):
        nonlocal last
        require(len(rows)==10 and len(ids)==10,"missing_races")
        for r,rid in zip(rows,ids):
            require(type(r) is dict and set(r)=={
                "race_id","frozen_utc","result_utc","champion_probability",
                "candidate_probability","baseline_probability","outcome","source_kind"
            },"row_schema_changed")
            require(r["race_id"]==rid and rid not in used
                    and r["source_kind"]=="LAB_SYNTHETIC_ONLY","duplicate_or_forged_source")
            before=clock(r["frozen_utc"]);after=clock(r["result_utc"])
            require(last<before<after,"future_or_overlap")
            last=after
            used.add(rid)
            require(type(r["outcome"]) is int and r["outcome"] in (0,1),"bad_outcome")
            for field in ("champion_probability","candidate_probability","baseline_probability"):
                x=r[field]
                require(type(x) in (int,float) and math.isfinite(x) and 0<x<1,"bad_probability")
    window(hold,p["holdout_race_ids"])
    require(p["holdout_race_ids"]==[r["race_id"] for r in hold],
            "holdout_changed")
    require(all(r["baseline_probability"]==.5 for r in hold),"baseline_changed")
    initial=scores(hold)
    close_scores(initial,decision["holdout_scores"])
    require(initial["candidate_gain_vs_champion_log_loss"]>=p["min_mean_improvement"]*p["comparison_count"]
            and initial["candidate_gain_vs_baseline_log_loss"]>0
            and initial["candidate_paired_better"]/10>=p["min_win_fraction"],
            "holdout_not_qualified")
    # Exact one-sided sign test for all wins, plus multiplicity penalty.
    wins=initial["candidate_paired_better"]
    adjusted=min(1.,p["comparison_count"]*sum(comb(10,k) for k in range(wins,11))/1024)
    require(adjusted<=.05 and wins==10 and decision["first_independent_gate"]=="LAB_ONLY_PASS"
            and decision["initial_shadow_admitted"] is True,
            "independent_candidate_admission_not_supported")
    require(decision["study_plan_sha256"]==plan_hash
            and decision["holdout_sha256"]==digest(hold)
            and decision["schema"]=="kyoto_F18_independent_shadow_monitor_rollback.v1"
            and decision["source_scope"]=="OFFLINE_SYNTHETIC_SEALED_HOLDOUT_ONLY"
            and decision["receipt_sha256"]==digest({k:v for k,v in decision.items() if k!="receipt_sha256"}),
            "target_decision_sha_or_scope_wrong")
    state="SHADOW_CANDIDATE_UNDER_TEST"
    prior=digest({"plan_hash":plan_hash,"holdout_hash":digest(hold),
                  "independent_audit_hash":decision["independent_holdout_receipt_sha256"],
                  "state":state})
    require(len(decision["forward_windows"])==2,"wrong_report_count")
    for i,(window_source,record) in enumerate(zip(stages,decision["forward_windows"]),1):
        require(window_source["window_id"]==f"MONITOR-{i:02d}"
             and window_source["race_ids"]==[r["race_id"] for r in window_source["observations"]],
             "monitor_identity_changed")
        window(window_source["observations"],window_source["race_ids"])
        evidence=scores(window_source["observations"])
        close_scores(evidence,record["scores"])
        delta=evidence["candidate_mean_log_loss"]-evidence["champion_mean_log_loss"]
        if state=="SHADOW_CANDIDATE_UNDER_TEST" and delta>=p["declared_drift_max_loss_delta"]:
            state="SHADOW_REVOKED_ROLLBACK_TO_CHAMPION"
        require(record["state_after"]==state
          and math.isclose(record["observed_candidate_loss_delta"],delta,rel_tol=0,abs_tol=1e-12)
          and record["source_sha256"]==digest(window_source)
          and record["prior_chain_sha256"]==prior
          and record["window_id"]==f"MONITOR-{i:02d}"
          and record["first_utc"]==window_source["observations"][0]["frozen_utc"]
          and record["last_result_utc"]==window_source["observations"][-1]["result_utc"],
          "forward_report_disagrees_with_original")
        require(record["event_sha256"]==digest({k:v for k,v in record.items() if k!="event_sha256"}),
                "forward_chain_hash_changed")
        prior=record["event_sha256"]
    require(state=="SHADOW_REVOKED_ROLLBACK_TO_CHAMPION"
            and decision["final_state"]==state
            and len(used)==30
            and decision["unique_holdout_monitor_races"]==30
            and decision["monitor_chain_head"]==prior,"last_state_or_chain_disagrees")
    for key in ("production_model_changed","auto_deployed","actual_bet_authorized",
                "alternate_auto_promoted","real_jra_model_improvement_verified"):
        require(decision.get(key) is False,"production_scope_forged")
    require(decision["retained_production_champion"]==p["champion"],"champion_was_modified")
    return {"schema":"kyoto_F18_second_independent_offline_shadow_rollback.v1",
            "fixed_gate":"F18","scoped_research_gate_accepted_points":5,
            "first_ci_run_id":int(RUN),"first_ci_head":HEAD,
            "plan_sha256":plan_hash,"source_holdout_sha256":digest(hold),
            "source_first_decision_sha256":decision["receipt_sha256"],
            "verified_holdout_races":10,"verified_forward_races":20,
            "verified_independent_baseline":True,"verified_sign_test_adjusted_p":adjusted,
            "verified_final_state":state,"verified_event_chain_head":prior,
            "independent_method":"isolated original rows, independent log loss/Brier/sign test, interval/state replay",
            "production_model_changed":False,"real_jra_improvement_certified":False,
            "real_bet_authorized":False}
