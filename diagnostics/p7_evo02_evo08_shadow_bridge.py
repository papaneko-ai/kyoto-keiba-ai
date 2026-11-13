"""EVO-02/EVO-08 discovery -> registered challenger -> independent shadow holdout.

All evidence is LAB_SYNTHETIC_ONLY. Training-result errors are analyzed only
after their frozen forecasts are settled. A proposal is locked before a
disjoint holdout is inspected. Reuses the P3/P7 model journal, P7 rollback
guard, and independent proper-score P7 researcher/auditor split. This does
not train a model, deploy one, authenticate JRA or authorize bets.
"""
from __future__ import annotations

from datetime import datetime,timezone
from math import fsum, log, isfinite
from diagnostics.p7_hybrid_model_registry import registered_model,_hash
from diagnostics.p7_hybrid_shadow_evolution_cycle import (
    read_shadow,scored_pairs,ShadowCycleRejected)
from diagnostics.p7_guarded_research_rollback import guard_research_champion
from diagnostics.p7_independent_research_certification import (
    independent_research_audit)

class ProposalRejected(ValueError):
    pass

def _utc(value):
    try:
        if type(value) is not str:
            raise ValueError()
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
        if t.utcoffset()!=timezone.utc.utcoffset(None):
            raise ValueError()
        return t
    except (ValueError,TypeError,AttributeError) as exc:
        raise ProposalRejected("utc_timestamp_required") from exc

def _frozen_label_evidence(state):
    if (len(state["freezes"])<6 or
        len(state["settled"])!=len(state["freezes"]) or state["decisions"]):
        raise ProposalRejected("training_requires_six_settled_undecided_races")
    rows=[]
    for rid,freeze in state["freezes"].items():
        result=state["settled"].get(rid)
        if result is None:
            raise ProposalRejected("training_outcome_missing")
        pair=result["winning_pair"]
        pred=freeze["predictions"]
        winner_probability=[]
        for p in pred:
            matches=[q["probability"] for q in p["quinella"] if q["pair"]==pair]
            if len(matches)!=1:
                raise ProposalRejected("winning_pair_not_in_prediction")
            winner_probability.append(matches[0])
        frames={r["horse_number"]:r["frame_number"] for r in freeze["snapshot"]["runners"]}
        category=("SAME_FRAME" if frames[pair[0]]==frames[pair[1]] else "CROSS_FRAME")
        rows.append({"race_id":rid,"cutoff_utc":freeze["snapshot"]["cutoff_utc"],
            "result_utc":result["outcome_utc"],"error_category":category,
            "champion_loss":-log(max(winner_probability[0],1e-15)),
            "challenger_loss":-log(max(winner_probability[1],1e-15)),
            "champion_winning_pair_probability":winner_probability[0]})
    return rows

