"""Strict shared P3 laboratory model output contract for all model families.

It consumes supplied research predictions, never fits a model, downloads
official data, or certifies genuine JRA provenance. Both quinella and bracket
are compared at identical supplied feature and source anchors.
"""
from __future__ import annotations
from datetime import datetime,timezone
from math import fsum,isfinite
from diagnostics.p7_hybrid_model_registry import registered_model,_hash

class PredictionContractRejected(ValueError):
    pass

def _utc(s):
    if type(s) is not str:
        raise PredictionContractRejected("utc_time_required")
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as exc:
        raise PredictionContractRejected("utc_invalid") from exc
    if t.utcoffset()!=timezone.utc.utcoffset(None):
        raise PredictionContractRejected("utc_timezone_invalid")
    return t

def _pairs(rows,permitted,label):
    if type(rows) is not list or len(rows)!=len(permitted):
        raise PredictionContractRejected(label+"_market_not_complete")
    found={}
    for r in rows:
        if type(r) is not dict or set(r)!={"pair","probability"}:
            raise PredictionContractRejected(label+"_pair_schema_invalid")
        pair=r["pair"];p=r["probability"]
        if (type(pair) is not list or len(pair)!=2 or
                any(type(n) is not int for n in pair) or
                pair!=sorted(pair) or tuple(pair) not in permitted or
                tuple(pair) in found):
            raise PredictionContractRejected(label+"_pair_invalid_or_duplicate")
        if type(p) not in (int,float) or not isfinite(p) or not 0<=p<=1:
            raise PredictionContractRejected(label+"_probability_invalid")
        found[tuple(pair)]=float(p)
    if set(found)!=permitted or abs(fsum(found.values())-1)>1e-9:
        raise PredictionContractRejected(label+"_normalization_invalid")
    return found

def check_lab_prediction(path, snapshot, prediction):
    """All computations research-only; caller's source hash is not authenticated."""
    reg=registered_model(path,prediction.get("model_id") if type(prediction) is dict else None)
    model=reg["model"]
    fields={"race_id","source_scope","source_sha256","feature_schema_sha256",
            "cutoff_utc","runners"}
    if type(snapshot) is not dict or set(snapshot)!=fields:
        raise PredictionContractRejected("snapshot_schema_invalid")
    if type(prediction) is not dict or set(prediction)!={"model_id","source_sha256",
            "feature_schema_sha256","cutoff_utc","quinella","bracket"}:
        raise PredictionContractRejected("prediction_schema_invalid")
    if (snapshot["source_scope"]!="LAB_SYNTHETIC_ONLY"
        or prediction["source_sha256"]!=snapshot["source_sha256"]
        or model["feature_schema_sha256"]!=snapshot["feature_schema_sha256"]
        or prediction["feature_schema_sha256"]!=snapshot["feature_schema_sha256"]):
        raise PredictionContractRejected("model_or_source_mismatch")
    if (type(snapshot["source_sha256"]) is not str or
        len(snapshot["source_sha256"])!=64 or
        any(c not in "0123456789abcdef" for c in snapshot["source_sha256"])):
        raise PredictionContractRejected("source_sha_format_invalid")
    if (type(snapshot["race_id"]) is not str or
        not snapshot["race_id"].startswith("LAB-")):
        raise PredictionContractRejected("race_not_lab")
    cut=_utc(snapshot["cutoff_utc"])
    if _utc(prediction["cutoff_utc"])!=cut:
        raise PredictionContractRejected("cutoff_mismatch")
    runners=snapshot["runners"]
    if type(runners) is not list or not 2<=len(runners)<=18:
        raise PredictionContractRejected("runner_count_invalid")
    frames={}
    for runner in runners:
        if type(runner) is not dict or set(runner)!={"horse_number","frame_number"}:
            raise PredictionContractRejected("runner_fields_invalid")
        n,f=runner["horse_number"],runner["frame_number"]
        if (type(n) is not int or not 1<=n<=18 or n in frames
            or type(f) is not int or not 1<=f<=8):
            raise PredictionContractRejected("runner_number_or_frame_invalid")
        frames[n]=f
    numbers=sorted(frames)
    allowed_q={(a,b) for i,a in enumerate(numbers) for b in numbers[i+1:]}
    q=_pairs(prediction["quinella"],allowed_q,"quinella")
    allowed_b={tuple(sorted((frames[a],frames[b]))) for a,b in allowed_q}
    b=_pairs(prediction["bracket"],allowed_b,"bracket")
    aggregated={}
    for (a,c),p in q.items():
        frame_pair=tuple(sorted((frames[a],frames[c])))
        aggregated[frame_pair]=aggregated.get(frame_pair,0)+p
    if any(abs(b[key]-aggregated[key])>1e-9 for key in allowed_b):
        raise PredictionContractRejected("bracket_not_derived_from_quinella")
    result={"schema":"kyoto_p3_hybrid_prediction_contract.v1",
            "model_id":prediction["model_id"],
            "model_kind":model["kind"],
            "race_id":snapshot["race_id"],
            "source_sha256":snapshot["source_sha256"],
            "registry_head_sha256":reg["registry_head_sha256"],
            "cutoff_utc":snapshot["cutoff_utc"],
            "runner_count":len(numbers),
            "quinella_pairs":len(allowed_q),"bracket_pairs":len(allowed_b),
            "same_frame_bracket_supported":any(a==c for a,c in allowed_b),
            "research_only":True,
            "real_JRA_source_authenticated":False,
            "actual_pre_race_prediction_verified":False,
            "independently_certified":False,
            "production_model_changed":False}
    return {**result,"contract_sha256":_hash(result)}
