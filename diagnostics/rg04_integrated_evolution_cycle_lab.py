"""RG-04B: training-only HYP discovery -> precommitted frozen holdout ->
independent P7 research audit -> existing rollback guard.

No JRA, production model mutation, alternate auto-promotion or real betting.
This is a LAB protocol verifier, NOT EVO-01..08 qualification.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import log
from diagnostics.p7_evo_candidate_falsification import (
    discover_and_refute, EVO_RULES
)
from diagnostics.p7_independent_research_certification import independent_research_audit
from diagnostics.p7_guarded_research_rollback import guard_research_champion

class EvolutionIntegrationRejected(ValueError): pass

def _utc(s):
    try:
        if type(s) is not str: raise ValueError()
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
        if t.utcoffset()!=timezone.utc.utcoffset(None): raise ValueError()
        return t
    except (ValueError,TypeError,AttributeError):
        raise EvolutionIntegrationRejected("UTC_timestamp_required")

def _hash(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
            separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _prepare(rows):
    if type(rows) is not list:
        raise EvolutionIntegrationRejected("records_not_a_list")
    last_cut=None
    seen=set()
    result=[]
    for record in rows:
        if type(record) is not dict or set(record)!={"frozen","outcome"}:
            raise EvolutionIntegrationRejected("split_freeze_outcome_required")
        frozen=record["frozen"];outcome=record["outcome"]
        if type(frozen) is not dict or set(frozen)!={"race_id","cutoff_utc","source_kind","runners","sha256"}:
            raise EvolutionIntegrationRejected("frozen_schema_invalid")
        if type(outcome) is not dict or set(outcome)!={"race_id","result_utc","winner","source_kind"}:
            raise EvolutionIntegrationRejected("result_schema_invalid")
        if frozen["source_kind"]!="LAB_SYNTHETIC_ONLY" or outcome["source_kind"]!="LAB_SYNTHETIC_ONLY":
            raise EvolutionIntegrationRejected("nonlab_provenance_forbidden")
        content={k:v for k,v in frozen.items() if k!="sha256"}
        if type(frozen["sha256"]) is not str or _hash(content)!=frozen["sha256"]:
            raise EvolutionIntegrationRejected("frozen_features_tampered")
        rid=frozen["race_id"]
        if type(rid) is not str or not rid.startswith("LAB-") or rid in seen or outcome["race_id"]!=rid:
            raise EvolutionIntegrationRejected("duplicate_or_mismatched_race")
        seen.add(rid)
        cut=_utc(frozen["cutoff_utc"]); result_at=_utc(outcome["result_utc"])
        if last_cut is not None and cut<=last_cut:
            raise EvolutionIntegrationRejected("cutoffs_not_chronological")
        last_cut=cut
        if cut>=result_at:
            raise EvolutionIntegrationRejected("outcome_before_cutoff")
        race={"race_id":rid,"cutoff_utc":frozen["cutoff_utc"],
              "pre_result_frozen":True,"runners":frozen["runners"],
              "winner":outcome["winner"]}
        result.append((race,cut,result_at))
    return result

def research_evolution_cycle(training, holdout, *, plan_locked_utc,
                             champion="LAB-CHAMPION", alternate="LAB-ALTERNATE",
                             comparison_count=1):
    """Only training labels select HYP rule. Holdout is scored after lock.

    The holdout outcome never selects the rule or a threshold.
    The fixed-probability LAB challenger is a test of wiring, not a fitted model.
    """
    if type(training) is not list or len(training)<6 or type(holdout) is not list or len(holdout)<10:
        raise EvolutionIntegrationRejected("six_training_and_ten_holdout_required")
    tr=_prepare(training);ho=_prepare(holdout)
    lock=_utc(plan_locked_utc)
    if tr[-1][2]>=lock or lock>=ho[0][1]:
        raise EvolutionIntegrationRejected("model_lock_must_follow_training_results_before_holdout")
    if any(tr[i][2]>=tr[i+1][1] for i in range(len(tr)-1)):
        raise EvolutionIntegrationRejected("training_result_not_available_for_next_race")
    if any(ho[i][2]>=ho[i+1][1] for i in range(len(ho)-1)):
        raise EvolutionIntegrationRejected("holdout_result_not_available_for_next_race")
    if tr[-1][1]>=ho[0][1] or set(r[0]["race_id"] for r in tr)&set(r[0]["race_id"] for r in ho):
        raise EvolutionIntegrationRejected("train_holdout_overlap")
    # Candidate family is predefined in existing P7 HYP, and selected on
    # training + *internal* validation only, never on external holdout.
    discovery=discover_and_refute([r[0] for r in tr],train_count=3)
    survivors=[r for r in discovery["candidates"] if r["verdict"]=="SURVIVED_SYNTHETIC_HOLDOUT_ONLY"]
    if not survivors:
        return {"schema":"kyoto_rg04_research_cycle.v1",
                "verdict":"NO_RESEARCH_CANDIDATE_RETAIN_CHAMPION",
                "retained_champion":champion, "alternate_promoted":False,
                "production_changed":False,"real_operational_credit":False,
                "auto_deploy":False}
    chosen=survivors[0]
    feature=chosen["feature"]
    candidate="LAB-CANDIDATE-"+chosen["id"]
    names={champion,candidate,alternate}
    if len(names)!=3 or any(type(n) is not str or not n for n in names):
        raise EvolutionIntegrationRejected("model_id_conflict")
    if type(comparison_count) is not int or comparison_count<1:
        raise EvolutionIntegrationRejected("multiplicity_invalid")
    ids=[r[0]["race_id"] for r in ho]
    # This plan is only a LAB self-consistency receipt, not external
    # timestamp notarization. Thresholds fixed BEFORE holdout scoring.
    plan={"champion":champion,"candidate":candidate,
          "researcher_id":"LAB-CANDIDATE-CONSTRUCTOR",
          "auditor_id":"LAB-INDEPENDENT-SCORER",
          "training_end_utc":tr[-1][2].isoformat(),
          "plan_locked_utc":lock.isoformat(),
          "min_races":10,"min_mean_improvement":0.01,
          "min_win_fraction":0.75,"comparison_count":comparison_count,
          "holdout_race_ids":ids}
    observations=[]
    paired=[]
    for race,cut,result_at in ho:
        rows=race["runners"]
        # Reuse fixed HYP rule; predictions only inspect frozen features.
        ranking=sorted(rows,key=lambda row:(-row["features"][feature],row["horse_number"]))
        number=ranking[0]["horse_number"]
        p=0.8 if number==1 and ranking[0]["features"][feature]>=chosen["threshold"] else 0.2
        y=int(race["winner"]==1)
        observations.append({"race_id":race["race_id"],"frozen_utc":cut.isoformat(),
            "result_utc":result_at.isoformat(),"champion_probability":0.5,
            "candidate_probability":p,"outcome":y})
        paired.append({"race_id":race["race_id"],"cutoff_utc":cut.isoformat(),
             "pre_result_frozen":True,
             "champion_log_loss":-log(0.5),
             "candidate_log_loss":-log(p if y else 1-p)})
    independent=independent_research_audit(plan,observations)
    rollback=guard_research_champion(champion=champion,candidate=candidate,
               alternate=alternate,observations=paired,
               min_races=10,min_mean_improvement=0.01,
               min_paired_win_fraction=0.75)
    eligible=(independent["research_gate"]=="LAB_ONLY_PASS" and
              rollback["decision"]=="SHADOW_CANDIDATE_ELIGIBLE_FOR_INDEPENDENT_AUDIT")
    result={"schema":"kyoto_rg04_research_cycle.v1",
        "scope":"PRECOMMITTED_LAB_ONLY_NO_REAL_JRA",
        "training_race_ids":[r[0]["race_id"] for r in tr],
        "holdout_race_ids":ids,"discovery_sha256":discovery["input_sha256"],
        "selected_hypothesis_id":chosen["id"],"candidate":candidate,
        "plan_sha256":independent["plan_sha256"],
        "independent_audit_sha256":independent["audit_sha256"],
        "rollback_decision_sha256":rollback["decision_sha256"],
        "verdict":"LAB_SHADOW_ELIGIBLE_NO_DEPLOY" if eligible else "LAB_REJECT_AND_RETAIN_CHAMPION",
        "retained_champion":rollback["retained_champion"],
        "rollback_result":rollback["decision"],
        "alternate_promoted":False,
        "production_changed":False,"real_operational_credit":False,
        "auto_deploy":False,"actual_bet_authorized":False}
    return {**result,"cycle_sha256":_hash(result)}
