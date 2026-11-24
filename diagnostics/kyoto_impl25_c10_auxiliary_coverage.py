"""C10: source-grounded auxiliary data availability, never synthetic workout.

Read-only analysis of *saved* racecards and official Kyoto track evidence.
No JRA HTTP, no guessed independent source, no modification of raw originals.
The report is intentionally not a substitute for G03/G05 independent audits.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json

FIELDS=("weather","turf_going","dirt_going",
        "horse_body_weight_kg","horse_body_weight_change_kg","workout")
WORKOUT_REASON="SOURCE_NOT_INDEPENDENTLY_OBSERVED"

def _receipt(root,name,day,schema):
    p=root/name
    if p.is_symlink() or not p.is_file():
        return None
    try:
        result=json.loads(p.read_text(encoding="utf8"))
    except (OSError,ValueError,UnicodeError):
        return None
    return result if isinstance(result,dict) and result.get("day")==day and result.get("schema")==schema else None

def _sha_saved(root,name,digest):
    if not isinstance(name,str) or name.startswith(".") or "/" in name or "\\" in name:
        return False
    p=root/name
    return (isinstance(digest,str) and len(digest)==64 and
            p.is_file() and not p.is_symlink() and
            hashlib.sha256(p.read_bytes()).hexdigest()==digest)

def assess(root,day):
    if day not in ("20261121","20261122","20261128","20261129"):
        raise ValueError("invalid_day")
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_source_root")
    g05=_receipt(root,"g05_receipt.json",day,"kyoto_g05_source_evidence.v1")
    track=_receipt(root,"g05_track_receipt.json",day,"kyoto_g05_kyoto_track.v1")
    per_race={}
    totals={f:{"observed_with_saved_original":0,"missing_or_unverified":0}
            for f in FIELDS}
    for race in range(1,13):
        part=(g05 or {}).get("races",{}).get(str(race))
        counts={f:{"observed":0,"missing":0} for f in FIELDS}
        state="RACECARD_AUXILIARY_NOT_VERIFIED"
        if isinstance(part,dict):
            proof=_sha_saved(root,f"g03_official_racecard_{race:02d}.html",
                             part.get("original_sha256"))
            if proof:
                state="G05_RACECARD_ORIGINAL_SHA_MATCHES"
                trackfields=part.get("track",{})
                horses=part.get("horses",{})
                for field in ("weather","turf_going","dirt_going"):
                    item=trackfields.get(field,{}) if isinstance(trackfields,dict) else {}
                    ok=(isinstance(item,dict) and item.get("state")=="OBSERVED"
                        and item.get("value") is not None
                        and item.get("source_sha256")==part["original_sha256"]
                        and item.get("source_original")==f"g03_official_racecard_{race:02d}.html")
                    counts[field]["observed" if ok else "missing"]+=1
                if isinstance(horses,dict):
                    for horse in horses.values():
                        if not isinstance(horse,dict):
                            continue
                        for field,key in (("horse_body_weight_kg","body_weight_kg"),
                                          ("horse_body_weight_change_kg","body_weight_change_kg")):
                            item=horse.get(key)
                            ok=(isinstance(item,dict) and item.get("state")=="OBSERVED"
                                and item.get("value") is not None
                                and item.get("source_sha256")==part["original_sha256"]
                                and item.get("source_original")==f"g03_official_racecard_{race:02d}.html")
                            counts[field]["observed" if ok else "missing"]+=1
                        # Never infer workout from prior-run or training-like
                        # text without a separately verified source.
                        counts["workout"]["missing"]+=1
        for field in FIELDS:
            totals[field]["observed_with_saved_original"]+=counts[field]["observed"]
            totals[field]["missing_or_unverified"]+=counts[field]["missing"]
        per_race[str(race)]={"state":state,"fields":counts}
    track_source_verified=bool(
        track and track.get("same_day_official_meeting_heading_verified") is True
        and _sha_saved(root,"g05_official_kyoto_track.html",track.get("source_sha256"))
    )
    return {
        "schema":"kyoto_impl25_auxiliary_source_coverage.v1",
        "day":day,"source_only":True,"prediction_ready":False,
        "g05_saved_receipt_available":g05 is not None,
        "g05_kyoto_track_independent_source_original_sha_verified":track_source_verified,
        "g05_kyoto_track_same_day_values":(
            {k:track.get(k) for k in ("weather","turf_going","dirt_going")}
            if track_source_verified else
            {"weather":None,"turf_going":None,"dirt_going":None}),
        "workout_source_independently_verified":False,
        "workout_source_state":WORKOUT_REASON,
        "workout_missing_values_never_zero":True,
        "no_auxiliary_http_started":True,
        "no_unverified_source_promoted":True,
        "per_race":per_race,"totals":totals,
        "official_sources":{
            "g03_racecard":"JRA_PC_SAVED_ORIGINAL_SHA_CHECKED_IF_PRESENT",
            "g05_independent_kyoto_track":"FIXED_JRA_TRACK_PAGE_SAME_DAY_SHA_CHECK_IF_PRESENT",
            "workout":"NO_INDEPENDENTLY_CONFIRMED_SOURCE",
        },
    }

def save(root,day):
    root=Path(root)
    report=assess(root,day)
    p=root/"c10_auxiliary_coverage_receipt.json"
    if p.exists() or p.is_symlink():
        raise ValueError("auxiliary_receipt_already_exists")
    p.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return report
