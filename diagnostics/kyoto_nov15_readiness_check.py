"""Offline Nov15 capture readiness: enumerate blockers BEFORE activation.

Never fetch JRA, invent official originals or certify claimed bytes.
A READY state means only that the offline operator inputs are consistent,
not that a live GET can succeed or that a real source has been authenticated.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from diagnostics.kyoto_nov14_nov15_second_day_handoff import (
    validate_day15_handoff, SecondDayRejected)

INPUTS = {
    "spec":"docs/diagnostics/nov15_pc_observed_race_spec.json",
    "roster":"docs/diagnostics/nov15_pc_current_roster.json",
    "selection":"docs/diagnostics/nov15_pc_official_selection.html",
    "meeting":"docs/diagnostics/nov15_pc_official_meeting.html",
    "start":"docs/diagnostics/nov15_pc_verified_start_utc.txt",
}
WORKFLOW=".github/workflows/kyoto-nov15-second-day-observed-oneshot.yml"
REQUIRED_TRIGGER="diagnostics/nov15_pc_explicit_activation.txt"

def readiness(root=".", *, clock_utc="2026-11-14T12:00:00Z", paths=None):
    base=Path(root)
    items=dict(INPUTS if paths is None else paths)
    if set(items)!=set(INPUTS):
        raise SecondDayRejected("readiness_input_keys_invalid")
    missing=[];invalid=[]
    originals={}
    for key,relative in items.items():
        if (type(relative) is not str or not re.fullmatch(
            r"docs/diagnostics/[A-Za-z0-9_./-]+\.(?:json|html|txt)",relative)
            or ".." in relative.split("/")):
            invalid.append("UNSAFE_PATH:"+key)
            continue
        p=base/relative
        if p.is_symlink():
            invalid.append("SYMLINK:"+key)
        elif not p.is_file():
            missing.append(key)
        elif p.stat().st_size>1_500_000 or p.stat().st_size==0:
            invalid.append("INVALID_SIZE:"+key)
        else:
            originals[key]=p.read_bytes()
    workflow=base/WORKFLOW
    if workflow.is_symlink() or not workflow.is_file():
        invalid.append("WORKFLOW_NOT_PRESENT")
    trigger=base/REQUIRED_TRIGGER
    if trigger.exists() or trigger.is_symlink():
        # This is a pre-activation guard. A premature marker is unsafe.
        invalid.append("PREMATURE_OR_ALREADY_CONSUMED_ACTIVATION")
    now=datetime.fromisoformat(clock_utc.replace("Z","+00:00"))
    if now.utcoffset()!=timedelta(0):
        raise SecondDayRejected("readiness_clock_must_be_utc")
    if now >= datetime(2026,11,16,0,0,tzinfo=timezone.utc):
        invalid.append("NOV15_OBSERVATION_DAY_EXPIRED")
    if not missing and not invalid:
        try:
            text=originals["start"].decode("utf8").strip()
            if not re.fullmatch(r"2026-11-15T[0-2]\d:[0-5]\d:[0-5]\dZ",text):
                raise SecondDayRejected("verified_start_format_invalid")
            end=datetime.fromisoformat(text.replace("Z","+00:00"))
            if end <= now+timedelta(minutes=10):
                raise SecondDayRejected("capture_cutoff_not_safely_in_future")
            report=validate_day15_handoff(
                spec_data=json.loads(originals["spec"].decode("utf8")),
                roster=json.loads(originals["roster"].decode("utf8")),
                official_selection_original=originals["selection"],
                official_meeting_original=originals["meeting"],
                verified_start_utc=text)
        except (SecondDayRejected,UnicodeError,ValueError,TypeError,KeyError) as exc:
            invalid.append("ORIGINAL_CHAIN_OR_RACE_INVALID:"+type(exc).__name__+":"+str(exc))
            report=None
    else:
        report=None
    return {
        "schema":"kyoto_nov15_zero_http_readiness.v1",
        "state":"OFFLINE_INPUTS_READY_NOT_SOURCE_AUTHENTICATED" if not missing and not invalid
            else "NOT_READY_FAIL_CLOSED",
        "missing":sorted(missing),
        "invalid":sorted(invalid),
        "race_day":"20261115",
        "can_execute_official_http_now":False,
        "source_authenticity_proven":False,
        "real_market_verified":False,
        "network_requests":0,
        "input_sha256":{key:hashlib.sha256(value).hexdigest()
                        for key,value in sorted(originals.items())},
        "provisional_source_receipt":report,
    }

def encrypted_pipeline_readiness(root=".", *, now_utc="2026-11-14T12:00:00Z",
                                 allow_activation=False):
    """Current secure design: original HTML is encrypted, not Git tracked.

    Only checks the inputs before an artifact is decrypted. Does not grant
    HTTP or claim authenticity. Existing readiness() is legacy offline fixture.
    """
    from diagnostics.jra_one_shot_market_capture import (
        ObservedRaceSpec,verified_roster_from_snapshot)
    from diagnostics.jra_market_source_chain import SourceChainError
    base=Path(root)
    files={
        "spec":"docs/diagnostics/nov15_pc_observed_race_spec.json",
        "roster":"docs/diagnostics/nov15_pc_current_roster.json",
        "start":"docs/diagnostics/nov15_pc_verified_start_utc.txt",
        "observer_run_id":"docs/diagnostics/nov15_observer_run_id.txt"}
    missing=[];invalid=[];contents={}
    for key,name in files.items():
        path=base/name
        if path.is_symlink():
            invalid.append("SYMLINK:"+key)
        elif not path.is_file():
            missing.append(key)
        elif not 0<path.stat().st_size<=1_500_000:
            invalid.append("SIZE:"+key)
        else:
            contents[key]=path.read_bytes()
    if (base/REQUIRED_TRIGGER).exists() and not allow_activation:
        invalid.append("PREMATURE_ACTIVATION")
    if not missing and not invalid:
        try:
            run_id=contents["observer_run_id"].decode("ascii").strip()
            if not re.fullmatch(r"[0-9]{5,20}",run_id):
                raise SecondDayRejected("observer_run_id_invalid")
            spec=ObservedRaceSpec(**json.loads(contents["spec"].decode("utf8"))).validate(
                require_channels=("PC",))
            if spec.race_day!="20261115":
                raise SecondDayRejected("wrong_race_day")
            roster=json.loads(contents["roster"].decode("utf8"))
            start=contents["start"].decode("ascii").strip()
            if not re.fullmatch(r"2026-11-15T[0-2]\d:[0-5]\d:[0-5]\dZ",start):
                raise SecondDayRejected("start_format_invalid")
            verified_roster_from_snapshot(roster,spec,race_start_utc=start)
            now=datetime.fromisoformat(now_utc.replace("Z","+00:00"))
            if now.utcoffset()!=timedelta(0):
                raise SecondDayRejected("now_must_be_utc")
            t=datetime.fromisoformat(start.replace("Z","+00:00"))
            if t<=now+timedelta(minutes=10):
                raise SecondDayRejected("cutoff_not_in_future")
        except (SecondDayRejected,SourceChainError,ValueError,TypeError,UnicodeError,KeyError) as exc:
            invalid.append("RACE_INPUTS_INVALID:"+str(exc))
    return {
        "schema":"kyoto_nov15_encrypted_pipeline_readiness.v1",
        "state":"INPUTS_READY_NEEDS_DECRYPTED_OFFICIAL_ORIGINAL_CHAIN" if not missing and not invalid else "NOT_READY",
        "missing":sorted(missing),"invalid":sorted(invalid),
        "http_authorized":False,"network_requests":0,
        "encrypted_observer_artifact_verified":False,
        "JRA_source_authenticated":False,
        "real_market_verified":False,
    }

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--mode",choices=("encrypted","legacy"),default="encrypted")
    p.add_argument("--allow-activation",action="store_true")
    p.add_argument("--now-utc",default=None)
    args=p.parse_args(argv)
    clock=args.now_utc or datetime.now(timezone.utc).isoformat()
    if args.mode=="encrypted":
        r=encrypted_pipeline_readiness(args.root,now_utc=clock,allow_activation=args.allow_activation)
    else:
        r=readiness(args.root,clock_utc=clock)
    print(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2))
    if r["state"] not in ("INPUTS_READY_NEEDS_DECRYPTED_OFFICIAL_ORIGINAL_CHAIN",
                          "OFFLINE_INPUTS_READY_NOT_SOURCE_AUTHENTICATED"):
        raise SystemExit(2)
    return r

if __name__=="__main__":
    main()
