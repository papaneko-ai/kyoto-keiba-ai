"""G03 same-session 12R collection after the existing official observer.

Only exact same-day URLs observed in the saved meeting original are followed.
All new originals are flattened into the existing AES-GCM staging directory.
"""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
from diagnostics.kyoto_g03_all_races import acquire_all, CoverageRejected
from diagnostics.kyoto_nov15_two_original_observer import _read
from diagnostics.jra_one_shot_market_capture import RequestPacer

def collect_after_observer(*,original_root,day,opener,pacer=None):
    root=Path(original_root)
    meeting=root/"official_meeting.html"
    observer_receipt=root/"receipt.json"
    if not meeting.is_file() or not observer_receipt.is_file():
        return {"state":"G03_NO_SAVED_MEETING","complete":False,"network_requests_started":0}
    observer=json.loads(observer_receipt.read_text(encoding="utf8"))
    if observer.get("day")!=day or not observer.get("observed_meeting_url"):
        raise CoverageRejected("meeting_provenance_not_verified")
    race12_url=observer.get("observed_racecard_url")
    race12_file=root/"official_racecard.html"
    count=0
    reused=False
    last_utc=None
    pacing=pacer if pacer is not None else RequestPacer(min_gap_seconds=2.0)
    def fetch(url):
        nonlocal count,reused,last_utc
        if (url==race12_url and observer.get("racecard_number")==12
            and observer.get("racecard_original_fetched") is True and race12_file.is_file()):
            raw=race12_file.read_bytes()
            if sha256(raw).hexdigest()!=observer.get("racecard_sha256"):
                raise CoverageRejected("saved_race12_sha_mismatch")
            recorded=observer.get("racecard_captured_at_utc")
            if not recorded:
                raise CoverageRejected("reused_race12_original_timestamp_missing")
            last_utc=recorded
            reused=True
            return raw
        pacing.before_request()
        count+=1
        raw=_read(opener,url)
        last_utc=datetime.now(timezone.utc).isoformat()
        return raw
    staging=root/"g03_tmp"
    try:
        result=acquire_all(day=day,root=staging,meeting_raw=meeting.read_bytes(),
            meeting_url=observer["observed_meeting_url"],fetch=fetch,
            captured_at_utc=lambda:last_utc,allowed=True)
    finally:
        if staging.is_dir() and not staging.is_symlink():
            for f in sorted(staging.iterdir()):
                if not f.is_file() or f.is_symlink():
                    raise CoverageRejected("unsafe_g03_staging_entry")
                dest=root/("g03_"+f.name)
                if dest.exists() or dest.is_symlink():
                    raise CoverageRejected("g03_destination_collision")
                f.rename(dest)
            staging.rmdir()
    result["network_requests_started"]=count
    result["race12_original_reused"]=reused
    result["prediction_ready"]=False
    (root/"g03_receipt.json").write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    return result
