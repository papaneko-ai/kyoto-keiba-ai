"""F18 tri-model sealed LAB shadow promotion and forward drift rollback.

- Research-only. No production model writes, no real JRA claim and no bets.
- Independent sealed holdout (unchanged historical P7 auditor) first qualifies a
  candidate against champion. A third baseline is scored on IDENTICAL races.
- Fresh chronological nonoverlapping monitoring windows can return SHADOW to
  retained champion; an alternate is NEVER silently promoted.
- Exact source/decision hashes enable a separate audit implementation.
"""
from __future__ import annotations
import hashlib,json,math
from datetime import datetime,timezone
from diagnostics.p7_independent_research_certification import independent_research_audit

class F18Rejected(ValueError):pass

def _hash(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _utc(s):
    if type(s) is not str or not s.endswith("Z"):
        raise F18Rejected("utc_z_required")
    try:v=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError:raise F18Rejected("invalid_utc") from None
    if v.utcoffset()!=timezone.utc.utcoffset(None):
        raise F18Rejected("not_utc")
    return v

def _check(c,reason):
    if not c:raise F18Rejected(reason)

def _validate(rows,ids,*,start_after,scope):
    _check(type(rows) is list and type(ids) is list and
           len(rows)==len(ids) and len(rows)>=10 and
           len(set(ids))==len(ids),"window_size_or_identity_invalid")
    last=start_after
    for row,rid in zip(rows,ids):
        _check(type(row) is dict and set(row)=={
            "race_id","frozen_utc","result_utc","champion_probability",
            "candidate_probability","baseline_probability","outcome","source_kind"
        },"window_schema_invalid")
        _check(row["race_id"]==rid and row["source_kind"]==scope,
               "source_or_order_changed")
        cut=_utc(row["frozen_utc"]);result=_utc(row["result_utc"])
        _check(last<cut<result,"future_leakage_or_window_overlap")
        last=result
        y=row["outcome"]
        _check(type(y) is int and y in (0,1),"invalid_outcome")
        for name in ("champion_probability","candidate_probability","baseline_probability"):
            p=row[name]
            _check(type(p) in (float,int) and math.isfinite(p) and 0<p<1,
                   "invalid_probability")
    return last

def _score(rows):
    from math import fsum,log
    scores={}
    for model in ("champion","candidate","baseline"):
        numbers=[-log(r[model+"_probability"] if r["outcome"] else
                      1-r[model+"_probability"]) for r in rows]
        scores[model+"_mean_log_loss"]=fsum(numbers)/len(numbers)
        scores[model+"_brier"]=fsum((r[model+"_probability"]-r["outcome"])**2 for r in rows)/len(rows)
    scores["candidate_gain_vs_champion_log_loss"]=scores["champion_mean_log_loss"]-scores["candidate_mean_log_loss"]
    scores["candidate_gain_vs_baseline_log_loss"]=scores["baseline_mean_log_loss"]-scores["candidate_mean_log_loss"]
    scores["candidate_paired_better"]=sum(
        (r["candidate_probability"]-r["outcome"])**2 <
        (r["champion_probability"]-r["outcome"])**2 for r in rows)
    return scores

def research_shadow_evolution(plan,holdout,monitoring,*,lab_only=True):
    _check(lab_only is True,"real_deployment_not_authorized")
    _check(type(plan) is dict and type(holdout) is list and type(monitoring) is list and len(monitoring)>=2,
           "required_plan_holdout_and_forward_windows")
    _check(plan.get("champion")!=plan.get("candidate") and
           plan.get("baseline") not in (plan.get("champion"),plan.get("candidate"))
           and type(plan.get("baseline")) is str,"three_distinct_models_required")
    _check(plan.get("source_scope")=="LAB_SYNTHETIC_ONLY" and
           plan.get("monitoring_window_min_races")==10 and
           plan.get("declared_drift_max_loss_delta")==0.03 and
           plan.get("decision_review")=="SHADOW_ONLY_EXPLICIT_RESEARCH_REVIEW",
           "unregistered_thresholds_or_scope")
    plan_hash=plan.get("sealed_plan_sha256")
    actual={k:v for k,v in plan.items() if k!="sealed_plan_sha256"}
    _check(type(plan_hash) is str and plan_hash==_hash(actual),"plan_sha_invalid")
    from diagnostics.p7_independent_holdout_research import AuditRejected
    primary={k:plan[k] for k in (
        "champion","candidate","researcher_id","auditor_id",
        "training_end_utc","plan_locked_utc","min_races",
        "min_mean_improvement","min_win_fraction","comparison_count",
        "holdout_race_ids")}
    for row in holdout:
        _check(row.get("source_kind")=="LAB_SYNTHETIC_ONLY"
               and row.get("baseline_probability")==0.5,"holdout_baseline_invalid")
    source_rows=[{k:row[k] for k in (
        "race_id","frozen_utc","result_utc",
        "champion_probability","candidate_probability","outcome")} for row in holdout]
    independent=independent_research_audit(primary,source_rows)
    _validate(holdout,plan["holdout_race_ids"],
              start_after=_utc(plan["plan_locked_utc"]),scope="LAB_SYNTHETIC_ONLY")
    _check(_score(holdout)["candidate_gain_vs_baseline_log_loss"]>0 or
           independent["research_gate"]!="LAB_ONLY_PASS",
           "candidate_not_better_than_baseline")
    admitted=independent["research_gate"]=="LAB_ONLY_PASS"
    state="SHADOW_CANDIDATE_UNDER_TEST" if admitted else "RETAINED_CHAMPION_NOT_ELIGIBLE"
    prior=_hash({"plan_hash":plan_hash,"holdout_hash":_hash(holdout),
                  "independent_audit_hash":independent["audit_sha256"],
                  "state":state})
    prior_window_last=_utc(holdout[-1]["result_utc"])
    used=set(plan["holdout_race_ids"])
    reports=[]
    for window_index,window in enumerate(monitoring,1):
        _check(type(window) is dict and set(window)=={"window_id","race_ids","observations"},
               "monitoring_schema_invalid")
        ids=window["race_ids"];rows=window["observations"]
        _check(type(window["window_id"]) is str and window["window_id"]==f"MONITOR-{window_index:02d}",
               "window_id_invalid")
        _check(not set(ids)&used,"holdout_or_monitoring_reused")
        prior_window_last=_validate(rows,ids,start_after=prior_window_last,
                                    scope="LAB_SYNTHETIC_ONLY")
        used.update(ids)
        score=_score(rows)
        loss_delta=score["candidate_mean_log_loss"]-score["champion_mean_log_loss"]
        if admitted and state=="SHADOW_CANDIDATE_UNDER_TEST":
            if loss_delta>=plan["declared_drift_max_loss_delta"]:
                state="SHADOW_REVOKED_ROLLBACK_TO_CHAMPION"
            else:
                state="SHADOW_CANDIDATE_UNDER_TEST"
        row_out={"window_id":window["window_id"],"first_utc":rows[0]["frozen_utc"],
          "last_result_utc":rows[-1]["result_utc"],"source_sha256":_hash(window),
          "scores":score,"observed_candidate_loss_delta":loss_delta,
          "state_after":state,"prior_chain_sha256":prior}
        row_out["event_sha256"]=_hash(row_out)
        prior=row_out["event_sha256"]
        reports.append(row_out)
    final={
      "schema":"kyoto_F18_independent_shadow_monitor_rollback.v1",
      "source_scope":"OFFLINE_SYNTHETIC_SEALED_HOLDOUT_ONLY",
      "study_plan_sha256":plan_hash,"holdout_sha256":_hash(holdout),
      "independent_holdout_receipt_sha256":independent["audit_sha256"],
      "first_independent_gate":independent["research_gate"],
      "initial_shadow_admitted":admitted,
      "champion":plan["champion"],"candidate":plan["candidate"],"baseline":plan["baseline"],
      "baseline_scored_on_same_holdout":True,
      "holdout_scores":_score(holdout),"forward_windows":reports,
      "unique_holdout_monitor_races":len(used),"final_state":state,
      "retained_production_champion":plan["champion"],
      "monitor_chain_head":prior,
      "alternate_auto_promoted":False,"production_model_changed":False,
      "auto_deployed":False,"real_jra_model_improvement_verified":False,
      "actual_bet_authorized":False,
    }
    return {**final,"receipt_sha256":_hash(final)}
