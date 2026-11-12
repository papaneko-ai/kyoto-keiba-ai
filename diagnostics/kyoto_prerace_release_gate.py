"""Fail-closed publication and market-readiness gate; no network operations.

Publication times must be independently confirmed for each race, not
inferred from generic schedules. This module never establishes actual
JRA provenance, scraping rights, or live paper-trade readiness.
"""
from datetime import datetime
import re

class ReleaseGateRejected(ValueError):
    pass

def _time(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ReleaseGateRejected("UTC_SECONDS_REQUIRED")
    try:
        return datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise ReleaseGateRejected("INVALID_DATETIME") from None

def evaluate(*, now_utc, race_start_utc, publication_not_before_utc,
             publication_stage, observed_stage, authority_confirmed,
             permission_confirmed, raw_source_verified,
             horse_numbers_verified, odds_verified, source_captured_utc):
    """Only an eligibility precheck, never authorization to freeze or wager."""
    now, start, announced, captured = (
        _time(v) for v in (now_utc, race_start_utc, publication_not_before_utc, source_captured_utc))
    if not all(type(x) is bool for x in
               (authority_confirmed, permission_confirmed, raw_source_verified,
                horse_numbers_verified, odds_verified)):
        raise ReleaseGateRejected("BOOLEAN_EVIDENCE_REQUIRED")
    stages = {"NOT_PUBLISHED":0, "ENTRIES_WITHOUT_NUMBERS":1,
              "NUMBERED_FIELD":2, "LIVE_MARKET":3}
    if publication_stage not in stages or publication_stage=="NOT_PUBLISHED":
        raise ReleaseGateRejected("UNKNOWN_PUBLICATION_STAGE")
    if observed_stage not in stages:
        raise ReleaseGateRejected("UNKNOWN_OBSERVED_STAGE")
    if not (authority_confirmed and permission_confirmed):
        return {"decision":"SAFE_STOP","reason":"AUTHORITY_OR_USAGE_PERMISSION_NOT_CONFIRMED"}
    if now < announced:
        return {"decision":"SAFE_STOP","reason":"BEFORE_OFFICIALLY_VERIFIED_PUBLICATION_TIME"}
    if not (captured <= now < start):
        return {"decision":"SAFE_STOP","reason":"SOURCE_FUTURE_OR_RACE_ALREADY_STARTED"}
    if not raw_source_verified:
        return {"decision":"SAFE_STOP","reason":"RAW_SOURCE_UNVERIFIED"}
    if stages[observed_stage] < stages[publication_stage]:
        return {"decision":"SAFE_STOP","reason":"REQUIRED_PUBLICATION_STAGE_NOT_OBSERVED"}
    if not horse_numbers_verified:
        return {"decision":"SAFE_STOP","reason":"HORSE_OR_BRACKET_IDENTITY_NOT_CONFIRMED"}
    if not odds_verified or observed_stage != "LIVE_MARKET":
        return {"decision":"SAFE_STOP","reason":"ACTUAL_PRERACE_ODDS_NOT_CONFIRMED"}
    return {"decision":"ELIGIBLE_FOR_FURTHER_INDEPENDENT_CHECKS_ONLY",
            "reason":"NOT_AN_AUTHORIZATION_TO_FREEZE_OR_BUY"}
