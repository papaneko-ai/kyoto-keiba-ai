"""P3-02 paired model/market comparator on one byte-verified LAB market.

Provides the *missing same-snapshot model comparison interface* so that
future independently authenticated pre-race JRA records can be supplied
without retrofitting the algorithms. It does not train, calibrate, rank,
promote or authorize any live model. Both models are frozen before the same
observation and must share an independently supplied feature SHA.
"""
from __future__ import annotations

import hashlib
import json
import math
from diagnostics.p4_source_bound_model_ev_research import compare_source_market_to_frozen_model
from diagnostics.p4_temporal_market_controls import _utc

class PairedMarketRejected(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                 separators=(",",":"), allow_nan=False).encode("utf-8")).hexdigest()


def compare_two_frozen_models_same_market(*, bundle, snapshot, observed_utc,
                                         channel, baseline, candidate,
                                         common_feature_sha256,
                                         probability_error_bound=0.05,
                                         odds_drift_fraction=0.05):
    """Compare all pairs and both ticket markets on EXACTLY the same source.

    The feature hash is checked for equality, not claimed independently
    authenticated. No use of results, payout, labels or post-race data.
    """
    if type(baseline) is not dict or type(candidate) is not dict:
        raise PairedMarketRejected("two_frozen_models_required")
    if (type(common_feature_sha256) is not str
        or len(common_feature_sha256)!=64
        or any(c not in "0123456789abcdef" for c in common_feature_sha256)):
        raise PairedMarketRejected("external_feature_anchor_format_invalid")
    for model in (baseline,candidate):
        if model.get("source_feature_sha256")!=common_feature_sha256:
            raise PairedMarketRejected("features_differ_between_models")
        try:
            if not _utc(model["frozen_utc"])<=_utc(observed_utc):
                raise PairedMarketRejected("model_freeze_after_observation")
        except (KeyError,ValueError,TypeError) as exc:
            raise PairedMarketRejected("model_freeze_invalid") from exc
    if baseline.get("model_version")==candidate.get("model_version"):
        raise PairedMarketRejected("distinct_model_versions_required")
    if baseline==candidate:
        raise PairedMarketRejected("distinct_models_required")

    common={"bundle":bundle,"snapshot":snapshot,"observed_utc":observed_utc,
            "channel":channel,
            "probability_error_bound":probability_error_bound,
            "odds_drift_fraction":odds_drift_fraction}
    a=compare_source_market_to_frozen_model(**common,frozen_model=baseline)
    b=compare_source_market_to_frozen_model(**common,frozen_model=candidate)
    for field in ("source_bundle_sha256","source_snapshot_sha256",
                  "market_audit_sha256","race_date","race"):
        if a[field]!=b[field]:
            raise PairedMarketRejected("same_source_audit_invariant_broken:"+field)
    if a["model_feature_anchor_asserted_sha256"]!=b["model_feature_anchor_asserted_sha256"]:
        raise PairedMarketRejected("model_feature_audit_invariant_broken")

    markets={}
    for market in ("QUINELLA","BRACKET"):
        left=a["markets"][market]
        right=b["markets"][market]
        if left["full_pair_count"]!=right["full_pair_count"]:
            raise PairedMarketRejected("pair_coverage_mismatch")
        lp=left["research_model_expected_net"]
        rp=right["research_model_expected_net"]
        if len(lp)!=len(rp) or not lp:
            raise PairedMarketRejected("market_not_exhaustive")
        if {tuple(t["pair"]) for t in lp}!={tuple(t["pair"]) for t in rp}:
            raise PairedMarketRejected("pair_identity_mismatch")
        la={tuple(t["pair"]):t for t in lp}
        rb={tuple(t["pair"]):t for t in rp}
        entries=[]
        for pair in sorted(la):
            x,y=la[pair],rb[pair]
            for v in (x["expected_net_per_unit"],x["stressed_net_lower"],
                      y["expected_net_per_unit"],y["stressed_net_lower"]):
                if type(v) not in (float,int) or not math.isfinite(v):
                    raise PairedMarketRejected("model_market_ev_nonfinite")
            entries.append({
                "pair":list(pair),
                "baseline_ev_per_unit":x["expected_net_per_unit"],
                "candidate_ev_per_unit":y["expected_net_per_unit"],
                "candidate_minus_baseline_ev_per_unit":
                    y["expected_net_per_unit"]-x["expected_net_per_unit"],
                "baseline_stressed_ev_lower":x["stressed_net_lower"],
                "candidate_stressed_ev_lower":y["stressed_net_lower"],
                "candidate_minus_baseline_stressed":
                    y["stressed_net_lower"]-x["stressed_net_lower"]})
        markets[market]={
            "pair_count":left["full_pair_count"],
            "pairwise_same_market_comparison":entries,
            "baseline_risk_sha256":left["risk_report_sha256"],
            "candidate_risk_sha256":right["risk_report_sha256"]}

    body={
        "schema":"kyoto_p3_paired_original_market_lab_v1",
        "scope":"FROZEN_LAB_MODELS_ON_ONE_UNAUTHENTICATED_MARKET_ONLY",
        "race_date":a["race_date"],"race":a["race"],
        "observed_utc":observed_utc,"channel":channel,
        "source_bundle_sha256":a["source_bundle_sha256"],
        "source_snapshot_sha256":a["source_snapshot_sha256"],
        "market_audit_sha256":a["market_audit_sha256"],
        "asserted_common_feature_sha256":common_feature_sha256,
        "baseline_model_version":baseline["model_version"],
        "candidate_model_version":candidate["model_version"],
        "baseline_model_sha256":a["model_sha256"],
        "candidate_model_sha256":b["model_sha256"],
        "baseline_p4_receipt_sha256":a["comparison_sha256"],
        "candidate_p4_receipt_sha256":b["comparison_sha256"],
        "markets":markets,
        "paired_prices_and_cutoff_verified_from_supplied_bytes":True,
        "independently_authenticated_jra_origin":False,
        "independently_authenticated_feature_observation":False,
        "actual_released_model_compared":False,
        "unused_real_race_outcomes_evaluated":False,
        "real_model_promotion_authorized":False,
        "actual_purchase_authorized":False,
        "network_requests":0}
    return {**body,"comparison_sha256":_digest(body)}
