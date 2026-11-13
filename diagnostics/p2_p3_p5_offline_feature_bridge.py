"""P2 -> P3 -> P5 offline feature bridge, no JRA GET, trading, or results leakage.

P2 selected feature names and the complete original discovery receipt are
bound to a frozen evaluation plan. P3 derives strengths from pre-race rows.
P5 cannot allocate without *independently verified* odds and calibration;
therefore this bridge deliberately produces an explicit zero-spend skip.
"""
from __future__ import annotations
from math import fsum,isfinite,prod
from diagnostics.p2_three_way_discovery import discover_interactions
from diagnostics.p3_offline_model_tournament import (
    predict,audit_chronological_holdout,_hash,_utc,TournamentRejected,CANDIDATES)
from diagnostics.p3_lab_calibration_audit import audit_calibration
from diagnostics.p3_p6_research_no_bet import allocate_research_budget

class FeatureBridgeRejected(ValueError):pass
FEATURE_SCHEMA=("course_fit","distance_fit","pace_fit","recent_form")
MAX_STRENGTH=100.0

def _feature_row(snapshot, *, expected_keys):
    if type(snapshot) is not dict or set(snapshot)!={
            "race_id","feature_source_sha256","feature_cutoff_utc",
            "race_start_utc","source_scope","runners"}:
        raise FeatureBridgeRejected("feature_snapshot_schema_invalid")
    if snapshot["source_scope"]!="LAB_OFFLINE_ONLY":
        raise FeatureBridgeRejected("nonlab_source_forbidden")
    if not (_utc(snapshot["feature_cutoff_utc"])<_utc(snapshot["race_start_utc"])):
        raise FeatureBridgeRejected("feature_time_invalid")
    if type(snapshot["runners"]) is not list or not 3<=len(snapshot["runners"])<=18:
        raise FeatureBridgeRejected("feature_runners_invalid")
    seen=set()
    for h in snapshot["runners"]:
        if type(h) is not dict or set(h)!={"number","frame","features"}:
            raise FeatureBridgeRejected("runner_feature_schema_invalid")
        if type(h["number"]) is not int or not 1<=h["number"]<=18 or h["number"] in seen:
            raise FeatureBridgeRejected("runner_number_invalid")
        seen.add(h["number"])
        if type(h["frame"]) is not int or not 1<=h["frame"]<=8:
            raise FeatureBridgeRejected("frame_invalid")
        f=h["features"]
        if type(f) is not dict or set(f)!=set(expected_keys):
            raise FeatureBridgeRejected("feature_missing_or_future_column")
        if any(type(v) not in (int,float) or not isfinite(v) or not 0<=v<=1 for v in f.values()):
            raise FeatureBridgeRejected("feature_values_invalid")
    return snapshot

def frozen_discovery(races,*,train_count,selection_count=2):
    """Reuse original P2 discovery; return names only, not outcome-dependent weights."""
    result=discover_interactions(races,train_count=train_count,selection_count=selection_count)
    names=[tuple(row["features"]) for row in result["selected"]]
    if (len(names)!=len(set(names)) or any(not set(n)<=set(FEATURE_SCHEMA) for n in names)
        or result["future_labels_used_for_selection"] is not False):
        raise FeatureBridgeRejected("feature_discovery_not_eligible")
    body={"schema":"kyoto_p2_p3_feature_lock.v1",
          "feature_schema":list(FEATURE_SCHEMA),
          "selected_keys":[list(n) for n in names],
          "p2_receipt_sha256":_hash(result),
          "p2_input_sha256":result["input_sha256"],
          "training_race_ids":result["race_ids"]["training"],
          "validation_race_ids":result["race_ids"]["validation"],
          "holdout_race_ids":result["race_ids"]["untouched_holdout"],
          "feature_rule":"LAB_POSITIVE_MEAN_OF_FROZEN_HYPOTHESES",
          "research_only":True,"production_eligible":False}
    return {**body,"feature_lock_sha256":_hash(body)}

