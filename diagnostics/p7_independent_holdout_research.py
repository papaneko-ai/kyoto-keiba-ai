"""Fail-closed, independent research-only P7-02 holdout adjudicator.

The caller supplies sealed study metadata and an untouched chronological test
window. This is an algorithmic research acceptance test, NOT proof of independent
JRA provenance or authorization to promote a live model.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone

class AuditRejected(ValueError):
    pass

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def utc(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() != timezone.utc.utcoffset(None):
            raise ValueError()
        return result
    except (TypeError, ValueError, AttributeError):
        raise AuditRejected("UTC_timestamp_required")

def adjudicate(plan, observations, *, independently_verified=False):
    """Judge an unseen chronological holdout against a pre-committed plan.

    plan requires an externally archived preregistration hash to be supplied
    by the caller. A self-contained hash cannot prove real-world timestamping.
    """
    required = {"champion", "candidate", "researcher_id", "auditor_id",
                "training_end_utc", "plan_locked_utc", "min_races",
                "min_mean_improvement", "min_win_fraction",
                "comparison_count", "holdout_race_ids"}
    if type(plan) is not dict or set(plan) != required:
        raise AuditRejected("plan_schema_invalid")
    if any(type(plan[k]) is not str or not plan[k] for k in
           ("champion", "candidate", "researcher_id", "auditor_id")):
        raise AuditRejected("missing_model_or_role")
    if plan["champion"] == plan["candidate"] or plan["researcher_id"] == plan["auditor_id"]:
        raise AuditRejected("model_or_auditor_not_independent")
    train_end, locked = utc(plan["training_end_utc"]), utc(plan["plan_locked_utc"])
    if train_end >= locked:
        raise AuditRejected("plan_not_locked_after_training")
    n = plan["min_races"]
    m = plan["comparison_count"]
    floor = plan["min_mean_improvement"]
    wins = plan["min_win_fraction"]
    if type(n) is not int or n < 4 or type(m) is not int or m < 1:
        raise AuditRejected("invalid_sample_or_multiplicity")
    if type(floor) not in (float, int) or not math.isfinite(floor) or floor <= 0:
        raise AuditRejected("invalid_improvement_threshold")
    if type(wins) not in (float, int) or not 0.5 < wins <= 1:
        raise AuditRejected("invalid_win_threshold")
    ids = plan["holdout_race_ids"]
    if type(ids) is not list or len(ids) < n or any(type(i) is not str or not i for i in ids) or len(set(ids)) != len(ids):
        raise AuditRejected("invalid_predeclared_holdout")
    if type(observations) is not list or len(observations) != len(ids):
        raise AuditRejected("missing_or_added_holdout_races")
    previous = locked
    improvements = []
    observed_ids = []
    for item in observations:
        if type(item) is not dict or set(item) != {"race_id", "frozen_utc", "result_utc",
            "champion_probability", "candidate_probability", "outcome"}:
            raise AuditRejected("observation_schema_invalid")
        rid = item["race_id"]
        if type(rid) is not str:
            raise AuditRejected("race_id_invalid")
        observed_ids.append(rid)
        frozen, result = utc(item["frozen_utc"]), utc(item["result_utc"])
        if frozen <= previous or result <= frozen:
            raise AuditRejected("future_leakage_or_nonchronological_window")
        previous = frozen
        if type(item["outcome"]) is not int or item["outcome"] not in (0, 1):
            raise AuditRejected("invalid_outcome")
        losses = []
        for key in ("champion_probability", "candidate_probability"):
            p = item[key]
            if type(p) not in (int, float) or not math.isfinite(p) or not 0 < p < 1:
                raise AuditRejected("invalid_probability")
            losses.append(-math.log(p if item["outcome"] else 1-p))
        improvements.append(losses[0] - losses[1])
    if observed_ids != ids:
        raise AuditRejected("holdout_selection_or_order_changed")
    mean = math.fsum(improvements) / len(improvements)
    win_rate = sum(d > 0 for d in improvements) / len(improvements)
    # Conservative multiple-comparison hurdle; study plan must fix m before use.
    threshold = floor * m
    eligible = mean >= threshold and win_rate >= wins
    payload = {"schema": "kyoto_p7_independent_holdout_research.v1",
               "scope": "RESEARCH_ONLY_UNVERIFIED_EXTERNAL_PROVENANCE",
               "plan_sha256": digest(plan), "observations_sha256": digest(observations),
               "holdout_races": len(ids), "mean_log_loss_gain": mean,
               "paired_win_fraction": win_rate, "multiplicity_adjusted_hurdle": threshold,
               "research_verdict": "RESEARCH_HOLDOUT_PASS" if eligible else "RESEARCH_HOLDOUT_REJECT",
               "independently_verified_external_evidence": independently_verified is True,
               "operationally_certified": False, "auto_deploy": False,
               "prediction_ready": False, "actual_bet_authorized": False}
    return {**payload, "receipt_sha256": digest(payload)}
