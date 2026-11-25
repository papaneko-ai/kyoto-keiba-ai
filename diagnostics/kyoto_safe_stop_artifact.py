"""Save a truthful no-HTTP stop receipt without depending on capture artifacts.

This fallback writes no JRA source HTML and grants zero operational credit.
It is deliberately independent of the PC and SP collector implementations.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path


def record_pre_http_stop(destination, *, race_day, reason, http_count_known=True):
    if type(http_count_known) is not bool:
        raise ValueError("invalid_http_count_certainty")
    root = Path(destination)
    if root.is_symlink():
        raise ValueError("safe_stop_destination_symlink")
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError("safe_stop_destination_invalid")
    target = root / "safe_stop.json"
    if target.is_symlink():
        raise ValueError("safe_stop_target_symlink")
    payload = {
        "schema": "kyoto_safe_stop.v1",
        "race_day": race_day,
        "reason": reason,
        "state": "NO_CAPTURE_OR_PRE_HTTP_STOP" if http_count_known else "NO_SOURCE_HTTP_UNVERIFIED",
        "JRA_success": False,
        "actual_jra_http_requests": 0 if http_count_known else "UNKNOWN",
        "official_originals_authenticated": False,
        "operational_credit": 0,
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    # Exclusive creation: an existing receipt must never be silently rewritten.
    with target.open("x", encoding="utf8") as output:
        json.dump(payload, output, sort_keys=True, ensure_ascii=False)
        output.write("\n")
    return payload