def propose_evo02_evo08(training_journal,registry_path,*,champion_id,
                       challenger_id,alternative_id,plan_locked_utc,
                       surprise_ceiling=0.15):
    """Training errors only: locate weakest outcome category and surprises.

    Select a PRE-REGISTERED challenger family, not a synthesized new model.
    No holdout labels are inputs to this function.
    """
    state=read_shadow(training_journal)
    rows=_frozen_label_evidence(state)
    locked=_utc(plan_locked_utc)
    if max(_utc(x["result_utc"]) for x in rows)>=locked:
        raise ProposalRejected("plan_must_follow_all_training_results")
    ids=(champion_id,challenger_id,alternative_id)
    if any(type(s) is not str or not s for s in ids) or len(set(ids))!=3:
        raise ProposalRejected("three_distinct_models_required")
    if not isfinite(surprise_ceiling) or type(surprise_ceiling) not in (float,int) or not 0<surprise_ceiling<1:
        raise ProposalRejected("surprise_ceiling_invalid")
    champ=registered_model(registry_path,champion_id)
    challenger=registered_model(registry_path,challenger_id)
    alternative=registered_model(registry_path,alternative_id)
    if champ["model"]["kind"]!="BASELINE" or challenger["model"]["kind"] not in ("MODIFY","ADD","ENSEMBLE"):
        raise ProposalRejected("model_kinds_incompatible")
    if (len({x["model"]["feature_schema_sha256"] for x in (champ,challenger,alternative)})!=1
        or any(x["model"]["source_scope"]!="LAB_RESEARCH_ONLY" for x in (champ,challenger,alternative))):
        raise ProposalRejected("feature_schema_or_source_mismatch")
    if any(x["predictions"][0]["model_id"]!=champion_id or
           x["predictions"][1]["model_id"]!=challenger_id
           for x in state["freezes"].values()):
        raise ProposalRejected("training_forecast_model_pair_mismatch")
    groups=[]
    for name in ("CROSS_FRAME","SAME_FRAME"):
        sub=[x for x in rows if x["error_category"]==name]
        if sub:
            groups.append({"category":name,"races":len(sub),
                "champion_mean_log_loss":fsum(x["champion_loss"] for x in sub)/len(sub),
                "challenger_mean_log_loss":fsum(x["challenger_loss"] for x in sub)/len(sub)})
    groups.sort(key=lambda x:(-x["champion_mean_log_loss"],x["category"]))
    surprise=[{"race_id":x["race_id"],"probability":x["champion_winning_pair_probability"],
               "category":x["error_category"]} for x in rows
               if x["champion_winning_pair_probability"]<=surprise_ceiling]
    surprise.sort(key=lambda x:(x["probability"],x["race_id"]))
    payload={
        "schema":"kyoto_evo02_evo08_registry_shadow_proposal.v1",
        "scope":"LAB_TRAINING_ONLY_NOT_JRA",
        "training_journal_head_sha256":state["head"],
        "training_race_ids":[x["race_id"] for x in rows],
        "training_result_last_utc":max(_utc(x["result_utc"]) for x in rows).isoformat(),
        "plan_locked_utc":locked.isoformat(),
        "registry_head_sha256":champ["registry_head_sha256"],
        "feature_schema_sha256":champ["model"]["feature_schema_sha256"],
        "champion_id":champion_id,"candidate_id":challenger_id,
        "alternate_id":alternative_id,
        "candidate_kind":challenger["model"]["kind"],
        "evo02_weakness_groups":groups,
        "evo02_priority":groups[0]["category"],
        "evo08_surprise_cases":surprise,
        "evo08_surprise_ceiling":float(surprise_ceiling),
        "proposal_strategy":"TEST_PRE_REGISTERED_CANDIDATE_ON_DISJOINT_HOLDOUT",
        "candidate_generated_or_trained":False,
        "independently_certified":False,
        "production_model_changed":False
    }
    return {**payload,"proposal_sha256":_hash(payload)}

