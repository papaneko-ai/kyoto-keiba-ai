"""P4-02 research-only strict three-original prices x frozen model probabilities.

Connect P1 byte-verified odds and P4 chronological freshness with existing
P3 distributions and P4 risk comparator. A synthetic model is NEVER promoted
to official/live capability even when the original HTML bytes match claims.
No trading, no network, no production model, no external data modification.
"""
from __future__ import annotations
import hashlib
import json
import math
from diagnostics.p1_operator_original_handoff import assess_originals
from diagnostics.p4_temporal_market_controls import audit_temporal_markets, _utc
from diagnostics.p3_p6_research_no_bet import quinella_from_strength, bracket_from_quinella
from diagnostics.p4_research_market_risk import audit_market_risk

class OriginalEvRejected(ValueError):pass

def _hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()

def compare_source_market_to_frozen_model(*,bundle,snapshot,observed_utc,channel,
     frozen_model,probability_error_bound=0.05,odds_drift_fraction=0.05,
     max_age_seconds=3600):
    if type(frozen_model) is not dict or set(frozen_model)!={
          "provenance","race_date","race_number","venue","frozen_utc",
          "cutoff_utc","strengths","source_feature_sha256","model_version"}:
        raise OriginalEvRejected("frozen_model_schema_invalid")
    if (frozen_model["provenance"]!="LAB_SYNTHETIC_ONLY" or
        frozen_model["venue"]!="京都" or
        frozen_model["race_date"]!=snapshot.get("meeting_date") or
        frozen_model["race_number"]!=snapshot.get("race")):
        raise OriginalEvRejected("model_race_or_provenance_mismatch")
    if (not isinstance(frozen_model["model_version"],str)
        or not frozen_model["model_version"].startswith("LAB-")
        or type(frozen_model["source_feature_sha256"]) is not str
        or len(frozen_model["source_feature_sha256"])!=64):
        raise OriginalEvRejected("external_frozen_feature_anchor_required")
    if not (_utc(frozen_model["frozen_utc"])<=_utc(observed_utc)
            <_utc(frozen_model["cutoff_utc"])==_utc(snapshot["prediction_cutoff_utc"])):
        raise OriginalEvRejected("model_freeze_or_cutoff_invalid")
    weights=frozen_model["strengths"]
    if (type(weights) is not dict or
        any(type(k) is not str or not k.isdecimal() or k!=str(int(k)) for k in weights)):
        raise OriginalEvRejected("model_strengths_invalid")
    roster={r["number"]:r["bracket"] for r in snapshot["runners"]}
    if (set(map(int,weights))!=set(roster) or
        any(type(w) not in (int,float) or not math.isfinite(w) or w<=0
            for w in weights.values())):
        raise OriginalEvRejected("model_roster_or_strength_invalid")
    # Content/temporal validation BEFORE evaluating ANY purported market EV.
    market=audit_temporal_markets(
        current_bundle=bundle,current_snapshot=snapshot,
        current_observed_utc=observed_utc,channel=channel,
        max_age_seconds=max_age_seconds)
    content=assess_originals(bundle,snapshot,observed_utc=observed_utc,channel=channel)
    if not (content["source_content_verified"] and market["current_prices_original_content_verified"]):
        raise OriginalEvRejected("original_content_not_verified")
    q=quinella_from_strength({int(k):v for k,v in weights.items()})
    b=bracket_from_quinella(q,roster)
    def prices(key,probs):
        result={}
        for row in snapshot[key]:
            pair=(row["first"],row["second"])
            if pair in result:raise OriginalEvRejected("duplicate_prices")
            result[pair]=row["decimal"]
        if set(result)!=set(probs):
            raise OriginalEvRejected("incomplete_market_pair_coverage")
        return result
    qr=audit_market_risk(q,prices("odds",q),
        probability_error_bound=probability_error_bound,
        odds_drift_fraction=odds_drift_fraction)
    br=audit_market_risk(b,prices("bracket_odds",b),
        probability_error_bound=probability_error_bound,
        odds_drift_fraction=odds_drift_fraction)
    rows={}
    for label,report in (("QUINELLA",qr),("BRACKET",br)):
        rows[label]={
          "full_pair_count":len(report["pairs"]),
          "research_model_expected_net":[{"pair":p["pair"],
               "expected_net_per_unit":p["model_expected_net"],
               "stressed_net_lower":p["stressed_expected_net_lower"]}
               for p in report["pairs"]],
          "risk_report_sha256":report["sha256"]}
    result={
      "schema":"kyoto_p4_source_bound_model_market_comparison.v1",
      "scope":"STRICT_ORIGINAL_CONTENT_PLUS_SYNTHETIC_MODEL_ONLY",
      "race_date":snapshot["meeting_date"],"race":snapshot["race"],
      "source_bundle_sha256":content["bundle_sha256"],
      "source_snapshot_sha256":content["snapshot_sha256"],
      "market_audit_sha256":market["sha256"],
      "model_sha256":_hash(frozen_model),
      "model_feature_anchor_asserted_sha256":frozen_model["source_feature_sha256"],
      "full_model_probabilities_sum_to_one":True,
      "markets":rows,
      "source_official_origin_authenticated":False,
      "official_sales_withdrawals_authenticated":False,
      "model_externally_calibrated":False,
      "real_race_prediction_ready":False,
      "real_paper_trades_written":0,
      "actual_purchase_authorized":False,
      "network_requests":0}
    return {**result,"comparison_sha256":_hash(result)}
