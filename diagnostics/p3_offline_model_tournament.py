"""Offline ALG-04/05/07 fixed-family model comparison; never authenticates JRA or bets."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from math import fsum,log,isfinite
import json
from diagnostics.p3_p6_research_no_bet import quinella_from_strength,bracket_from_quinella

class TournamentRejected(ValueError):pass
CANDIDATES=("PL_BASE","PL_SHARP","PL_FLAT","PAIR_PRODUCT","PL_PRODUCT_BLEND")

def _hash(x):
    return sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _utc(s):
    if type(s) is not str or not(s.endswith("Z") or s.endswith("+00:00")):
        raise TournamentRejected("UTC_required")
    try:t=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as exc:raise TournamentRejected("UTC_invalid") from exc
    if t.utcoffset()!=timezone.utc.utcoffset(None):raise TournamentRejected("UTC_required")
    return t

def _validate(s):
    fields={"race_id","feature_source_sha256","feature_cutoff_utc","race_start_utc",
            "source_scope","runners"}
    if type(s) is not dict or set(s)!=fields:raise TournamentRejected("snapshot_schema")
    if s["source_scope"]!="LAB_OFFLINE_ONLY" or type(s["race_id"]) is not str or not s["race_id"].startswith("LAB-"):
        raise TournamentRejected("nonlab_source_forbidden")
    h=s["feature_source_sha256"]
    if type(h) is not str or len(h)!=64 or any(c not in "0123456789abcdef" for c in h):
        raise TournamentRejected("source_sha_invalid")
    if _utc(s["feature_cutoff_utc"])>=_utc(s["race_start_utc"]):
        raise TournamentRejected("future_features")
    rows=s["runners"]
    if type(rows) is not list or not 3<=len(rows)<=18:raise TournamentRejected("runner_count")
    weights={};frames={}
    for r in rows:
        if type(r) is not dict or set(r)!={"number","frame","prior_strength"}:
            raise TournamentRejected("runner_schema")
        n,f,w=r["number"],r["frame"],r["prior_strength"]
        if (type(n) is not int or not 1<=n<=18 or n in weights
            or type(f) is not int or not 1<=f<=8
            or type(w) not in (int,float) or not isfinite(w) or w<=0):
            raise TournamentRejected("runner_value")
        weights[n]=w;frames[n]=f
    return weights,frames

def predict(snapshot,model):
    strengths,frames=_validate(snapshot)
    if model not in CANDIDATES:raise TournamentRejected("unknown_model")
    max_value=max(strengths.values())
    weights={n:w/max_value for n,w in strengths.items()}
    pl=quinella_from_strength(weights)
    if model=="PL_BASE":q=pl
    elif model in ("PL_SHARP","PL_FLAT"):
        exponent=1.5 if model=="PL_SHARP" else .75
        q=quinella_from_strength({n:w**exponent for n,w in weights.items()})
    else:
        products={pair:weights[pair[0]]*weights[pair[1]] for pair in pl}
        total=fsum(products.values())
        product={pair:w/total for pair,w in products.items()}
        q=product if model=="PAIR_PRODUCT" else {pair:(pl[pair]+product[pair])/2 for pair in pl}
    b=bracket_from_quinella(q,frames)
    body={"schema":"kyoto_p3_offline_candidate_prediction.v1",
        "model_id":model,"race_id":snapshot["race_id"],
        "source_sha256":snapshot["feature_source_sha256"],
        "cutoff_utc":snapshot["feature_cutoff_utc"],
        "quinella":[{"pair":list(k),"probability":v} for k,v in sorted(q.items())],
        "bracket":[{"pair":list(k),"probability":v} for k,v in sorted(b.items())],
        "scope":"LAB_OFFLINE_ONLY","official_JRA_authenticated":False,
        "model_calibrated":False,"production_eligible":False}
    return {**body,"forecast_sha256":_hash(body)}

def audit_chronological_holdout(train,holdout,*,plan_locked_utc):
    locked=_utc(plan_locked_utc)
    if type(train) is not list or type(holdout) is not list or len(train)<6 or len(holdout)<10:
        raise TournamentRejected("insufficient_train_or_holdout")
    seen=set();last=None
    for group,rows in (("train",train),("holdout",holdout)):
        for row in rows:
            if type(row) is not dict or set(row)!={"snapshot","forecast_frozen_utc","outcome_utc","winning_pair"}:
                raise TournamentRejected("label_record_schema")
            s=row["snapshot"];w,_=_validate(s)
            cutoff=_utc(s["feature_cutoff_utc"]);start=_utc(s["race_start_utc"])
            freeze=_utc(row["forecast_frozen_utc"]);outcome=_utc(row["outcome_utc"])
            if (s["race_id"] in seen or (last is not None and cutoff<=last)
                or not cutoff<=freeze<start<outcome
                or (group=="train" and outcome>=locked)
                or (group=="holdout" and cutoff<=locked)):
                raise TournamentRejected("leakage_or_duplicate_or_time_order")
            pair=row["winning_pair"]
            if (type(pair) is not list or len(pair)!=2 or pair!=sorted(pair)
                or len(set(pair))!=2 or any(type(n) is not int or n not in w for n in pair)):
                raise TournamentRejected("winner_invalid")
            seen.add(s["race_id"]);last=cutoff
    scores={}
    for model in CANDIDATES:
        losses=[];briers=[]
        for row in holdout:
            forecast=predict(row["snapshot"],model)
            pairs=forecast["quinella"];winner=row["winning_pair"]
            hit=[p["probability"] for p in pairs if p["pair"]==winner]
            if len(hit)!=1:raise TournamentRejected("winner_not_in_market")
            losses.append(-log(max(hit[0],1e-15)))
            briers.append(fsum((p["probability"]-int(p["pair"]==winner))**2 for p in pairs))
        scores[model]={"mean_multiclass_log_loss":fsum(losses)/len(losses),
            "mean_multiclass_brier":fsum(briers)/len(briers),
            "holdout_races":len(holdout)}
    ranking=sorted(CANDIDATES,key=lambda m:(scores[m]["mean_multiclass_log_loss"],
        scores[m]["mean_multiclass_brier"],m))
    result={"schema":"kyoto_p3_offline_tournament.v1",
        "train_count":len(train),"holdout_count":len(holdout),
        "plan_locked_utc":plan_locked_utc,"comparison_count":len(CANDIDATES),
        "family":list(CANDIDATES),"ranking_by_log_loss_only":ranking,
        "metrics":scores,"independent_real_JRA_validation":False,
        "calibration_certified":False,"selection_certified":False,
        "production_model_changed":False,"real_betting_authorized":False}
    return {**result,"receipt_sha256":_hash(result)}