def audit_evo_holdout(proposal,training_journal,holdout_journal,
                      registry_path,*,min_races=10,comparison_count=1):
    """Second lane consumes precommitted proposal and *different* frozen races.

    Independent P7 Brier audit uses the champion's top *pre-result* quinella
    pair as its binary target. Separate P7 rollback lane scores the actual
    winning quinella pair with log loss; BOTH lanes must pass.
    """
    if type(proposal) is not dict or "proposal_sha256" not in proposal:
        raise ProposalRejected("proposal_missing")
    if _hash({k:v for k,v in proposal.items() if k!="proposal_sha256"})!=proposal["proposal_sha256"]:
        raise ProposalRejected("proposal_hash_mismatch")
    if type(min_races) is not int or min_races<10 or type(comparison_count) is not int or not 1<=comparison_count<=8:
        raise ProposalRejected("holdout_sample_or_multiplicity_invalid")
    training=read_shadow(training_journal)
    held=read_shadow(holdout_journal)
    if training["head"]!=proposal["training_journal_head_sha256"]:
        raise ProposalRejected("training_rewritten_since_plan")
    if registered_model(registry_path,proposal["candidate_id"])["registry_head_sha256"]!=proposal["registry_head_sha256"]:
        raise ProposalRejected("model_registry_changed_since_plan")
    if (len(held["freezes"])<min_races or len(held["settled"])!=len(held["freezes"])
        or held["decisions"]):
        raise ProposalRejected("holdout_incomplete_or_prejudged")
    if set(held["freezes"]) & set(training["freezes"]):
        raise ProposalRejected("holdout_training_race_overlap")
    lock=_utc(proposal["plan_locked_utc"])
    first=_utc(next(iter(held["freezes"].values()))["snapshot"]["cutoff_utc"])
    if first<=lock:
        raise ProposalRejected("holdout_started_before_proposal_lock")
    champion=proposal["champion_id"];candidate=proposal["candidate_id"]
    if any(f["predictions"][0]["model_id"]!=champion or
           f["predictions"][1]["model_id"]!=candidate for f in held["freezes"].values()):
        raise ProposalRejected("holdout_forecast_model_mismatch")
    independent_rows=[]
    for rid,freeze in held["freezes"].items():
        result=held["settled"][rid]
        start=_utc(freeze["snapshot"]["cutoff_utc"])
        outcome=_utc(result["outcome_utc"])
        if outcome<=start:
            raise ProposalRejected("label_before_forecast")
        champ,cand=freeze["predictions"]
        top=sorted(champ["quinella"],key=lambda r:(-r["probability"],r["pair"]))[0]["pair"]
        top_p=next(r["probability"] for r in champ["quinella"] if r["pair"]==top)
        next_p=next(r["probability"] for r in cand["quinella"] if r["pair"]==top)
        if any(type(p) not in (float,int) or not 0<p<1 for p in (top_p,next_p)):
            raise ProposalRejected("independent_binary_probability_invalid")
        independent_rows.append({
            "race_id":rid,"frozen_utc":freeze["snapshot"]["cutoff_utc"],
            "result_utc":result["outcome_utc"],
            "champion_probability":top_p,"candidate_probability":next_p,
            "outcome":int(top==result["winning_pair"])})
    plan={"champion":champion,"candidate":candidate,
        "researcher_id":"LAB-EVO02-EVO08-PROPOSAL",
        "auditor_id":"LAB-INDEPENDENT-P7-SCORER",
        "training_end_utc":proposal["training_result_last_utc"],
        "plan_locked_utc":proposal["plan_locked_utc"],
        "min_races":min_races,"min_mean_improvement":0.01,
        "min_win_fraction":0.75,"comparison_count":comparison_count,
        "holdout_race_ids":list(held["freezes"])}
    independent=independent_research_audit(plan,independent_rows)
    guard=guard_research_champion(champion=champion,candidate=candidate,
        alternate=proposal["alternate_id"],
        observations=scored_pairs(holdout_journal),min_races=min_races,
        min_mean_improvement=0.01,min_paired_win_fraction=0.75)
    eligible=(independent["research_gate"]=="LAB_ONLY_PASS" and
              guard["decision"]=="SHADOW_CANDIDATE_ELIGIBLE_FOR_INDEPENDENT_AUDIT")
    payload={"schema":"kyoto_evo02_evo08_independent_shadow_audit.v1",
        "scope":"LAB_ONLY_NOT_AUTHENTICATED_OFFICIAL",
        "proposal_sha256":proposal["proposal_sha256"],
        "training_journal_head_sha256":training["head"],
        "holdout_journal_head_sha256":held["head"],
        "holdout_race_count":len(held["freezes"]),
        "independent_brier_audit_sha256":independent["audit_sha256"],
        "logloss_guard_sha256":guard["decision_sha256"],
        "independent_brier_gate":independent["research_gate"],
        "logloss_guard":guard["decision"],
        "decision":("LAB_SHADOW_ELIGIBLE_FOR_FURTHER_AUDIT" if eligible
                    else "LAB_REJECT_RETAIN_CHAMPION"),
        "retained_champion_id":champion,
        "candidate_promoted":False,"auto_deploy":False,
        "real_JRA_effectiveness_verified":False,
        "real_bet_authorized":False}
    return {**payload,"audit_sha256":_hash(payload)}
