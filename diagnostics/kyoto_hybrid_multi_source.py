"""Source-first, zero-network hybrid selection and item-level evidence merge.

Experimental only. No JRA/network I/O, no credentials, no change to
production, schedule, database or official fixed progress. The caller must
provide externally verified source URLs and original bytes. Missing information
is a follow-up acquisition request, not silently a model input.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit
import math,re

FIELDS=("horse_name","profile","prior_form","jockey","trainer","body_weight",
        "body_weight_delta","weather","turf_going","dirt_going",
        "workout","quinella_odds","bracket_odds")
SOURCES=("JRA_PC","JRA_SP","SUPPLEMENTAL")
_ALLOWED_JRA={"JRA_PC":frozenset(("www.jra.go.jp","jra.go.jp","own.jra.jp")),
              "JRA_SP":frozenset(("sp.jra.jp",))}
HASH=re.compile(r"[a-f0-9]{64}\Z")
class HybridRejected(ValueError): pass

def utc(value):
    if type(value) is not str:
        raise HybridRejected("missing_utc")
    try: d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise HybridRejected("invalid_utc") from exc
    if d.tzinfo is None or d.utcoffset()!=timezone.utc.utcoffset(None):
        raise HybridRejected("utc_not_aware_utc")
    return d

def source_valid(src):
    if type(src) is not dict or set(src)!={
        "kind","url","verified_original_url","license_verified","allowed_for_automated_access"}:
        raise HybridRejected("source_registration_invalid")
    kind=src["kind"]
    if kind not in SOURCES or src["verified_original_url"] is not True:
        raise HybridRejected("unverified_source_url")
    u=urlsplit(src["url"])
    if (u.scheme!="https" or not u.hostname or u.username or u.password or
        u.port is not None or u.fragment):
        raise HybridRejected("unsafe_url")
    if kind in _ALLOWED_JRA:
        if u.hostname not in _ALLOWED_JRA[kind]:
            raise HybridRejected("channel_host_mismatch")
    elif src["license_verified"] is not True or src["allowed_for_automated_access"] is not True:
        raise HybridRejected("supplemental_usage_not_authorized")
    return kind

def evidence_valid(e, race_key, horse_number, cutoff):
    """Verify original bytes exactly. No naked SHA, label or receipt counts as evidence."""
    if type(e) is not dict or set(e)!={
        "race_key","horse_number","field","value","source","raw",
        "source_sha256","captured_utc","published_utc","identity_verified"}:
        raise HybridRejected("evidence_schema_invalid")
    if e["race_key"]!=race_key or e["horse_number"]!=horse_number or e["identity_verified"] is not True:
        raise HybridRejected("race_horse_identity_not_verified")
    if e["field"] not in FIELDS or e["value"] is None:
        raise HybridRejected("invalid_field_or_null_candidate")
    kind=source_valid(e["source"])
    raw=e["raw"]
    if type(raw) is not bytes or not 0<len(raw)<=1_500_000:
        raise HybridRejected("invalid_original_bytes")
    if type(e["source_sha256"]) is not str or not HASH.fullmatch(e["source_sha256"]):
        raise HybridRejected("invalid_original_sha")
    if sha256(raw).hexdigest()!=e["source_sha256"]:
        raise HybridRejected("altered_original")
    captured=utc(e["captured_utc"])
    if captured>=cutoff:raise HybridRejected("captured_after_cutoff")
    published=e["published_utc"]
    if published is not None and (utc(published)>captured or utc(published)>=cutoff):
        raise HybridRejected("publication_after_capture_or_cutoff")
    return kind

def rank_sources(metrics,field,*,min_samples=5):
    """Rank observed performance; zero sample never wins from arbitrary speed."""
    if field not in FIELDS:raise HybridRejected("unknown_field")
    ranked=[]
    for kind in SOURCES:
        m=metrics.get(kind,{}).get(field)
        if not m or m.get("samples",0)<min_samples:
            continue
        n=m["samples"];success=m.get("verified_field_success",0)
        seconds=m.get("mean_elapsed_seconds")
        bytes_used=m.get("mean_bytes")
        if (type(n) is not int or type(success) is not int or not 0<=success<=n or
            type(seconds) not in (float,int) or not math.isfinite(seconds) or seconds<0 or
            type(bytes_used) not in (int,float) or not math.isfinite(bytes_used) or bytes_used<0):
            raise HybridRejected("invalid_metrics")
        if kind=="SUPPLEMENTAL" and m.get("approved_for_automation") is not True:
            continue
        reliability=success/n
        # Observed completeness dominates latency, then payload size.
        ranked.append((kind,reliability,float(seconds),float(bytes_used)))
    ranked.sort(key=lambda x:(-x[1],x[2],x[3],SOURCES.index(x[0])))
    return [x[0] for x in ranked]

def merge_fields(*,race_key,horse_number,cutoff_utc,evidence,required_fields,metrics=None):
    """Merge verified evidence. Conflict => no value. All absence => follow-up."""
    cutoff=utc(cutoff_utc)
    if (type(race_key) is not str or not re.fullmatch(r"KYOTO:20[0-9]{6}:(?:0[1-9]|1[0-2])",race_key)
        or type(horse_number) is not int or not 1<=horse_number<=18):
        raise HybridRejected("race_identity_invalid")
    if type(required_fields) not in (tuple,list) or not required_fields or any(
        x not in FIELDS for x in required_fields) or len(set(required_fields))!=len(required_fields):
        raise HybridRejected("required_fields_invalid")
    if type(evidence) is not list or len(evidence)>100:
        raise HybridRejected("unbounded_evidence")
    grouped={field:[] for field in required_fields}
    for item in evidence:
        kind=evidence_valid(item,race_key,horse_number,cutoff)
        if item["field"] in grouped:
            grouped[item["field"]].append((kind,item))
    fields={};followup=[];disputed=[]
    for field in required_fields:
        rows=grouped[field]
        unique={}
        for kind,item in rows:
            # Same source with a later update does NOT invalidate provenance.
            # But conflicting values are always held until independently adjudicated.
            key=(type(item["value"]).__name__,repr(item["value"]))
            unique.setdefault(key,[]).append((kind,item))
        if len(unique)>1:
            disputed.append(field)
            fields[field]={"state":"CONFLICT","value":None,
                           "source_evidence":[{"kind":k,"sha256":x["source_sha256"],
                                               "captured_utc":x["captured_utc"]}
                                              for k,x in rows]}
            continue
        if not rows:
            preference=rank_sources(metrics or {},field)
            followup.append({"field":field,"reason":"MISSING_SOURCE",
                             "try_sources_in_order":preference,
                             "must_observe_actual_links":True,
                             "already_queried_sources":[]})
            fields[field]={"state":"MISSING","value":None}
            continue
        # Preferred sources determine transport acquisition order, not an
        # arbitrary overwrite of a differing authenticated value.
        chosen=sorted(rows,key=lambda kx:(utc(kx[1]["captured_utc"]),SOURCES.index(kx[0])),reverse=True)[0]
        fields[field]={"state":"VERIFIED","value":chosen[1]["value"],
                       "source_kind":chosen[0],"source_url":chosen[1]["source"]["url"],
                       "sha256":chosen[1]["source_sha256"],
                       "captured_utc":chosen[1]["captured_utc"],
                       "all_sources":sorted(set(k for k,_ in rows))}
    return {"schema":"kyoto_hybrid_verified_field_merge.v1","race_key":race_key,
            "horse_number":horse_number,"fields":fields,"followup":followup,
            "conflict_fields":disputed,"verified_field_count":sum(
                v["state"]=="VERIFIED" for v in fields.values()),
            "required_field_count":len(required_fields),
            "complete":not followup and not disputed,
            "prediction_ready":False,"network_requests":0,
            "experimental_only":True}

def coverage(receipts):
    """Comparable counts. Missingness never becomes a horse performance score."""
    if type(receipts) is not list or not receipts:raise HybridRejected("empty_receipts")
    items=sum(x["required_field_count"] for x in receipts)
    proven=sum(x["verified_field_count"] for x in receipts)
    return {"horses":len(receipts),"field_cells":items,
            "verified_cells":proven,"coverage_pct":round(proven*100/items,2),
            "horses_fully_verified":sum(x["complete"] for x in receipts),
            "conflicts":sum(len(x["conflict_fields"]) for x in receipts)}
