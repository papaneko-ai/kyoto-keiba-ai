"""Research-only pair-probability calibration and proper scoring, no wagering.

Pre-registered chronological train/evaluation split; each held-out race is
scored once. Labels and prices never enter fitting features. No live claims.
"""
from __future__ import annotations
import math
from datetime import datetime,timezone


class CalibrationRejected(ValueError):
    pass


def timestamp(value):
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
        if t.tzinfo is None or t.utcoffset() is None:
            raise ValueError("timezone required")
        return t.astimezone(timezone.utc)
    except (AttributeError,TypeError,ValueError) as exc:
        raise CalibrationRejected("invalid_utc_timestamp") from exc


def validate_races(races):
    if not isinstance(races,list) or len(races)<4:
        raise CalibrationRejected("at_least_four_independent_races_required")
    ids=set()
    parsed=[]
    for race in races:
        try:
            key=race["race_id"]
            t=timestamp(race["prediction_cutoff_utc"])
            pairs=race["pairs"]
            winner=tuple(race["winning_pair"])
            if not isinstance(key,str) or not key or key in ids:
                raise CalibrationRejected("duplicate_or_invalid_race_id")
            ids.add(key)
            if not isinstance(pairs,list) or len(pairs)<1:
                raise CalibrationRejected("missing_pairs")
            ps={}
            for pair in pairs:
                pair_key=tuple(pair["pair"])
                p=pair["probability"]
                if (len(pair_key)!=2 or any(type(x) is not int for x in pair_key)
                        or pair_key[0]>=pair_key[1] or pair_key in ps
                        or type(p) not in (int,float) or not math.isfinite(p)
                        or not 0<p<1):
                    raise CalibrationRejected("invalid_pair_probability")
                ps[pair_key]=float(p)
            if winner not in ps:
                raise CalibrationRejected("winner_missing_from_predicted_pairs")
            if abs(math.fsum(ps.values())-1.0)>1e-9:
                raise CalibrationRejected("pair_probabilities_not_normalized")
            # A receipt must explicitly attest that predictions were frozen
            # before any outcomes became known. Never infer from labels.
            if race.get("pre_result_frozen") is not True:
                raise CalibrationRejected("pre_result_prediction_receipt_required")
            parsed.append((t,key,ps,winner))
        except (KeyError,TypeError) as exc:
            raise CalibrationRejected("invalid_race_record") from exc
    if parsed!=sorted(parsed,key=lambda x:(x[0],x[1])):
        raise CalibrationRejected("races_not_chronologically_sorted")
    if len({x[0] for x in parsed})!=len(parsed):
        raise CalibrationRejected("same_timestamp_races_require_explicit_order")
    return parsed


def shrink_distribution(ps,alpha):
    # Mixture with the uniform distribution is a proper probability vector.
    n=len(ps)
    return {k:(1-alpha)*p+alpha/n for k,p in ps.items()}


def scores(ps,winner):
    brier=math.fsum((p-(1 if k==winner else 0))**2 for k,p in ps.items())
    log_loss=-math.log(ps[winner])
    return brier,log_loss


def calibrate_holdout(races,*,train_count):
    parsed=validate_races(races)
    if type(train_count) is not int or train_count<2 or train_count>=len(parsed):
        raise CalibrationRejected("invalid_chronological_train_count")
    training=parsed[:train_count]
    testing=parsed[train_count:]
    if not training[-1][0]<testing[0][0]:
        raise CalibrationRejected("train_holdout_overlap")
    # Select shrinkage ONLY on the training races; no evaluation labels
    # influence the chosen parameter. Fixed grid, deterministic tie-breaking.
    candidates=(0.0,0.1,0.2,0.4,0.6,0.8,1.0)
    best=min(candidates,key=lambda a:(
        math.fsum(scores(shrink_distribution(ps,a),win)[1]
                  for _,_,ps,win in training)/len(training),a))
    def evaluate(rows,alpha):
        bs=[];ls=[]
        for _,_,ps,win in rows:
            b,l=scores(shrink_distribution(ps,alpha),win)
            bs.append(b);ls.append(l)
        return {"races":len(rows),"brier":math.fsum(bs)/len(bs),
                "log_loss":math.fsum(ls)/len(ls)}
    raw=evaluate(testing,0.0)
    adjusted=evaluate(testing,best)
    return {
        "schema":"kyoto_p3_research_calibration.v1",
        "status":"RESEARCH_HOLDOUT_SCORED_NOT_DEPLOYED",
        "train_race_ids":[x[1] for x in training],
        "holdout_race_ids":[x[1] for x in testing],
        "train_last_utc":training[-1][0].isoformat(),
        "holdout_first_utc":testing[0][0].isoformat(),
        "selected_uniform_shrinkage":best,
        "uncalibrated_holdout":raw,
        "calibrated_holdout":adjusted,
        "improved_brier":adjusted["brier"]<raw["brier"],
        "improved_log_loss":adjusted["log_loss"]<raw["log_loss"],
        "prediction_ready":False,"real_money_authorized":False,
    }


def walk_forward_overfit_audit(races,*,min_train=3):
    """Expanding-window prequential audit: each future race scored once.

    A fold fits its shrinkage using strictly earlier races; the held-out
    outcome is used only for scoring. Never promote on a favorable average
    without separately verified real, previously unseen racing evidence.
    """
    parsed=validate_races(races)
    if type(min_train) is not int or min_train<2 or min_train>=len(parsed):
        raise CalibrationRejected("invalid_walk_forward_min_train")
    folds=[]
    for i in range(min_train,len(parsed)):
        # No fold can train on the outcome it is scoring.
        result=calibrate_holdout(races[:i+1],train_count=i)
        if len(result["holdout_race_ids"])!=1:
            raise CalibrationRejected("walk_forward_holdout_must_be_one_race")
        folds.append({
            "race_id":result["holdout_race_ids"][0],
            "trained_through_utc":result["train_last_utc"],
            "tested_at_utc":result["holdout_first_utc"],
            "shrinkage":result["selected_uniform_shrinkage"],
            "raw":result["uncalibrated_holdout"],
            "calibrated":result["calibrated_holdout"],
        })
    def average(key,metric):
        return math.fsum(x[key][metric] for x in folds)/len(folds)
    raw={"brier":average("raw","brier"),"log_loss":average("raw","log_loss")}
    adjusted={"brier":average("calibrated","brier"),"log_loss":average("calibrated","log_loss")}
    return {
        "schema":"kyoto_p3_research_walk_forward.v1",
        "status":"RESEARCH_WALK_FORWARD_AUDITED_NOT_DEPLOYED",
        "folds":folds,
        "baseline":raw,"candidate":adjusted,
        "overfit_warning":(adjusted["brier"]>=raw["brier"] or
                           adjusted["log_loss"]>=raw["log_loss"]),
        "auto_promote":False,"prediction_ready":False,
    }
