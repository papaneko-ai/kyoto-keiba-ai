"""Re-audit preserved JRA 2026-11-07 Kyoto *pre-race roster* snapshots.

This does not reconstruct unavailable original HTML, authenticate latest scratches,
claim historical pre-race market quotes, or create backdated predictions/bets.
Its purpose is to bound F03 and F04 independently and produce a fail-closed,
explainable day-level readiness receipt from previously preserved data.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/"docs"/"diagnostics"
EXPECTED={1:9,2:15,3:13,4:15,5:8,6:11,7:11,8:9,9:10,10:14,11:16,12:17}
BASE_DAY="2026-11-07"
DAY_LIMIT=datetime(2026,11,7,tzinfo=timezone.utc)
SHA=re.compile(r"^[0-9a-f]{64}$")
class RosterAuditRejected(ValueError):pass

def file_for(race):
    if race==7:return DOC/"JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json"
    if race in (1,6,12):return DOC/"multirace_20261106"/f"kyoto_{race:02d}_snapshot.json"
    return DOC/"remaining8_20261106"/f"kyoto_{race:02d}_snapshot.json"

def _digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,
      separators=(",",":"),allow_nan=False).encode()).hexdigest()

def inspect_day(*,read=None):
    if read is None:read=lambda p:p.read_bytes()
    originals=[];sample=[]
    overall_runner=0;overall_prior=0
    all_sha=set()
    # Each of the 12 snapshots must be anchored in a distinct original HTML SHA.
    for race in range(1,13):
        filename=file_for(race)
        contents=read(filename)
        if not isinstance(contents,bytes):raise RosterAuditRejected("reader_must_return_bytes")
        try:r=json.loads(contents)
        except (TypeError,ValueError) as e:raise RosterAuditRejected("snapshot_json_corrupt") from e
        if (r.get("race_number")!=race or r.get("venue")!="KYOTO"
            or r.get("race_date")!=BASE_DAY):
            raise RosterAuditRejected("race_identity_mismatch")
        src=r.get("source_sha256")
        if type(src) is not str or not SHA.fullmatch(src) or src in all_sha:
            raise RosterAuditRejected("source_sha_missing_or_duplicate")
        all_sha.add(src)
        stamp=r.get("fetched_at_utc",r.get("captured_at_utc"))
        if not isinstance(stamp,str):
            raise RosterAuditRejected("capture_timestamp_absent")
        try:when=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        except ValueError as e:raise RosterAuditRejected("timestamp_invalid") from e
        if when.tzinfo is None or when.astimezone(timezone.utc)>=DAY_LIMIT:
            raise RosterAuditRejected("snapshot_not_before_meeting_date")
        horses=r.get("runners")
        if type(horses) is not list or len(horses)!=EXPECTED[race] or r.get("runner_count")!=len(horses):
            raise RosterAuditRejected("runner_count_invalid")
        seen_names=set()
        prior=0
        for i,h in enumerate(horses,1):
            if type(h) is not dict:
                raise RosterAuditRejected("bad_horse")
            name=h.get("horse_name")
            num=h.get("horse_number")
            frame=h.get("frame_number")
            href=h.get("horse_profile_href")
            if (type(num) is not int or num!=i
                or type(frame) is not int or not 1<=frame<=8
                or type(name) is not str or not name or name in seen_names
                or type(href) is not str or not href.startswith("/JRADB/accessU.html?CNAME=")):
                raise RosterAuditRejected("bad_runner_identity")
            seen_names.add(name)
            history=h.get("prior_race_dates",h.get("past_race_dates"))
            if type(history) is not list or any(type(dt) is not str or
               not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",dt) or dt>=BASE_DAY for dt in history):
                raise RosterAuditRejected("invalid_or_future_history")
            prior+=len(history)
        if "prior_date_count" in r and r["prior_date_count"]!=prior:
            raise RosterAuditRejected("prior_row_mismatch")
        if r.get("errors",r.get("parse_errors",[]))!=[]:
            raise RosterAuditRejected("parser_errors_not_empty")
        for flag in ("prediction_ready","ready_for_prediction","training_ready","ready_for_training"):
            if flag in r and r[flag] is not False:
                raise RosterAuditRejected("false_prediction_readiness_claim")
        overall_runner+=len(horses);overall_prior+=prior
        originals.append({
            "race":race,"runner_count":len(horses),
            "prior_dates_count":prior,"source_sha256":src,
            "snapshot_sha256":hashlib.sha256(contents).hexdigest(),
            "source_captured_at_utc":when.isoformat().replace("+00:00","Z")})
        sample.append(r)
    if overall_runner!=148 or overall_prior!=396:
        raise RosterAuditRejected("pre_race_day_totals_mismatch")
    accepted=json.loads(read(DOC/"JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json"))
    if (accepted.get("race_count")!=12 or accepted.get("runner_count")!=148
        or accepted.get("prior_date_count")!=396
        or {int(k):v for k,v in accepted["counts_by_race"].items()}!=EXPECTED
        or accepted.get("html_bytes_independently_verified_by_ci") is not False
        or accepted.get("prediction_ready") is not False
        or accepted.get("training_ready") is not False):
        raise RosterAuditRejected("baseline_receipt_mismatch")
    result={
      "schema":"kyoto_20261107_real_prerace_roster_offline_reaudit.v1",
      "meeting_date":BASE_DAY,"venue":"KYOTO","races_checked":12,
      "runners_checked":148,"prior_race_dates_checked":396,
      "real_historic_pre_race_snapshot_receipts_present":True,
      "original_html_bytes_independently_verified_here":False,
      "permanent_horse_ids_all_verified":False,
      "scratch_and_exclusion_status_all_verified":False,
      "required_all_runner_features_verified":False,
      "actual_prerace_quinella_bracket_odds_verified":False,
      "F03_fixed_gate_accepted":False,
      "F04_fixed_gate_accepted":False,
      "ready_for_prediction":False,
      "real_paper_trade_registered":False,
      "snapshot_sources":originals,
      "necessary_next_steps":[
        "independently validate each original HTML byte stream versus saved SHA",
        "complete and validate all required features, official permanent ID and scratches",
        "capture genuine pre-race dual-market odds with preserved source and UTC",
        "prove source-observed-before-start and actual freeze operation, never backdate"],
      "no_new_JRA_network_requests":True
    }
    return {**result,"receipt_sha256":_digest(result)}
