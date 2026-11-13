"""P3/P7 append-only, research-only model registry for hybrid evolution.

Registration is NOT training, independent EVO-07 certification, deployment,
real prediction or production activation. All source labels are user assertions.
A hash-chain detects mutations; an isolated lock serializes cooperating writers.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
from pathlib import Path

class RegistryRejected(ValueError):
    pass

ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
SHA=re.compile(r"^[0-9a-f]{64}$")
TYPES={"BASELINE","MODIFY","ADD","ENSEMBLE"}
SCHEMA="kyoto_p3p7_hybrid_model_registry.v1"
MAX_BYTES=3_000_000

def _encoded(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def _hash(obj):
    return hashlib.sha256(_encoded(obj)).hexdigest()

def _check_sha(value):
    return type(value) is str and SHA.fullmatch(value) is not None

def _check_spec(model, existing):
    needed={"model_id","kind","parents","feature_schema_sha256",
            "code_sha256","configuration_sha256","training_end_utc",
            "source_scope","weights_bps"}
    if type(model) is not dict or set(model)!=needed:
        raise RegistryRejected("model_spec_schema_invalid")
    mid=model["model_id"]
    if type(mid) is not str or not ID.fullmatch(mid) or mid in existing:
        raise RegistryRejected("model_identifier_invalid_or_duplicate")
    if any(not _check_sha(model[k]) for k in ("feature_schema_sha256",
                                                "code_sha256","configuration_sha256")):
        raise RegistryRejected("model_hash_invalid")
    if model["kind"] not in TYPES or model["source_scope"]!="LAB_RESEARCH_ONLY":
        raise RegistryRejected("unknown_kind_or_nonlab_scope")
    if model["training_end_utc"] is not None:
        from datetime import datetime,timezone
        try:
            d=datetime.fromisoformat(model["training_end_utc"].replace("Z","+00:00"))
        except (TypeError,ValueError,AttributeError) as exc:
            raise RegistryRejected("training_time_invalid") from exc
        if d.utcoffset()!=timezone.utc.utcoffset(None):
            raise RegistryRejected("training_time_not_utc")
    parents=model["parents"]
    weights=model["weights_bps"]
    if type(parents) is not list or any(type(p) is not str for p in parents) or len(parents)!=len(set(parents)):
        raise RegistryRejected("parents_invalid")
    if any(p not in existing for p in parents):
        raise RegistryRejected("parent_missing")
    if any(existing[p]["feature_schema_sha256"]!=model["feature_schema_sha256"] for p in parents):
        raise RegistryRejected("feature_schema_incompatible")
    kind=model["kind"]
    if kind=="BASELINE" and (parents or weights or model["training_end_utc"] is not None):
        raise RegistryRejected("baseline_must_be_root")
    if kind in ("MODIFY","ADD") and (len(parents)!=1 or weights):
        raise RegistryRejected("single_parent_required")
    if kind=="ENSEMBLE" and (
            not 2<=len(parents)<=4 or type(weights) is not list
            or len(weights)!=len(parents) or
            any(type(w) is not int or not 0<w<=10000 for w in weights)
            or sum(weights)!=10000):
        raise RegistryRejected("ensemble_fixed_weights_invalid")

def read_registry(path):
    path=Path(path)
    if path.is_symlink():
        raise RegistryRejected("registry_symlink_forbidden")
    if not path.exists():
        return {"events":[],"models":{},"head":"0"*64}
    if not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise RegistryRejected("registry_size_or_type_invalid")
    raw=path.read_bytes()
    if not raw or not raw.endswith(b"\n"):
        raise RegistryRejected("partial_or_empty_registry")
    events=[];models={};previous="0"*64
    for line in raw.splitlines():
        try:
            obj=json.loads(line.decode("utf-8"))
        except (ValueError,UnicodeError) as exc:
            raise RegistryRejected("corrupted_journal_line") from exc
        if type(obj) is not dict or set(obj)!={"schema","seq","prev_sha256","event","event_sha256"}:
            raise RegistryRejected("registry_event_schema_invalid")
        if (obj["schema"]!=SCHEMA or type(obj["seq"]) is not int
            or obj["seq"]!=len(events)+1 or obj["prev_sha256"]!=previous
            or obj["event_sha256"]!=_hash({k:v for k,v in obj.items() if k!="event_sha256"})):
            raise RegistryRejected("registry_chain_corrupted")
        event=obj["event"]
        if type(event) is not dict or set(event)!={"action","model"} or event["action"]!="REGISTER":
            raise RegistryRejected("unknown_event_type")
        model=event["model"]
        _check_spec(model,models)
        models[model["model_id"]]=model
        previous=obj["event_sha256"]
        events.append(obj)
    return {"events":events,"models":models,"head":previous}

def register_model(path, model):
    """Append one immutable research model. No activation or deployment API."""
    path=Path(path)
    if not path.parent.is_dir() or path.is_symlink():
        raise RegistryRejected("registry_parent_or_symlink_invalid")
    lock=path.with_name(path.name+".lock")
    try:
        descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:
        raise RegistryRejected("concurrent_writer_lock") from exc
    try:
        os.close(descriptor)
        state=read_registry(path)
        _check_spec(model,state["models"])
        event={"schema":SCHEMA,"seq":len(state["events"])+1,
               "prev_sha256":state["head"],
               "event":{"action":"REGISTER","model":model}}
        event["event_sha256"]=_hash(event)
        raw=_encoded(event)+b"\n"
        if (path.stat().st_size if path.exists() else 0)+len(raw)>MAX_BYTES:
            raise RegistryRejected("registry_capacity_exceeded")
        flags=os.O_WRONLY|os.O_CREAT|os.O_APPEND
        if hasattr(os,"O_NOFOLLOW"):
            flags|=os.O_NOFOLLOW
        fd=os.open(path,flags,0o600)
        try:
            with os.fdopen(fd,"ab",closefd=True) as out:
                out.write(raw)
                out.flush()
                os.fsync(out.fileno())
        finally:
            pass
        verified=read_registry(path)
        if verified["head"]!=event["event_sha256"]:
            raise RegistryRejected("append_verification_failed")
        return {"event_sha256":verified["head"],"model_id":model["model_id"],
                "registry_size":len(verified["events"]),
                "scope":"LAB_RESEARCH_ONLY","production_model_changed":False,
                "certified":False,"auto_promote":False}
    finally:
        lock.unlink(missing_ok=True)

def registered_model(path, model_id):
    state=read_registry(path)
    if model_id not in state["models"]:
        raise RegistryRejected("unknown_model")
    return {"model":state["models"][model_id],"registry_head_sha256":state["head"],
            "research_only":True,"independently_certified":False,
            "live_prediction_authorized":False}
