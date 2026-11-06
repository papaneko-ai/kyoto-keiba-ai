"""Offline source-to-source identity audit. Never guesses the permanent JRA horse ID."""
from __future__ import annotations
from datetime import date, datetime
from hashlib import sha256
from urllib.parse import urlsplit

from diagnostics.parse_jra_result_roster import extract_result_roster
from diagnostics.jra_prior_form_offline import parse_horse_history

JRA_RESULT_URL = "https://www.jra.go.jp/JRADB/accessD.html"

class EvidenceError(ValueError):
    pass

def reconcile_one_horse(result_raw: bytes, profile_raw: bytes, *,
                        expected_race: int, expected_name: str,
                        target_date: date, profile_captured_utc: datetime,
                        prediction_cutoff_utc: datetime) -> dict:
    """Match saved result-link name to saved profile name; fail closed on uncertainty."""
    if not isinstance(expected_race, int) or expected_race < 1:
        raise EvidenceError("invalid_race")
    if not isinstance(profile_captured_utc, datetime) or profile_captured_utc.tzinfo is None:
        raise EvidenceError("capture_time_provenance_missing")
    roster = extract_result_roster(result_raw, JRA_RESULT_URL)
    if roster["parse_errors"]:
        raise EvidenceError("result_parse_errors")
    found = [r for r in roster["races"] if r["race_number"] == expected_race]
    if len(found) != 1:
        raise EvidenceError("race_not_unique")
    matches = [x for x in found[0]["rows"] if x["horse_name"] == expected_name]
    if len(matches) != 1:
        raise EvidenceError("horse_name_not_unique")
    target = matches[0]
    url = target["profile_url"]
    u = urlsplit(url)
    if u.path != "/JRADB/accessU.html" or not u.query.startswith("CNAME="):
        raise EvidenceError("profile_link_not_confirmed")
    prior = parse_horse_history(
        profile_raw, source_url=url, fetched_at_utc=profile_captured_utc,
        prediction_cutoff_utc=prediction_cutoff_utc, target_date=target_date,
        expected_horse_name=expected_name
    )
    if prior["profile_horse_name"] != expected_name:
        raise EvidenceError("name_mismatch")
    return {
        "schema_version": "jra_offline_identity_audit.v1",
        "result_source_sha256": roster["source_sha256"],
        "profile_source_sha256": sha256(profile_raw).hexdigest(),
        "target_date": target_date.isoformat(), "race_number": expected_race,
        "horse_name": expected_name, "horse_number": target["horse_number"],
        "frame_number": target["frame_number"], "profile_link_matched": True,
        "profile_name_matched": True,
        "profile_navigation_token": target["profile_action_token"],
        "official_permanent_horse_id": None,
        "official_permanent_horse_id_verified": False,
        "prior_row_count": prior["prior_row_count"],
        "excluded_row_count": len(prior["excluded_rows"]),
        "profile_captured_before_cutoff": prior["profile_captured_before_cutoff"],
        "pre_race_roster_verified": False, "prediction_ready": False,
        "reason": "post_race_data_no_pre_race_snapshot_or_stable_horse_id"
    }

def make_audit_report(result_raw: bytes, profile_raw: bytes, *,
                      target_date: date, profile_captured_utc: datetime,
                      prediction_cutoff_utc: datetime, name: str, race: int) -> dict:
    roster = extract_result_roster(result_raw, JRA_RESULT_URL)
    match = reconcile_one_horse(
        result_raw, profile_raw, expected_race=race, expected_name=name,
        target_date=target_date, profile_captured_utc=profile_captured_utc,
        prediction_cutoff_utc=prediction_cutoff_utc
    )
    return {
        "reconciliation": match, "result_race_count": roster["race_count"],
        "result_rows": roster["horse_rows"],
        "profile_links": roster["profile_links"],
        "per_race_counts": roster["per_race_counts"],
        "parse_errors": roster["parse_errors"],
        "all_runners_stable_ids_verified": False,
        "all_runners_histories_verified": False, "ready_for_model": False
    }
