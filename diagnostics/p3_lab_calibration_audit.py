"""ALG-04/07 independent LAB-only multiclass calibration and benchmark audit.

Do not use this report to authorize paper trades, JRA-source certification,
production promotion, or superiority claims based on synthetic holdout.
"""
from __future__ import annotations
from math import fsum, log
from diagnostics.p3_offline_model_tournament import (
    CANDIDATES,TournamentRejected,_utc,_hash,_validate,predict,
    audit_chronological_holdout,
)

def audit_calibration(train,holdout,*,plan_locked_utc,bins=5,min_holdout=10):
    if type(bins) is not int or not 2<=bins<=20:
        raise TournamentRejected("calibration_bins_invalid")
    if type(min_holdout) is not int or min_holdout<10 or len(holdout)<min_holdout:
        raise TournamentRejected("calibration_holdout_too_short")
    tournament=audit_chronological_holdout(
        train,holdout,plan_locked_utc=plan_locked_utc)
    calibration={}
    for model in CANDIDATES:
        accum=[{"n":0,"sum_probability":0.0,"sum_hits":0} for _ in range(bins)]
        per_race=[]
        for record in holdout:
            forecast=predict(record["snapshot"],model)
            expected=record["winning_pair"]
            pairrows=forecast["quinella"]
            selected=max(pairrows,key=lambda row:(row["probability"],[-n for n in row["pair"]]))
            p=selected["probability"]
            hit=int(selected["pair"]==expected)
            bucket=min(int(p*bins),bins-1)
            cell=accum[bucket]
            cell["n"]+=1
            cell["sum_probability"]+=p
            cell["sum_hits"]+=hit
            per_race.append({"race_id":record["snapshot"]["race_id"],
                "forecast_sha256":forecast["forecast_sha256"],
                "cutoff_utc":record["snapshot"]["feature_cutoff_utc"],
                "selected_pair":selected["pair"],"selected_probability":p,
                "selected_was_winner":bool(hit)})
        summary=[]
        for i,cell in enumerate(accum):
            n=cell["n"]
            summary.append({"bin_index":i,"count":n,
                "mean_forecast":cell["sum_probability"]/n if n else None,
                "empirical_frequency":cell["sum_hits"]/n if n else None})
        ece=fsum((cell["count"]/len(holdout))*abs(
            cell["mean_forecast"]-cell["empirical_frequency"]) for cell in summary
            if cell["count"]>0)
        calibration[model]={"top_pair_ece":ece,
            "bin_count":bins,"bins":summary,"race_receipts":per_race,
            "total_samples":len(holdout)}
    # The five fixed formula alternatives were evaluated on the same sealed
    # chronology. This report does not use holdout outcomes to fit any model.
    # Selecting a winner on holdout is NOT a fresh independent demonstration.
    baseline=tournament["metrics"]["PL_BASE"]
    comparison={}
    for model in CANDIDATES:
        m=tournament["metrics"][model]
        comparison[model]={"paired_races":len(holdout),
            "mean_log_loss_delta_vs_PL_BASE":
                baseline["mean_multiclass_log_loss"]-m["mean_multiclass_log_loss"],
            "mean_brier_delta_vs_PL_BASE":
                baseline["mean_multiclass_brier"]-m["mean_multiclass_brier"]}
    body={"schema":"kyoto_p3_lab_calibration_audit.v1",
        "tournament_sha256":tournament["receipt_sha256"],
        "fixed_hypothesis_count":len(CANDIDATES),
        "train_races":len(train),"holdout_races":len(holdout),
        "plan_locked_utc":plan_locked_utc,"calibration":calibration,
        "paired_comparison":comparison,"metric_role":
            "TOP_PAIR_RELIABILITY_ECE_AND_MULTICLASS_PROPER_SCORES",
        "independent_source_authenticated":False,
        "holdout_based_model_selection_authorized":False,
        "calibration_certified":False,
        "production_model_changed":False,"real_bet_authorized":False}
    return {**body,"audit_sha256":_hash(body)}
