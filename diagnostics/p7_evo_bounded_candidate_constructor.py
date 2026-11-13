"""Bounded EVO02/08 candidate *construction* from LAB frozen training only.

Fits one frame-group probability multiplier over predeclared bps grid, derives
quinella and bracket probabilities from identical frozen champion outputs,
registers a new MODIFY algorithm version, and freezes the created predictor
before separate holdout labels. This is a real executable bounded formula,
NOT arbitrary code generation, JRA verification or deployable training.
"""
from __future__ import annotations
from math import fsum,log,isfinite
from datetime import datetime,timezone
from diagnostics.p7_hybrid_model_registry import (
    registered_model,register_model,read_registry,_hash)
from diagnostics.p3_hybrid_prediction_contract import check_lab_prediction
from diagnostics.p7_hybrid_shadow_evolution_cycle import read_shadow
from diagnostics.kyoto_f17_executable_lab_streams import summarize_frozen_evo02_evo08_errors
from diagnostics.p7_evo02_evo08_shadow_bridge import _frozen_label_evidence

class CandidateBuildRejected(ValueError): pass

GRID_BPS=(500,750,1000,1250,1500,2000,3000)
FORMULA="LAB_FRAME_GROUP_MULTIPLIER_V1"
MODEL_CODE_SHA256=_hash({"formula":FORMULA,"grid":list(GRID_BPS),
    "normalization":"pairwise_then_frame_aggregate"})

def _utc(v):
    try:
        if type(v) is not str:raise ValueError()
        t=datetime.fromisoformat(v.replace("Z","+00:00"))
        if t.utcoffset()!=timezone.utc.utcoffset(None):raise ValueError()
        return t
    except (ValueError,TypeError,AttributeError) as exc:
        raise CandidateBuildRejected("UTC_required") from exc

def _probability_pairs(snapshot,base,category,multiplier_bps):
    frames={r["horse_number"]:r["frame_number"] for r in snapshot["runners"]}
    weights=[]
    for item in base["quinella"]:
        pair=item["pair"]
        group="SAME_FRAME" if frames[pair[0]]==frames[pair[1]] else "CROSS_FRAME"
        factor=multiplier_bps/1000 if group==category else 1.0
        weights.append(item["probability"]*factor)
    norm=fsum(weights)
    if not isfinite(norm) or norm<=0:
        raise CandidateBuildRejected("candidate_total_mass_invalid")
    numbers=[]
    grouped={}
    for row,weight in zip(base["quinella"],weights):
        p=weight/norm
        numbers.append({"pair":list(row["pair"]),"probability":p})
        key=tuple(sorted((frames[row["pair"][0]],frames[row["pair"][1]])))
        grouped[key]=grouped.get(key,0.0)+p
    return numbers,[{"pair":list(k),"probability":v} for k,v in sorted(grouped.items())]

def _candidate_prediction(snapshot,base,*,model_id,category,multiplier_bps):
    q,b=_probability_pairs(snapshot,base,category,multiplier_bps)
    return {"model_id":model_id,"source_sha256":snapshot["source_sha256"],
            "feature_schema_sha256":snapshot["feature_schema_sha256"],
            "cutoff_utc":snapshot["cutoff_utc"],
            "quinella":q,"bracket":b}

