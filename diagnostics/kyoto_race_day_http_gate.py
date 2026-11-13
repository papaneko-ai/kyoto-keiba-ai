"""Fail-closed independent race-day clock gate, before all external JRA HTTP."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

class DayGateRejected(ValueError):
    pass

def require_race_day_window(*, now, race_day, not_before_utc, latest_utc, run_attempt, event_name):
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DayGateRejected("UTC_AWARE_CLOCK_REQUIRED_NO_HTTP")
    if now.utcoffset() != timedelta(0):
        raise DayGateRejected("NON_UTC_CLOCK_NO_HTTP")
    if race_day not in ("20261114","20261115"):
        raise DayGateRejected("UNAUTHORIZED_RACE_DAY_NO_HTTP")
    if now.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d") != race_day:
        raise DayGateRejected("WRONG_JAPAN_RACE_DAY_NO_HTTP")
    if run_attempt != "1":
        raise DayGateRejected("RERUN_BLOCKED_NO_HTTP")
    if event_name not in ("push", "schedule", "workflow_dispatch"):
        raise DayGateRejected("UNRECOGNIZED_EVENT_NO_HTTP")
    for value in (not_before_utc,latest_utc):
        if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset()!=timedelta(0):
            raise DayGateRejected("WINDOW_MUST_BE_UTC_NO_HTTP")
    if not (not_before_utc <= now < latest_utc):
        raise DayGateRejected("OUTSIDE_OBSERVED_WINDOW_NO_HTTP")
    return {"race_day":race_day, "date_gate_passed":True, "external_http_permitted_by_date_only":False}
