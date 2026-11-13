"""Nov15 exact capture receipt gate; no HTTP, no false-green GitHub run.

Capture returning status CAPTURE_BLOCKED is a valid safe-stop, NOT a
successful verification. This module only tests the saved source chain
reported by the existing capturer; no independent source authentication.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime,timezone,timedelta
from pathlib import Path

class CaptureAcceptanceRejected(ValueError):
    pass

EXPECTED={"official_racecard.html":"racecard",
          "quinella_original.html":"quinella",
          "bracket_quinella_original.html":"bracket_quinella"}

def _utc(value, field):
    if type(value) is not str or not (value.endswith("Z") or value.endswith("+00:00")):
        raise CaptureAcceptanceRejected("capture_utc_invalid:"+field)
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (ValueError,TypeError) as exc:
        raise CaptureAcceptanceRejected("capture_utc_invalid:"+field) from exc
    if parsed.utcoffset()!=timedelta(0):
        raise CaptureAcceptanceRejected("capture_utc_invalid:"+field)
    return parsed

def _temporal_receipts(doc, by_step, expected_race_id):
    if (doc.get("schema_version")!="jra_one_shot_market_capture.v1"
        or doc.get("channel") not in ("PC","SP")):
        raise CaptureAcceptanceRejected("capture_receipt_schema_or_channel_invalid")
    start=_utc(doc.get("started_at_utc"),"started")
    race_start=_utc(doc.get("verified_start_utc"),"race_start")
    ended=_utc(doc.get("ended_at_utc"),"ended")
    if (not start<=ended<race_start-timedelta(minutes=10)
        or not expected_race_id.startswith(race_start.strftime("%Y-%m-%d")+"_" )):
        raise CaptureAcceptanceRejected("capture_run_not_prerace")
    for step,record in by_step.items():
        if type(record) is not dict:
            raise CaptureAcceptanceRejected("capture_step_invalid")
        observed=_utc(record.get("captured_at_utc"),step)
        if not start<=observed<=ended or observed>=race_start-timedelta(minutes=10):
            raise CaptureAcceptanceRejected("capture_market_not_prerace:"+step)
        if (record.get("http_status")!=200
            or record.get("method") not in ("GET","POST")
            or type(record.get("requested_url")) is not str
            or type(record.get("response_url")) is not str):
            raise CaptureAcceptanceRejected("capture_http_provenance_incomplete:"+step)
    return {"run_start_utc":start.isoformat(),"run_end_utc":ended.isoformat(),
            "verified_race_start_utc":race_start.isoformat()}

def assess_saved_capture(root, *, expected_race_id):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise CaptureAcceptanceRejected("capture_folder_invalid")
    receipt=root/"receipt.json"
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size>300_000:
        raise CaptureAcceptanceRejected("receipt_missing_or_invalid")
    try:
        doc=json.loads(receipt.read_text(encoding="utf8"))
    except (UnicodeError,ValueError,OSError) as exc:
        raise CaptureAcceptanceRejected("receipt_unreadable") from exc
    if not isinstance(doc,dict) or type(expected_race_id) is not str or doc.get("race_id")!=expected_race_id:
        raise CaptureAcceptanceRejected("race_identity_conflict")
    if (doc.get("state")!="SOURCE_FROZEN"
        or doc.get("pre_race_prices_accepted") is not True
        or not isinstance(doc.get("market_receipt"),dict)
        or doc["market_receipt"].get("classification")!="VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED"):
        raise CaptureAcceptanceRejected("no_complete_prerace_markets_safe_stop")
    if doc.get("prediction_ready") is not False or doc.get("training_ready") is not False:
        raise CaptureAcceptanceRejected("research_scope_misrepresented")
    attempts=doc.get("request_receipts")
    if not isinstance(attempts,list):
        raise CaptureAcceptanceRejected("request_receipts_missing")
    by_step={}
    for step in attempts:
        if not isinstance(step,dict) or type(step.get("step")) is not str:
            raise CaptureAcceptanceRejected("request_step_invalid")
        key=step["step"]
        if key in by_step:
            raise CaptureAcceptanceRejected("request_step_duplicate")
        by_step[key]=step
    timing=_temporal_receipts(doc,by_step,expected_race_id)
    sources={}
    for filename,step in EXPECTED.items():
        p=root/filename
        if (p.is_symlink() or not p.is_file() or
            not 0<p.stat().st_size<=1_500_000):
            raise CaptureAcceptanceRejected("original_missing_or_unsafe:"+filename)
        raw=p.read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        record=by_step.get(step)
        if (not isinstance(record,dict)
            or record.get("sha256")!=digest
            or type(record.get("bytes")) is not int
            or record.get("bytes")!=len(raw)):
            raise CaptureAcceptanceRejected("original_receipt_sha_or_size_mismatch:"+filename)
        sources[step]=digest
    return {
        "schema":"kyoto_nov15_capture_acceptance.v1",
        "scope":"CAPTURE_RECEIPT_CONSISTENCY_ONLY",
        "race_id":expected_race_id,
        "state":"OFFLINE_SOURCE_BYTES_MATCH_RECEIPT",
        "source_sha256":sources,
        "time_receipt":timing,
        "independent_official_source_authenticated":False,
        "real_market_independently_verified":False,
        "prediction_ready":False,
        "real_bet_authorized":False,
        "network_requests":0,
    }

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--directory",required=True)
    p.add_argument("--spec",required=True)
    args=p.parse_args(argv)
    path=Path(args.spec)
    if path.is_symlink() or not path.is_file():
        raise CaptureAcceptanceRejected("race_spec_file_invalid")
    try:
        spec=json.loads(path.read_text(encoding="utf8"))
    except (UnicodeError,ValueError) as exc:
        raise CaptureAcceptanceRejected("race_spec_json_invalid") from exc
    report=assess_saved_capture(args.directory,expected_race_id=spec.get("race_id"))
    print(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2))
    return report

if __name__=="__main__":
    main()
