"""Offline handoff and classification for Nov14 -> Nov15 Kyoto second-day trial.

Does not GET JRA, invent a race-specific CNAME, authenticate the provenance
of user-supplied original files, or make a prediction. Live capture requires
a separate, explicit, one-shot GitHub workflow after this validation.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from diagnostics.jra_one_shot_market_capture import (
    ObservedRaceSpec, SourceChainError, verified_roster_from_snapshot,
)
from diagnostics.jra_official_link_repair import (
    OFFICIAL_ENTRY, observed_links, LinkRepairRejected,
)

DAY14 = "20261114"
DAY15 = "20261115"


class SecondDayRejected(ValueError):
    pass


def _same_day_not_guessed(original, *, parent, day, label, race=None):
    try:
        options = observed_links(original, parent)
    except (LinkRepairRejected, UnicodeError) as exc:
        raise SecondDayRejected("observed_original_invalid") from exc
    candidates = set()
    for url, text, token in options:
        if day not in token or (label and label not in text):
            continue
        if race is not None:
            if not re.search(rf"(?<!\d)0?{race}\s*(?:R|レース)(?!\d)", text):
                continue
            if f"{race:02d}{day}" not in token:
                continue
        candidates.add(url)
    if len(candidates) != 1:
        raise SecondDayRejected("unique_observed_official_link_missing_or_ambiguous")
    return next(iter(candidates))


def validate_day15_handoff(*, spec_data, roster, official_selection_original,
                           official_meeting_original, verified_start_utc):
    if type(spec_data) is not dict or type(roster) is not dict:
        raise SecondDayRejected("spec_and_roster_required")
    if (type(official_selection_original) is not bytes or
        type(official_meeting_original) is not bytes or
        not 0 < len(official_selection_original) <= 1_500_000 or
        not 0 < len(official_meeting_original) <= 1_500_000):
        raise SecondDayRejected("two_independent_original_bytes_required")
    if official_selection_original == official_meeting_original:
        raise SecondDayRejected("selection_and_meeting_originals_not_independent")
    try:
        spec=ObservedRaceSpec(**spec_data).validate(require_channels=("PC",))
        if spec.race_day != DAY15 or spec.pc_racecard_url == "":
            raise SecondDayRejected("nov15_identity_required")
        if spec.sp_racecard_url not in ("", None):
            # SP source requires a separately documented, independently
            # observed SP anchor. This PC-first gate does not grant it.
            raise SecondDayRejected("sp_source_unproven_in_pc_only_handoff")
        if not type(verified_start_utc) is str:
            raise SecondDayRejected("verified_start_required")
        start=datetime.fromisoformat(verified_start_utc.replace("Z","+00:00"))
        if start.utcoffset() != timezone.utc.utcoffset(None):
            raise SecondDayRejected("start_must_be_utc")
        verified_roster_from_snapshot(roster, spec, race_start_utc=verified_start_utc)
    except (SourceChainError, TypeError, ValueError, KeyError, AttributeError) as exc:
        if isinstance(exc, SecondDayRejected):
            raise
        raise SecondDayRejected("race_spec_roster_or_start_inconsistent") from exc
    meeting_url=_same_day_not_guessed(
        official_selection_original, parent=OFFICIAL_ENTRY,
        day=DAY15, label="京都"
    )
    race_url=_same_day_not_guessed(
        official_meeting_original, parent=meeting_url,
        day=DAY15, label="", race=spec.race_number
    )
    if race_url != spec.pc_racecard_url:
        raise SecondDayRejected("racecard_link_not_bound_to_original")
    result={
        "schema":"kyoto_nov15_pc_handoff.v1",
        "day14_prior_attempt_kept_separate": True,
        "race_day":DAY15,
        "race_id":spec.race_id,
        "race_number":spec.race_number,
        "channel":"PC",
        "source_observation_claim":"OFFLINE_OPERATOR_SUPPLIED_NOT_AUTHENTICATED",
        "observed_meeting_url":meeting_url,
        "observed_pc_racecard_url":race_url,
        "selection_original_sha256":hashlib.sha256(official_selection_original).hexdigest(),
        "meeting_original_sha256":hashlib.sha256(official_meeting_original).hexdigest(),
        "roster_original_claim_sha256":roster["source_sha256"],
        "runner_count":len(roster["runners"]),
        "verified_start_utc":verified_start_utc,
        "http_attempts":0,
        "real_prerace_roster_authenticated":False,
        "real_prerace_quinella_authenticated":False,
        "real_prerace_bracket_authenticated":False,
        "real_paper_trade_authorized":False,
    }
    return result


def classify_day14_capture(artifact_receipt):
    """Explain a *recorded* failure; do not infer publication state."""
    if type(artifact_receipt) is not dict:
        raise SecondDayRejected("prior_receipt_required")
    attempted=artifact_receipt.get("attempted_GET")
    if type(attempted) is not int or attempted not in (0,1):
        raise SecondDayRejected("attempt_count_invalid")
    status=artifact_receipt.get("status")
    if status=="FAILED_CLOSED" and attempted==1:
        return {"status":"DAY14_FAILED_PRESERVE_AND_DIAGNOSE",
                "cause":"UNKNOWN_WITHOUT_HTTP_ORIGINAL",
                "safe_action":"REVIEW_EXISTING_RECEIPT_AND_ERROR_CLASS_OFFLINE",
                "day15_separate_trial_permitted_in_principle":True,
                "nov14_retry_authorized":False,"network_requests":0}
    if status=="OFFICIAL_NOV14_KYOTO_MEETING_LINK_OBSERVED" and attempted==1:
        return {"status":"DAY14_MEETING_LINK_OBSERVED_ONLY",
                "cause":"RACE_MARKETS_NOT_YET_INDEPENDENTLY_PROVEN",
                "safe_action":"DO_NOT_PROMOTE_TO_LIVE_ODDS",
                "day15_separate_trial_permitted_in_principle":True,
                "nov14_retry_authorized":False,"network_requests":0}
    if attempted==0:
        return {"status":"DAY14_NO_GET_ATTEMPT_PROVEN_BY_SUPPLIED_RECEIPT",
                "cause":"NO_OBSERVED_OFFICIAL_RESPONSE",
                "safe_action":"KEEP_DAY15_INDEPENDENT",
                "day15_separate_trial_permitted_in_principle":True,
                "nov14_retry_authorized":False,"network_requests":0}
    raise SecondDayRejected("day14_receipt_state_conflict")
