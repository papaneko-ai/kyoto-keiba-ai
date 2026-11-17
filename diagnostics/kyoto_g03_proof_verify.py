"""Independently re-open a G03 source-only receipt and all 12 original racecards.

Run ONLY on a local/decrypted evidence directory; never upload plaintext to CI.
No HTTP requests. A successful synthetic test is not proof of a future event.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from diagnostics.kyoto_g03_all_races import links, parse, G03Error

class G03ProofRejected(ValueError):
    pass

def verify(root, *, expected_day=None):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():
        raise G03ProofRejected("unsafe_proof_root")
    receipt_path=root/"g03_receipt.json"
    meeting_path=root/"official_meeting.html"
    if any(p.is_symlink() for p in (receipt_path, meeting_path)):
        raise G03ProofRejected("unsafe_proof_links")
    try:
        report=json.loads(receipt_path.read_text(encoding="utf8"))
        meeting=meeting_path.read_bytes()
    except (OSError,UnicodeError,ValueError) as exc:
        raise G03ProofRejected("missing_or_invalid_proof") from exc
    day=report.get("day")
    if (type(day) is not str or not re.fullmatch(r"20[0-9]{6}",day)
        or expected_day is not None and day!=expected_day):
        raise G03ProofRejected("proof_day_mismatch")
    if report.get("schema")!="kyoto_g03_all_races.v1":
        raise G03ProofRejected("unknown_receipt_schema")
    if hashlib.sha256(meeting).hexdigest()!=report.get("meeting_sha256"):
        raise G03ProofRejected("meeting_sha_mismatch")
    observed=links(meeting,report.get("meeting_url",""),day)
    if sorted(observed)!=list(range(1,13)):
        raise G03ProofRejected("missing_official_race_links")
    entries=report.get("races")
    if type(entries) is not dict or set(entries)!={str(i) for i in range(1,13)}:
        raise G03ProofRejected("wrong_race_receipt_set")
    if report.get("complete") is not True or report.get("missing_races")!=[]:
        raise G03ProofRejected("partial_capture_not_verified")
    verified=[]
    for race in range(1,13):
        info=entries[str(race)]
        if type(info) is not dict or info.get("state")!="ROSTER_AND_START_VERIFIED_OFFLINE":
            raise G03ProofRejected("race_unverified:"+str(race))
        filename="official_racecard_%02d.html"%race
        if info.get("original_file")!=filename or info.get("source_url")!=observed[race]:
            raise G03ProofRejected("race_source_url_or_filename_mismatch:"+str(race))
        path=root/("g03_"+filename)
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=1_500_000:
            raise G03ProofRejected("race_original_missing:"+str(race))
        original=path.read_bytes()
        if hashlib.sha256(original).hexdigest()!=info.get("original_sha256"):
            raise G03ProofRejected("race_original_sha_mismatch:"+str(race))
        try:
            parsed=parse(original,day,race,observed[race],info.get("captured_at_utc"))
        except (G03Error,AttributeError,TypeError,ValueError) as exc:
            raise G03ProofRejected("race_reparse_failed:"+str(race)) from exc
        if (parsed["runner_count"]!=info.get("runner_count")
            or parsed["runners"]!=info.get("runners")
            or parsed["start_time_jst"]!=info.get("start_time_jst")
            or parsed["local_race_key"]!=info.get("local_race_key")):
            raise G03ProofRejected("race_receipt_content_mismatch:"+str(race))
        verified.append({"race":race,"runner_count":parsed["runner_count"],
                         "original_sha256":parsed["sha256"],"source_url_verified":True})
    return {"schema":"kyoto_g03_independent_reparse.v1",
            "day":day,"complete_source_originals":True,"races_verified":len(verified),
            "runner_count":sum(x["runner_count"] for x in verified),
            "race_original_sha256s":[x["original_sha256"] for x in verified],
            "live_jra_network_observed_by_this_verifier":False,
            "encrypted_artifact_authenticated_by_this_verifier":False,
            "prediction_ready":False}