def construct_lab_candidate(training_path,registry_path,*,base_id,new_id,
                            plan_locked_utc,min_improvement=0.005):
    """Choose the best of the predeclared finite grid with training labels only.

    No challenger training labels, holdout labels or additional JRA source GET.
    A candidate with no minimum gain is explicitly rejected and not registered.
    """
    state=read_shadow(training_path)
    rows=_frozen_label_evidence(state)
    if len(rows)<6 or any(_utc(r["result_utc"])>=_utc(plan_locked_utc) for r in rows):
        raise CandidateBuildRejected("training_result_or_plan_lock_invalid")
    if type(min_improvement) not in (int,float) or not isfinite(min_improvement) or not 0<min_improvement<1:
        raise CandidateBuildRejected("minimum_training_gain_invalid")
    model=registered_model(registry_path,base_id)
    if model["model"]["kind"]!="BASELINE" or model["model"]["source_scope"]!="LAB_RESEARCH_ONLY":
        raise CandidateBuildRejected("baseline_model_required")
    if type(new_id) is not str or not new_id.startswith("LAB-GEN-"):
        raise CandidateBuildRejected("generated_lab_id_required")
    if any(x["predictions"][0]["model_id"]!=base_id for x in state["freezes"].values()):
        raise CandidateBuildRejected("training_baseline_anchor_mismatch")
    if any(x["registry_head_sha256"]!=model["registry_head_sha256"]
           for x in state["freezes"].values()):
        raise CandidateBuildRejected("registry_changed_since_training")
    analysis=summarize_frozen_evo02_evo08_errors(rows)
    categories=("SAME_FRAME","CROSS_FRAME")
    baseline=fsum(x["champion_loss"] for x in rows)/len(rows)
    trials=[]
    for group in categories:
        for factor in GRID_BPS:
            if factor==1000:continue
            losses=[]
            for rid,freeze in state["freezes"].items():
                result=state["settled"][rid]
                q,_=_probability_pairs(freeze["snapshot"],freeze["predictions"][0],
                                      group,factor)
                matches=[p["probability"] for p in q if p["pair"]==result["winning_pair"]]
                if len(matches)!=1:
                    raise CandidateBuildRejected("winner_pair_not_in_training_output")
                losses.append(-log(max(matches[0],1e-15)))
            mean=fsum(losses)/len(losses)
            trials.append({"category":group,"factor_bps":factor,
                           "mean_training_log_loss":mean,
                           "mean_gain":baseline-mean})
    best=sorted(trials,key=lambda x:(-x["mean_gain"],x["category"],x["factor_bps"]))[0]
    if best["mean_gain"]<min_improvement:
        return {"state":"NO_CANDIDATE_BASELINE_RETAINED",
                "training_journal_head_sha256":state["head"],
                "training_mean_log_loss":baseline,
                "best_provisional_gain":best["mean_gain"],
                "trial_count":len(trials),"registered":False,
                "production_model_changed":False,
                "real_JRA_certified":False}
    config={"formula":FORMULA,"category":best["category"],
            "factor_bps":best["factor_bps"],"source_baseline_id":base_id,
            "training_journal_head_sha256":state["head"],
            "selection_trial_count":len(trials)}
    spec={"model_id":new_id,"kind":"MODIFY","parents":[base_id],
          "feature_schema_sha256":model["model"]["feature_schema_sha256"],
          "code_sha256":MODEL_CODE_SHA256,
          "configuration_sha256":_hash(config),
          "training_end_utc":max(_utc(r["result_utc"]) for r in rows).isoformat(),
          "source_scope":"LAB_RESEARCH_ONLY","weights_bps":[]}
    receipt=register_model(registry_path,spec)
    proposal={
        "schema":"kyoto_evo_generated_frame_candidate.v1",
        "scope":"LAB_RESEARCH_ONLY",
        "plan_locked_utc":_utc(plan_locked_utc).isoformat(),
        "training_journal_head_sha256":state["head"],
        "post_registration_registry_head_sha256":read_registry(registry_path)["head"],
        "evo02_weakness":analysis["evo02_priority"],
        "evo08_surprise_race_ids":[x["race_id"] for x in analysis["evo08_surprise_cases"]],
        "generated_model_id":new_id,"baseline_id":base_id,
        "configuration":config,"configuration_sha256":_hash(config),
        "code_sha256":MODEL_CODE_SHA256,
        "model_spec":spec,
        "training_mean_log_loss":baseline,
        "candidate_training_mean_log_loss":best["mean_training_log_loss"],
        "training_gain":best["mean_gain"],
        "trial_count":len(trials),
        "candidate_constructed":True,
        "independent_audit_passed":False,"production_model_changed":False,
        "real_JRA_certified":False}
    return {**proposal,"proposal_sha256":_hash(proposal),
            "registry_receipt_sha256":receipt["event_sha256"]}

def forecast_lab_generated(proposal,registry_path,snapshot,baseline_forecast):
    """No results accepted. Enforce locked registry and same-cutoff P3 contract."""
    if type(proposal) is not dict or proposal.get("schema")!="kyoto_evo_generated_frame_candidate.v1":
        raise CandidateBuildRejected("generated_proposal_required")
    payload={k:v for k,v in proposal.items() if k not in ("proposal_sha256","registry_receipt_sha256")}
    if _hash(payload)!=proposal.get("proposal_sha256"):
        raise CandidateBuildRejected("proposal_modified")
    reg=registered_model(registry_path,proposal["generated_model_id"])
    if (reg["registry_head_sha256"]!=proposal["post_registration_registry_head_sha256"]
        or reg["model"]!=proposal["model_spec"]):
        raise CandidateBuildRejected("generated_registry_version_drift")
    check_lab_prediction(registry_path,snapshot,baseline_forecast)
    if baseline_forecast["model_id"]!=proposal["baseline_id"]:
        raise CandidateBuildRejected("wrong_base_prediction")
    if _utc(snapshot["cutoff_utc"])<=_utc(proposal["plan_locked_utc"]):
        raise CandidateBuildRejected("holdout_not_after_plan_lock")
    config=proposal["configuration"]
    if _hash(config)!=proposal["configuration_sha256"] or config["formula"]!=FORMULA:
        raise CandidateBuildRejected("config_not_authorized")
    if config["factor_bps"] not in GRID_BPS or config["category"] not in ("SAME_FRAME","CROSS_FRAME"):
        raise CandidateBuildRejected("unsupported_candidate_formula")
    prediction=_candidate_prediction(snapshot,baseline_forecast,
        model_id=proposal["generated_model_id"],
        category=config["category"],multiplier_bps=config["factor_bps"])
    check_lab_prediction(registry_path,snapshot,prediction)
    return prediction
