"""Offline P1 consistency gate for independently supplied prerace records.

Only corroborates structured evidence; it NEVER enables live betting or asserts
that user-supplied metadata is authenticated JRA evidence.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from math import isfinite

HEX = re.compile(r"[0-9a-f]{64}\Z")
HORSE = re.compile(r"[0-9A-Za-z_-]{4,64}\Z")


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp_invalid") from exc
    if t.tzinfo is None or t.utcoffset() != timedelta(0):
        raise ValueError("timestamp_not_utc")
    return t.astimezone(timezone.utc)


def _digest(data):
    return sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def evaluate(snapshot, *, observed_utc):
    """Fail closed. A PASS is only structural, NEVER official source approval."""
    reasons = []
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "kyoto_p1_prerace_snapshot.v1":
        return {"status": "BLOCKED", "reasons": ["schema_invalid"],
                "prediction_ready": False, "network_requests": 0}
    try:
        now = _utc(observed_utc)
        captured = _utc(snapshot.get("captured_utc"))
        start = _utc(snapshot.get("scheduled_start_utc"))
        cutoff = _utc(snapshot.get("prediction_cutoff_utc"))
        meeting = snapshot.get("meeting_date")
        if not isinstance(meeting, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meeting):
            raise ValueError("meeting_date_invalid")
        date = datetime.strptime(meeting, "%Y-%m-%d").date()
        if (start + timedelta(hours=9)).date() != date:
            reasons.append("start_meeting_date_mismatch")
        if not captured < cutoff < start:
            reasons.append("prerace_time_order_invalid")
        if captured > now:
            reasons.append("future_capture")
    except (ValueError, TypeError, OverflowError) as exc:
        reasons.append(str(exc) if str(exc).startswith("timestamp") else "date_invalid")
    race = snapshot.get("race")
    if type(race) is not int or not 1 <= race <= 12:
        reasons.append("race_invalid")
    sources = snapshot.get("sources")
    if not isinstance(sources, dict) or set(sources) != {"racecard", "odds"}:
        reasons.append("source_pair_missing")
    else:
        for name in ("racecard", "odds"):
            item = sources[name]
            if not isinstance(item, dict) or not HEX.fullmatch(str(item.get("sha256", ""))):
                reasons.append(f"{name}_sha_invalid")
            else:
                try:
                    time = _utc(item.get("captured_utc"))
                    if time > captured:
                        reasons.append(f"{name}_later_than_snapshot")
                    if time >= cutoff:
                        reasons.append(f"{name}_after_cutoff")
                except (ValueError, UnboundLocalError):
                    reasons.append(f"{name}_timestamp_invalid")
    runners = snapshot.get("runners")
    if not isinstance(runners, list) or len(runners) < 2 or len(runners) > 18:
        reasons.append("runner_roster_invalid")
    else:
        nums, ids = [], []
        for item in runners:
            if not isinstance(item, dict):
                reasons.append("runner_invalid")
                continue
            number, horse_id, name = item.get("number"), item.get("horse_id"), item.get("name")
            if type(number) is not int or not 1 <= number <= 18:
                reasons.append("runner_number_invalid")
            else:
                nums.append(number)
            if not isinstance(horse_id, str) or not HORSE.fullmatch(horse_id):
                reasons.append("runner_id_invalid")
            else:
                ids.append(horse_id)
            if not isinstance(name, str) or not name.strip():
                reasons.append("runner_name_missing")
        if len(nums) != len(set(nums)) or len(ids) != len(set(ids)):
            reasons.append("runner_identity_duplicate")
        odds = snapshot.get("odds")
        if not isinstance(odds, list) or not odds:
            reasons.append("odds_missing")
        else:
            seen_pairs = set()
            for pair in odds:
                if not isinstance(pair, dict):
                    reasons.append("odds_pair_invalid")
                    continue
                a, b, value = pair.get("first"), pair.get("second"), pair.get("decimal")
                if type(a) is not int or type(b) is not int or a == b or a not in nums or b not in nums:
                    reasons.append("odds_pair_unknown_runner")
                    continue
                key = tuple(sorted((a, b)))
                if key in seen_pairs:
                    reasons.append("odds_pair_duplicate")
                seen_pairs.add(key)
                if type(value) not in (float, int) or not isfinite(value) or not 1.0 < value < 100000:
                    reasons.append("odds_value_invalid")
    unique = sorted(set(reasons))
    return {"status": "STRUCTURAL_CHECK_ONLY" if not unique else "BLOCKED",
            "reasons": unique, "prediction_ready": False, "network_requests": 0,
            "snapshot_sha256": _digest(snapshot),
            "runner_count": len(runners) if isinstance(runners, list) else 0,
            "unverified": ["JRA_source_authenticity", "actual_official_race_time",
                           "market_completeness", "scratches_and_sales_status",
                           "official_access_permission"]}
