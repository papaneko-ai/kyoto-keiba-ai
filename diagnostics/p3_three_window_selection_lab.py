"""Three-window P3 model selection with strictly untouched final LAB evaluation.

Selection uses validation only, never final evaluation. This is not an
independent source authenticity proof or production certification.
"""
from __future__ import annotations
from math import fsum,log
from diagnostics.p3_offline_model_tournament import (
    CANDIDATES,TournamentRejected,_utc,_hash,_validate,predict)

def _validate_rows(rows, previous, seen, *, bound_start=None, bound_end=None):
    score={}
    for r in rows:
        if type(r) is not dict or set(r)!={"snapshot","forecast_frozen_utc","outcome_utc","winning_pair"}:
            raise TournamentRejected("evaluation_record_schema")
        snap=r["snapshot"]
        strengths,_=_validate(snap)
        cutoff=_utc(snap["feature_cutoff_utc"])
        start=_utc(snap["race_start_utc"])
        freeze=_utc(r["forecast_frozen_utc"])
        outcome=_utc(r["outcome_utc"])
        if (snap["race_id"] in seen or (previous is not None and cutoff<=previous)
            or not cutoff<=freeze<start<outcome
            or (bound_end is not None and outcome>=bound_end)
            or (bound_start is not None and cutoff<=bound_start)):
            raise TournamentRejected("three_window_overlap_or_leakage")
        pair=r["winning_pair"]
        if (type(pair) is not list or len(pair)!=2 or pair!=sorted(pair)
            or pair[0]==pair[1] or any(type(n) is not int or n not in strengths for n in pair)):
            raise TournamentRejected("winner_pair_invalid")
        seen.add(snap["race_id"])
        previous=cutoff
    return previous

def _score(rows,model):
    losses=[];briers=[]
    for r in rows:
        pred=predict(r["snapshot"],model)
        correct=r["winning_pair"]
        pairs=pred["quinella"]
        p=next((x["probability"] for x in pairs if x["pair"]==correct),None)
        if p is None:raise TournamentRejected("winning_pair_unavailable")
        losses.append(-log(max(p,1e-15)))
        briers.append(fsum((x["probability"]-int(x["pair"]==correct))**2 for x in pairs))
    return {"n":len(rows),"mean_log_loss":fsum(losses)/len(rows),
            "mean_brier":fsum(briers)/len(rows)}

def three_window_selection(training,validation,untouched,*,selection_locked_utc,
                           final_locked_utc):
    if (any(type(group) is not list for group in (training,validation,untouched))
        or len(training)<6 or len(validation)<6 or len(untouched)<10):
        raise TournamentRejected("three_window_minimum_sample_required")
    selection_lock=_utc(selection_locked_utc)
    final_lock=_utc(final_locked_utc)
    if selection_lock>=final_lock:
        raise TournamentRejected("incorrect_lock_order")
    seen=set();last=None
    last=_validate_rows(training,last,seen,bound_end=selection_lock)
    last=_validate_rows(validation,last,seen,bound_start=selection_lock,bound_end=final_lock)
    _validate_rows(untouched,last,seen,bound_start=final_lock)
    validation_metrics={model:_score(validation,model) for model in CANDIDATES}
    winner=min(CANDIDATES,key=lambda m:(
        validation_metrics[m]["mean_log_loss"],
        validation_metrics[m]["mean_brier"],m))
    final_metrics={model:_score(untouched,model) for model in ("PL_BASE",winner)}
    baseline=final_metrics["PL_BASE"];selected=final_metrics[winner]
    # Always count all five hypotheses, even when the chosen candidate
    # happens to be the baseline.
    body={"schema":"kyoto_p3_three_window_selection_lab.v1",
        "candidate_family":list(CANDIDATES),
        "selection_count":len(CANDIDATES),
        "selection_locked_utc":selection_locked_utc,
        "final_locked_utc":final_locked_utc,
        "training_count":len(training),
        "validation_count":len(validation),
        "untouched_count":len(untouched),
        "training_input_sha256":_hash(training),
        "validation_input_sha256":_hash(validation),
        "untouched_input_sha256":_hash(untouched),
        "selected_on_validation":winner,
        "validation_metrics":validation_metrics,
        "final_metrics":final_metrics,
        "final_log_loss_improvement_vs_baseline":
            baseline["mean_log_loss"]-selected["mean_log_loss"],
        "final_brier_improvement_vs_baseline":
            baseline["mean_brier"]-selected["mean_brier"],
        "independent_time_window":True,
        "independent_official_source":False,
        "selection_significance_certified":False,
        "live_model_certified":False,
        "production_model_changed":False,
        "real_trade_authorized":False}
    return {**body,"receipt_sha256":_hash(body)}
