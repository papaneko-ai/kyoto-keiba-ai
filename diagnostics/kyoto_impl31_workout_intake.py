"""Offline-only workout intake contract. No network/source approval implied.

Accepts a canonical JSON export from a separately authorized data adapter.
A canonical export is NOT the provider's raw original. Preserve and verify
both bytes and their hashes; the caller must independently verify the adapter
and the right to use the provider. Never feeds production coverage directly.
"""
from datetime import datetime, date, timezone, timedelta
from hashlib import sha256
import json
import math
import re

MAX_BYTES = 4_000_000
SOURCES = {"JRA_VAN", "JRDB", "OTHER_AUTHORIZED"}
FIELDS = {"number", "name", "workouts"}
WORKOUT_FIELDS = {"training_date", "course", "distance_m", "elapsed_s"}

def utc(value):
    if not isinstance(value, str):
        raise ValueError("utc_required")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.utcoffset() != timedelta(0):
        raise ValueError("utc_required")
    return t

def hash_bytes(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("invalid_bytes")
    return sha256(raw).hexdigest()

def unique_keys(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate_json_key")
        d[k] = v
    return d

def bad_number(value):
    raise ValueError("nonfinite_json")

def inspect_workouts(*, original, canonical, expected_day, race_number,
                     expected_roster, verified_start_utc, captured_utc,
                     expected_original_sha256, expected_canonical_sha256):
    """Validate canonical records against an already independently checked roster.

    Expected roster maps int horse numbers to exact published names. An empty
    workout list is missing, not a zero-time observation. A bad/missing horse
    must not discard correctly identified other horses. No claims of verified
    adapter authenticity, source permission, or actual acquisition are made.
    """
    if hash_bytes(original) != expected_original_sha256 or hash_bytes(canonical) != expected_canonical_sha256:
        raise ValueError("source_hash_mismatch")
    if not isinstance(expected_day, str) or not re.fullmatch(r"20\d{6}", expected_day):
        raise ValueError("day_identity")
    day = date.fromisoformat(f"{expected_day[:4]}-{expected_day[4:6]}-{expected_day[6:]}")
    if type(race_number) is not int or not 1 <= race_number <= 12:
        raise ValueError("race_identity")
    if not isinstance(expected_roster, dict) or not 2 <= len(expected_roster) <= 18 or any(type(n) is not int or not 1 <= n <= 18 or not isinstance(s, str) or not s.strip() for n,s in expected_roster.items()):
        raise ValueError("roster_identity")
    cutoff, stamp = utc(verified_start_utc), utc(captured_utc)
    jst = timezone(timedelta(hours=9))
    if cutoff.astimezone(jst).date() != day or stamp >= cutoff:
        raise ValueError("not_prerace")
    obj = json.loads(canonical.decode("utf-8"), object_pairs_hook=unique_keys, parse_constant=bad_number)
    if not isinstance(obj,dict) or set(obj) != {"schema", "source", "day", "venue", "race", "original_sha256", "horses"} or obj["schema"] != "kyoto_workout_canonical.v1" or obj["source"] not in SOURCES or obj["day"] != expected_day or obj["venue"] != "08" or type(obj["race"]) is not int or obj["race"] != race_number or obj["original_sha256"] != expected_original_sha256 or not isinstance(obj["horses"],list) or len(obj["horses"]) > 18:
        raise ValueError("canonical_identity")
    per = {str(n): {"state":"MISSING"} for n in sorted(expected_roster)}
    seen = set()
    for row in obj["horses"]:
        if not isinstance(row,dict) or type(row.get("number")) is not int or row["number"] not in expected_roster:
            raise ValueError("unexpected_horse_identity")
        n = row["number"]
        if n in seen:
            raise ValueError("duplicate_horse_identity")
        seen.add(n)
        if set(row) != FIELDS or row["name"] != expected_roster[n]:
            per[str(n)] = {"state":"HORSE_IDENTITY_MISMATCH"}
            continue
        runs = row["workouts"]
        if not isinstance(runs,list) or len(runs)>128:
            per[str(n)] = {"state":"INVALID_WORKOUTS"}
            continue
        if not runs:
            continue
        try:
            keys = set()
            for run in runs:
                if not isinstance(run,dict) or set(run)!=WORKOUT_FIELDS:
                    raise ValueError("workout_fields")
                dt = date.fromisoformat(run["training_date"])
                if not day-timedelta(days=31) <= dt < day or dt > stamp.astimezone(jst).date():
                    raise ValueError("workout_date")
                if not isinstance(run["course"],str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,24}",run["course"]):
                    raise ValueError("course")
                distance, elapsed = run["distance_m"],run["elapsed_s"]
                if type(distance) is not int or not 100 <= distance <= 4000 or type(elapsed) not in (int,float) or not math.isfinite(elapsed) or not 0 < elapsed <= 600:
                    raise ValueError("workout_value")
                k = (run["training_date"],run["course"],distance,elapsed)
                if k in keys:
                    raise ValueError("duplicate_workout")
                keys.add(k)
            normalized=sorted(runs,key=lambda r:(r["training_date"],r["course"],r["distance_m"],r["elapsed_s"]))
            digest=sha256(json.dumps(normalized,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
            per[str(n)]={"state":"CANONICAL_RECORD_VALID", "record_count":len(normalized), "value_digest":digest, "original_sha256":expected_original_sha256,"canonical_sha256":expected_canonical_sha256,"captured_utc":stamp.isoformat()}
        except (ValueError,TypeError,KeyError,OverflowError):
            per[str(n)]={"state":"INVALID_WORKOUTS"}
    count=sum(x["state"]=="CANONICAL_RECORD_VALID" for x in per.values())
    return {"schema":"kyoto_workout_intake_audit.v1","day":expected_day,"race":race_number,"source":obj["source"],"horse_denominator":len(expected_roster),"canonical_valid_horses":count,"canonical_missing_horses":len(expected_roster)-count,"horses":per,"canonical_records_cover_roster":count==len(expected_roster),"adapter_source_binding_verified":False,"source_permission_verified":False,"live_acquisition_certified":False,"production_coverage_authorized":False}
