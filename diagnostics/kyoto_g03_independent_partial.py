"""Independently certify each saved G03 race without declaring 12R complete.

Does NOT replace the original all-12 G03 verifier. Used only to preserve
valid source inputs when unrelated race capture fails. No HTTP; no invented
links. All source SHA, roster identity, UTC and per-race cutoff rechecked.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from diagnostics.kyoto_g03_all_races import links,parse,G03Error

class PartialProofRejected(ValueError): pass
JST=timezone(timedelta(hours=9))

def verify_partial(root,*,expected_day):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():
        raise PartialProofRejected("unsafe_proof_root")
    rp=root/"g03_receipt.json"
    mp=root/"official_meeting.html"
    if any(p.is_symlink() or not p.is_file() for p in (rp,mp)):
        raise PartialProofRejected("missing_or_unsafe_meeting_receipt")
    try:
        report=json.loads(rp.read_text(encoding="utf8"))
        meeting=mp.read_bytes()
    except (OSError,UnicodeError,ValueError) as exc:
        raise PartialProofRejected("invalid_meeting_receipt") from exc
    day=report.get("day")
    if (type(day) is not str or not re.fullmatch(r"20[0-9]{6}",day)
        or day!=expected_day):
        raise PartialProofRejected("proof_day_mismatch")
    if report.get("schema")!="kyoto_g03_all_races.v1":
        raise PartialProofRejected("unknown_receipt_schema")
    if hashlib.sha256(meeting).hexdigest()!=report.get("meeting_sha256"):
        raise PartialProofRejected("meeting_sha_mismatch")
    observed=links(meeting,report.get("meeting_url",""),day)
    entries=report.get("races")
    if not isinstance(entries,dict) or set(entries)!={str(r) for r in range(1,13)}:
        raise PartialProofRejected("wrong_race_receipt_set")
    verified=[]
    excluded=[]
    for race in range(1,13):
        item=entries[str(race)]
        if not isinstance(item,dict):
            excluded.append({"race":race,"reason":"INVALID_RECEIPT"});continue
        if item.get("state")!="ROSTER_AND_START_VERIFIED_OFFLINE":
            excluded.append({"race":race,"reason":"NOT_VERIFIED_G03"});continue
        try:
            filename=f"official_racecard_{race:02d}.html"
            if (race not in observed or item.get("source_url")!=observed[race]
                or item.get("original_file")!=filename):
                raise PartialProofRejected("source_link_or_filename_mismatch")
            p=root/("g03_"+filename)
            if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=1_500_000:
                raise PartialProofRejected("source_original_missing_or_invalid")
            raw=p.read_bytes()
            sha=hashlib.sha256(raw).hexdigest()
            if sha!=item.get("original_sha256"):
                raise PartialProofRejected("source_sha_mismatch")
            utc=item.get("captured_at_utc")
            parsed=parse(raw,day,race,observed[race],utc)
            if (parsed["runner_count"]!=item.get("runner_count")
                or parsed["runners"]!=item.get("runners")
                or parsed["start_time_jst"]!=item.get("start_time_jst")
                or parsed["local_race_key"]!=item.get("local_race_key")):
                raise PartialProofRejected("source_content_mismatch")
            acquired=datetime.fromisoformat(utc.replace("Z","+00:00"))
            post=datetime.fromisoformat(
                f"{day[:4]}-{day[4:6]}-{day[6:]}T{parsed['start_time_jst']}:00"
            ).replace(tzinfo=JST).astimezone(timezone.utc)
            if acquired>=post:
                raise PartialProofRejected("post_start_source_not_reusable")
            verified.append(race)
        except (PartialProofRejected,G03Error,ValueError,TypeError,KeyError,AttributeError,OSError) as exc:
            excluded.append({"race":race,"reason":type(exc).__name__,
                             "detail":str(exc)[:120]})
    return {"schema":"kyoto_g03_racewise_partial_evidence.v1",
            "day":day,"verified_race_numbers":verified,
            "verified_race_count":len(verified),"excluded_races":excluded,
            "all_12_races_verified":len(verified)==12,
            "prediction_ready":False,"live_jra_network_observed":False}
