"""P3->P7 sealed same-race shadow evaluation and research-only decision journal.

Uses the existing hybrid model registry, common quinella/bracket contract and
P7 proper-score guard. Freeze predictions before the outcome is accepted;
settle only a later supplied LAB label. No authentic official evidence, model
training, auto-promotion, JRA GET or production mutation is provided.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from datetime import datetime,timezone
from pathlib import Path
from diagnostics.p7_hybrid_model_registry import (
    read_registry, registered_model,_hash,_encoded)
from diagnostics.p3_hybrid_prediction_contract import (
    check_lab_prediction,_utc)
from diagnostics.p7_guarded_research_rollback import guard_research_champion

class ShadowCycleRejected(ValueError): pass
SCHEMA="kyoto_p3p7_hybrid_shadow_journal.v1"
ACTIONS=("FREEZE","SETTLE","DECIDE")
ZERO="0"*64

def _validate_lineage(state):
    freezes={};settled={};decisions=[];max_cutoff=None;last_result=None
    for row in state["events"]:
        data=row["data"];action=row["action"]
        if action=="FREEZE":
            if (type(data) is not dict or set(data)!={"snapshot","predictions","registry_head_sha256","freeze_utc"}):
                raise ShadowCycleRejected("freeze_schema_invalid")
            snap=data["snapshot"];race=snap.get("race_id") if type(snap) is dict else None
            if race in freezes or type(race) is not str or not race.startswith("LAB-"):
                raise ShadowCycleRejected("freeze_duplicate_race_or_nonlab")
            if type(data["predictions"]) is not list or len(data["predictions"])!=2:
                raise ShadowCycleRejected("freeze_models_invalid")
            preds=data["predictions"]
            if any(type(p) is not dict or type(p.get("model_id")) is not str for p in preds):
                raise ShadowCycleRejected("freeze_prediction_schema_invalid")
            if preds[0]["model_id"]==preds[1]["model_id"]:
                raise ShadowCycleRejected("freeze_same_model_twice")
            cut=_utc(snap["cutoff_utc"])
            frozen=_utc(data["freeze_utc"])
            if frozen>cut:
                raise ShadowCycleRejected("freeze_after_cutoff")
            if max_cutoff is not None and cut<=max_cutoff:
                raise ShadowCycleRejected("freeze_not_strictly_chronological")
            if last_result is not None and cut<=last_result:
                raise ShadowCycleRejected("new_freeze_before_past_result")
            max_cutoff=cut
            freezes[race]=data
        elif action=="SETTLE":
            if (type(data) is not dict or set(data)!={"race_id","outcome_utc","winning_pair","label_scope"}):
                raise ShadowCycleRejected("settle_schema_invalid")
            race=data["race_id"]
            if race not in freezes or race in settled:
                raise ShadowCycleRejected("settle_missing_or_duplicate_freeze")
            if data["label_scope"]!="LAB_SYNTHETIC_ONLY":
                raise ShadowCycleRejected("external_result_not_accepted")
            winner=data["winning_pair"]
            nums={r["horse_number"] for r in freezes[race]["snapshot"]["runners"]}
            if (type(winner) is not list or len(winner)!=2 or any(type(x) is not int for x in winner)
                or winner!=sorted(winner) or len(set(winner))!=2 or not set(winner)<=nums):
                raise ShadowCycleRejected("winning_pair_invalid")
            result_time=_utc(data["outcome_utc"])
            if result_time<=_utc(freezes[race]["snapshot"]["cutoff_utc"]):
                raise ShadowCycleRejected("result_not_after_cutoff")
            settled[race]=data
            last_result=result_time
        elif action=="DECIDE":
            if type(data) is not dict or set(data)!={"decision","settled_races","settlement_sha256"}:
                raise ShadowCycleRejected("decision_schema_invalid")
            if type(data["settled_races"]) is not list or any(
                r not in settled for r in data["settled_races"]):
                raise ShadowCycleRejected("decision_unsettled_races")
            if data["settlement_sha256"]!=_hash([settled[r] for r in data["settled_races"]]):
                raise ShadowCycleRejected("decision_settlement_mismatch")
            if decisions or set(data["settled_races"])!=set(freezes) or len(set(data["settled_races"]))!=len(freezes):
                raise ShadowCycleRejected("decision_reuses_or_omits_races")
            decision=data["decision"]
            if type(decision) is not dict or decision.get("status")!="RESEARCH_ONLY_NOT_DEPLOYED":
                raise ShadowCycleRejected("decision_research_scope_invalid")
            if (any(f["predictions"][0]["model_id"]!=decision.get("champion")
                    or f["predictions"][1]["model_id"]!=decision.get("candidate")
                    for f in freezes.values())):
                raise ShadowCycleRejected("decision_model_pair_mismatch")
            scored=[]
            for race in data["settled_races"]:
                f=freezes[race];winner=settled[race]["winning_pair"]
                pp=f["predictions"]
                probabilities=[]
                for prediction in pp:
                    matches=[q["probability"] for q in prediction["quinella"]
                             if q["pair"]==winner]
                    if len(matches)!=1 or type(matches[0]) not in (int,float) or not math.isfinite(matches[0]) or not 0<=matches[0]<=1:
                        raise ShadowCycleRejected("frozen_prediction_not_replayable")
                    probabilities.append(-math.log(max(matches[0],1e-15)))
                scored.append({"race_id":race,"cutoff_utc":f["snapshot"]["cutoff_utc"],
                               "pre_result_frozen":True,
                               "champion_log_loss":probabilities[0],
                               "candidate_log_loss":probabilities[1]})
            try:
                thresholds=decision["thresholds"]
                recomputed=guard_research_champion(
                    champion=decision["champion"],candidate=decision["candidate"],
                    alternate=decision["alternate"],observations=scored,
                    min_races=thresholds["min_races"],
                    min_mean_improvement=thresholds["min_mean_improvement"],
                    min_paired_win_fraction=thresholds["min_paired_win_fraction"],
                    prior_decision_sha256=None)
            except (KeyError,TypeError,ValueError) as exc:
                raise ShadowCycleRejected("decision_recalculation_rejected") from exc
            if recomputed!=decision:
                raise ShadowCycleRejected("decision_not_reproducible_from_frozen_outcomes")
            decisions.append(data)
        else:
            raise ShadowCycleRejected("unknown_journal_event")
    return {"freezes":freezes,"settled":settled,"decisions":decisions}

def read_shadow(path):
    p=Path(path)
    if p.is_symlink():raise ShadowCycleRejected("journal_symlink_forbidden")
    if not p.exists():
        return {"events":[],"head":ZERO,"freezes":{},"settled":{},"decisions":[]}
    if not p.is_file() or p.stat().st_size>6_000_000:
        raise ShadowCycleRejected("journal_size_invalid")
    raw=p.read_bytes()
    if not raw or not raw.endswith(b"\n"):
        raise ShadowCycleRejected("journal_partial")
    events=[];prev=ZERO
    for line in raw.splitlines():
        try:row=json.loads(line)
        except (ValueError,UnicodeError) as exc:raise ShadowCycleRejected("journal_json_invalid") from exc
        if type(row) is not dict or set(row)!={"schema","seq","previous_sha256","action","data","event_sha256"}:
            raise ShadowCycleRejected("journal_line_schema_invalid")
        if (row["schema"]!=SCHEMA or type(row["seq"]) is not int or row["seq"]!=len(events)+1
            or row["previous_sha256"]!=prev or row["action"] not in ACTIONS
            or row["event_sha256"]!=_hash({k:v for k,v in row.items() if k!="event_sha256"})):
            raise ShadowCycleRejected("journal_chain_invalid")
        prev=row["event_sha256"];events.append(row)
    state={"events":events,"head":prev}
    state.update(_validate_lineage(state))
    return state

def _append(path,action,data,*,expected_head):
    p=Path(path)
    if type(expected_head) is not str or len(expected_head)!=64:
        raise ShadowCycleRejected("expected_head_required")
    if not p.parent.is_dir() or p.is_symlink():
        raise ShadowCycleRejected("journal_parent_invalid")
    lock=p.with_name(p.name+".lock")
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:raise ShadowCycleRejected("journal_locked") from exc
    try:
        os.close(fd)
        old=read_shadow(p)
        if expected_head!=old["head"]:
            raise ShadowCycleRejected("journal_stale_head")
        row={"schema":SCHEMA,"seq":len(old["events"])+1,
             "previous_sha256":old["head"],"action":action,"data":data}
        row["event_sha256"]=_hash(row)
        candidate={"events":old["events"]+[row]}
        _validate_lineage(candidate)
        content=_encoded(row)+b"\n"
        if (p.stat().st_size if p.exists() else 0)+len(content)>6_000_000:
            raise ShadowCycleRejected("journal_capacity_exceeded")
        flags=os.O_WRONLY|os.O_CREAT|os.O_APPEND
        if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
        outfd=os.open(p,flags,0o600)
        with os.fdopen(outfd,"ab") as out:
            out.write(content);out.flush();os.fsync(out.fileno())
        verified=read_shadow(p)
        if verified["head"]!=row["event_sha256"]:
            raise ShadowCycleRejected("journal_append_mismatch")
        return {"event_sha256":verified["head"],"event_count":len(verified["events"]),
                "research_only":True,"production_model_changed":False}
    finally: lock.unlink(missing_ok=True)

def freeze_lab_pair(path,registry_path,snapshot,champion,challenger,*,freeze_utc,expected_head):
    """Lock both outputs on the same immutable pre-result snapshot."""
    if type(champion) is not dict or type(challenger) is not dict:
        raise ShadowCycleRejected("two_prediction_dicts_required")
    if (champion.get("model_id")==challenger.get("model_id")
        or champion.get("model_id") is None):
        raise ShadowCycleRejected("distinct_challenger_required")
    c=check_lab_prediction(registry_path,snapshot,champion)
    q=check_lab_prediction(registry_path,snapshot,challenger)
    if c["registry_head_sha256"]!=q["registry_head_sha256"]:
        raise ShadowCycleRejected("registry_anchor_changed")
    return _append(path,"FREEZE",{
        "snapshot":snapshot,"predictions":[champion,challenger],
        "registry_head_sha256":c["registry_head_sha256"],
        "freeze_utc":freeze_utc},expected_head=expected_head)

def settle_lab_pair(path,race_id,winning_pair,*,outcome_utc,expected_head):
    data={"race_id":race_id,"outcome_utc":outcome_utc,
          "winning_pair":winning_pair,"label_scope":"LAB_SYNTHETIC_ONLY"}
    return _append(path,"SETTLE",data,expected_head=expected_head)

def scored_pairs(path):
    state=read_shadow(path)
    pairs=[]
    for race,freeze in state["freezes"].items():
        if race not in state["settled"]:continue
        settled=state["settled"][race]
        winning=settled["winning_pair"]
        first,second=freeze["predictions"]
        def loss(pred):
            choice=next(q["probability"] for q in pred["quinella"] if q["pair"]==winning)
            return -math.log(max(choice,1e-15))
        pairs.append({"race_id":race,"cutoff_utc":freeze["snapshot"]["cutoff_utc"],
                      "pre_result_frozen":True,"champion_log_loss":loss(first),
                      "candidate_log_loss":loss(second)})
    return pairs

def record_shadow_decision(path,*,champion,candidate,alternate,
                           expected_head,min_races=4,min_mean_improvement=0.01,
                           min_paired_win_fraction=0.75):
    state=read_shadow(path)
    if not state["freezes"] or len(state["settled"])!=len(state["freezes"]):
        raise ShadowCycleRejected("all_precommitted_races_must_be_settled")
    freezes=list(state["freezes"].values())
    if any(x["predictions"][0]["model_id"]!=champion or
           x["predictions"][1]["model_id"]!=candidate for x in freezes):
        raise ShadowCycleRejected("model_pair_changed")
    paired=scored_pairs(path)
    decision=guard_research_champion(
        champion=champion,candidate=candidate,alternate=alternate,
        observations=paired,min_races=min_races,
        min_mean_improvement=min_mean_improvement,
        min_paired_win_fraction=min_paired_win_fraction,
        prior_decision_sha256=state["decisions"][-1]["decision"]["decision_sha256"] if state["decisions"] else None)
    races=[r["race_id"] for r in paired]
    receipt=_append(path,"DECIDE",{
        "decision":decision,"settled_races":races,
        "settlement_sha256":_hash([state["settled"][r] for r in races])},
        expected_head=expected_head)
    return {**receipt,"shadow_decision":decision["decision"],
            "decision_sha256":decision["decision_sha256"],
            "actual_JRA_improvement_verified":False,
            "independent_live_certification":False,"auto_deployed":False}
