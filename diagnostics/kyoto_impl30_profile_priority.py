"""Conservative profile budget using only independently verified G03 start times.

No new network, no new race cutoff, no release authorization. Expired markets
are not allowed to consume the profile budget of later eligible races.
"""
from datetime import datetime, timedelta, timezone
import math

# Existing G06 cutoff is start minus ten minutes. Six observed GETs at
# timeout 20s plus 2s pacer, one in-flight profile and track GET, 30s overhead.
MARKET_RESERVE_SECONDS = 6 * 22 + 2 * 22 + 30

def profile_deadline(records, *, wall_utc, mono_now, original_deadline):
    if not isinstance(wall_utc, datetime) or wall_utc.tzinfo is None or wall_utc.utcoffset() is None:
        raise ValueError("wall_clock_not_aware")
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0
           for v in (mono_now,original_deadline)):
        raise ValueError("invalid_monotonic_budget")
    upcoming=[]
    for number, item in records.items():
        if item is None:
            continue
        if type(number) is not int or not 1<=number<=12 or not isinstance(item,dict):
            raise ValueError("invalid_verified_race_record")
        value=item.get("verified_start_utc")
        if not isinstance(value,str):
            raise ValueError("missing_verified_start")
        start=datetime.fromisoformat(value.replace("Z","+00:00"))
        if start.tzinfo is None or start.utcoffset()!=timedelta(0):
            raise ValueError("verified_start_not_utc")
        cutoff=start-timedelta(minutes=10)
        seconds=(cutoff-wall_utc.astimezone(timezone.utc)).total_seconds()
        if seconds>0:
            upcoming.append((seconds,number,cutoff.isoformat()))
    if not upcoming:
        return {"deadline_monotonic":original_deadline,"reason":"NO_UPCOMING_ELIGIBLE_MARKET",
                "earliest_race":None,"reserve_seconds":MARKET_RESERVE_SECONDS}
    seconds,number,cutoff=min(upcoming)
    deadline=min(original_deadline, max(mono_now,mono_now+seconds-MARKET_RESERVE_SECONDS))
    return {"deadline_monotonic":deadline,"reason":"MARKET_CUTOFF_PRIORITY" if deadline<original_deadline else "ORIGINAL_PROFILE_CAP",
            "earliest_race":number,"verified_market_cutoff_utc":cutoff,"reserve_seconds":MARKET_RESERVE_SECONDS}