def feature_forecast_snapshot(frozen_plan, snapshot):
    if type(frozen_plan) is not dict or frozen_plan.get("schema")!="kyoto_p2_p3_feature_lock.v1":
        raise FeatureBridgeRejected("feature_lock_required")
    if _hash({k:v for k,v in frozen_plan.items() if k!="feature_lock_sha256"})!=frozen_plan.get("feature_lock_sha256"):
        raise FeatureBridgeRejected("feature_plan_tampered")
    keys=frozen_plan["selected_keys"]
    if (not keys or any(type(k) is not list or not 1<=len(k)<=2 or
        any(name not in FEATURE_SCHEMA for name in k) for k in keys)
        or frozen_plan.get("feature_schema")!=list(FEATURE_SCHEMA)):
        raise FeatureBridgeRejected("feature_selection_invalid")
    snapshot=_feature_row(snapshot,expected_keys=FEATURE_SCHEMA)
    if snapshot["race_id"] in frozen_plan["training_race_ids"] or snapshot["race_id"] in frozen_plan["validation_race_ids"]:
        raise FeatureBridgeRejected("training_or_validation_reuse")
    # This deterministic transform is frozen before independent outcomes.
    rows=[]
    for runner in snapshot["runners"]:
        f=runner["features"]
        strength=fsum(prod(0.05+f[name] for name in selection) for selection in keys)/len(keys)
        if not 0<strength<=MAX_STRENGTH:
            raise FeatureBridgeRejected("invalid_derived_strength")
        rows.append({"number":runner["number"],"frame":runner["frame"],
                    "prior_strength":strength})
    body={k:snapshot[k] for k in ("race_id","feature_source_sha256",
         "feature_cutoff_utc","race_start_utc","source_scope")}
    body["runners"]=rows
    return body

def evaluate_feature_bridge(plan, training, holdout, *,plan_locked_utc,
                            daily_budget_yen=10000):
    """Predictions are generated from the frozen feature rule, not outcomes.

    Training and evaluation racing IDs and chronology are rechecked by P3.
    No market odds may be invented: all exposure is zero until verified.
    """
    if (type(training) is not list or type(holdout) is not list or
        type(daily_budget_yen) is not int or not 0<=daily_budget_yen<=1_000_000
        or daily_budget_yen%100):
        raise FeatureBridgeRejected("evaluation_input_invalid")
    def convert(rows):
        result=[]
        for row in rows:
            if type(row) is not dict or set(row)!={"snapshot","forecast_frozen_utc",
                                                "outcome_utc","winning_pair"}:
                raise FeatureBridgeRejected("evaluation_row_schema")
            new={**row,"snapshot":feature_forecast_snapshot(plan,row["snapshot"])}
            result.append(new)
        return result
    base_train,base_hold=convert(training),convert(holdout)
    if set(plan["holdout_race_ids"]) & {r["snapshot"]["race_id"] for r in training}:
        raise FeatureBridgeRejected("holdout_training_identity_overlap")
    scores=audit_chronological_holdout(base_train,base_hold,plan_locked_utc=plan_locked_utc)
    calibration=audit_calibration(base_train,base_hold,plan_locked_utc=plan_locked_utc)
    abstain=allocate_research_budget([],daily_limit_yen=daily_budget_yen)
    if abstain["spent_yen"]!=0 or abstain["selected"]:
        raise FeatureBridgeRejected("unverified_market_must_skip")
    body={"schema":"kyoto_p2_p3_p5_offline_bridge.v1",
        "feature_lock_sha256":plan["feature_lock_sha256"],
        "tournament_sha256":scores["receipt_sha256"],
        "calibration_sha256":calibration["audit_sha256"],
        "candidate_family":list(CANDIDATES),
        "training_count":len(base_train),"evaluation_count":len(base_hold),
        "daily_budget_yen":daily_budget_yen,"virtual_exposure_yen":0,
        "unspent_yen":daily_budget_yen,"skip_reason":"NO_VERIFIED_PRERACE_ODDS_OR_CALIBRATED_LIVE_MODEL",
        "independent_jra_evidence":False,"production_model_changed":False,
        "official_settlement_performed":False,"real_bet_authorized":False}
    return {**body,"bridge_sha256":_hash(body)}
