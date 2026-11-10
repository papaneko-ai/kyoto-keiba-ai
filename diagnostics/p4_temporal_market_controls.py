"""P4-03: strict offline market freshness / scratches / drift / takeout gate.

Reuses P1 three-HTML byte-verified intake; does not independently authenticate
JRA origin, official sales, scratch state or a jurisdictional takeout policy.
A prior price must itself have passed identical three-original validation.
No network and no actionable wagers.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from decimal import Decimal, InvalidOperation
import json
from diagnostics.p1_operator_original_handoff import assess_originals

class TemporalMarketRejected(ValueError):pass

def _utc(value):
    try:
        if type(value) is not str:raise ValueError()
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        if dt.utcoffset()!=timezone.utc.utcoffset(None):raise ValueError()
        return dt
    except (TypeError,ValueError,AttributeError):
        raise TemporalMarketRejected("UTC_required")

def _pairs(snapshot,name):
    out={}
    for row in snapshot[name]:
        key=(row["first"],row["second"])
        try:
            price=Decimal(str(row["decimal"]))
        except (InvalidOperation,TypeError,KeyError):
            raise TemporalMarketRejected("invalid_market_decimal")
        if key in out or not price.is_finite() or price<=1:
            raise TemporalMarketRejected("invalid_or_duplicate_market_price")
        out[key]=price
    return out

def _stage(bundle,snapshot,observed_utc,channel,max_age_seconds):
    receipt=assess_originals(bundle,snapshot,observed_utc=observed_utc,channel=channel)
    if receipt["prediction_ready"] is not False or receipt["official_origin_authenticated"] is not False:
        raise TemporalMarketRejected("unsafe_parser_authorization")
    if any(r["status"]!="ACTIVE" for r in snapshot["runners"]):
        raise TemporalMarketRejected("scratch_requires_new_snapshot_and_sales_proof")
    at=_utc(observed_utc)
    if at>=_utc(snapshot["prediction_cutoff_utc"]):
        raise TemporalMarketRejected("after_cutoff")
    for k,tag in (("odds","quinella"),("bracket_odds","bracket")):
        src=_utc(snapshot["sources"][k]["captured_utc"])
        state=snapshot["market_states"][tag]
        if state["sales"]!="OPEN":
            raise TemporalMarketRejected("sales_state_not_open")
        if _utc(state["observed_utc"])!=src:
            raise TemporalMarketRejected("market_state_source_clock_mismatch")
        age=(at-src).total_seconds()
        if age<0 or age>max_age_seconds:
            raise TemporalMarketRejected("market_freshness_rejected:"+k)
    return receipt

def audit_temporal_markets(*, current_bundle,current_snapshot,current_observed_utc,
                           channel, max_age_seconds=600,
                           previous_bundle=None,previous_snapshot=None,
                           previous_observed_utc=None,
                           max_declared_odds_drift=0.20,
                           takeout_policy_bytes=None):
    if (type(max_age_seconds) is not int or not 1<=max_age_seconds<=3600 or
        type(max_declared_odds_drift) not in (float,int) or
        not 0<=max_declared_odds_drift<1):
        raise TemporalMarketRejected("invalid_freshness_or_drift_limit")
    if not isinstance(current_bundle,bytes) or not isinstance(current_snapshot,dict):
        raise TemporalMarketRejected("current_source_missing")
    cur=_stage(current_bundle,current_snapshot,current_observed_utc,channel,max_age_seconds)
    previous=(previous_bundle,previous_snapshot,previous_observed_utc)
    if any(x is not None for x in previous) and not all(x is not None for x in previous):
        raise TemporalMarketRejected("incomplete_prior_original_set")
    prior=None
    if all(x is not None for x in previous):
        if not isinstance(previous_bundle,bytes) or not isinstance(previous_snapshot,dict):
            raise TemporalMarketRejected("prior_original_invalid")
        prior=_stage(previous_bundle,previous_snapshot,previous_observed_utc,channel,max_age_seconds)
        if (current_snapshot["meeting_date"],current_snapshot["race"])!=(
            previous_snapshot["meeting_date"],previous_snapshot["race"]):
            raise TemporalMarketRejected("different_races_cannot_measure_drift")
        if _utc(previous_observed_utc)>=_utc(current_observed_utc):
            raise TemporalMarketRejected("nonchronological_quotes")
        if [(r["number"],r["bracket"],r["status"]) for r in previous_snapshot["runners"]] != [
            (r["number"],r["bracket"],r["status"]) for r in current_snapshot["runners"]]:
            raise TemporalMarketRejected("roster_changed_before_market_comparison")
    drift={}
    for field in ("odds","bracket_odds"):
        newest=_pairs(current_snapshot,field)
        if prior is None:
            drift[field]=None
            continue
        older=_pairs(previous_snapshot,field)
        if set(newest)!=set(older):
            raise TemporalMarketRejected("market_pair_coverage_changed:"+field)
        worst=max((abs(newest[k]-older[k])/older[k] for k in newest),default=Decimal(0))
        if worst>Decimal(str(max_declared_odds_drift)):
            raise TemporalMarketRejected("market_drift_limit_exceeded:"+field)
        drift[field]=str(worst)
    policy_digest=None
    policy_value=None
    if takeout_policy_bytes is not None:
        if type(takeout_policy_bytes) is not bytes:
            raise TemporalMarketRejected("takeout_policy_raw_bytes_required")
        try:
            policy=json.loads(takeout_policy_bytes)
            if set(policy)!={"scope","takeout_fraction"} or policy["scope"]!="LAB_DECLARED_POLICY":
                raise ValueError()
            x=Decimal(policy["takeout_fraction"])
            if not x.is_finite() or not 0<=x<1:raise ValueError()
        except (ValueError,TypeError,InvalidOperation,KeyError):
            raise TemporalMarketRejected("takeout_policy_invalid")
        policy_value=str(x)
        policy_digest=sha256(takeout_policy_bytes).hexdigest()
    body={
        "schema":"kyoto_p4_temporal_market_research.v1",
        "scope":"SOURCE_BYTE_MATCHING_NOT_OFFICIAL_AUTHENTICATION",
        "race":current_snapshot["race"],
        "meeting_date":current_snapshot["meeting_date"],
        "current_three_original_sha256":cur["bundle_sha256"],
        "previous_three_original_sha256":prior["bundle_sha256"] if prior else None,
        "market_age_max_seconds":max_age_seconds,
        "max_declared_price_drift_fraction":max_declared_odds_drift,
        "observed_price_drifts":drift,
        "takeout_assumed_fraction":policy_value,
        "takeout_assumption_bytes_sha256":policy_digest,
        "takeout_verified_official":False,
        "scratch_and_sales_checked_against_asserted_snapshot":True,
        "official_scratch_and_sales_authenticated":False,
        "current_prices_original_content_verified":True,
        "official_origin_authenticated":False,
        "production_model_ready":False,
        "actual_bet_authorized":False,
        "network_requests":0
    }
    return {**body,"sha256":sha256(json.dumps(body,sort_keys=True,
             separators=(",",":"),allow_nan=False).encode()).hexdigest()}
