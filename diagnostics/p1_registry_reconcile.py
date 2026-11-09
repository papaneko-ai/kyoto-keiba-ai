"""Reconcile immutable 2026-11-07 Kyoto per-runner archived registry with summary.

Offline, historical only. Do not convert this into a live/prerace model input.
"""
import re
from hashlib import sha256


class RegistryConflict(ValueError):
    pass


def reconcile(status, rows):
    if not isinstance(status, dict) or not isinstance(rows, list):
        raise RegistryConflict("invalid_archive_inputs")
    if status.get("date") != "2026-11-07" or status.get("race_count") != 12:
        raise RegistryConflict("historical_identity_mismatch")
    if status.get("prediction_ready") is not False or status.get("training_ready") is not False:
        raise RegistryConflict("historical_readiness_flag_invalid")
    if len(rows) != status.get("runner_count") or len(rows) != 148:
        raise RegistryConflict("runner_count_conflict")
    by_race = {n: {"total": 0, "with_history": 0, "verified_empty": 0, "unqueried": 0,
                   "valid_prior_rows": 0} for n in range(1, 13)}
    identity = set()
    card_hashes = {}
    statuses = {"VERIFIED_SOURCE_ROWS": "with_history",
                "VERIFIED_EMPTY_HISTORY": "verified_empty",
                "NOT_QUERIED": "unqueried"}
    for row in rows:
        if not isinstance(row, dict):
            raise RegistryConflict("invalid_row")
        race, number = row.get("race_number"), row.get("horse_number")
        if type(race) is not int or race not in by_race or type(number) is not int or not 1 <= number <= 18:
            raise RegistryConflict("invalid_race_horse_number")
        key = race, number
        if key in identity:
            raise RegistryConflict("duplicate_horse_in_race")
        identity.add(key)
        if row.get("race") != f"2026-11-07_KYOTO_{race:02d}R":
            raise RegistryConflict("race_identity_conflict")
        if row.get("prediction_ready") is not False or row.get("training_ready") is not False:
            raise RegistryConflict("unverified_row_ready")
        coverage = row.get("source_coverage")
        if not isinstance(coverage, dict) or coverage.get("racecard") != "CONFIRMED":
            raise RegistryConflict("racecard_not_confirmed")
        state = coverage.get("horse_profile")
        if state not in statuses:
            raise RegistryConflict("unknown_profile_state")
        source = row.get("racecard_source_sha256")
        if not isinstance(source, str) or not re.fullmatch("[0-9a-f]{64}", source):
            raise RegistryConflict("bad_racecard_hash")
        if race in card_hashes and card_hashes[race] != source:
            raise RegistryConflict("racecard_source_disagreement")
        card_hashes[race] = source
        profile_sha = row.get("profile_source_sha256")
        features = row.get("performance_features")
        if state == "NOT_QUERIED":
            if profile_sha or features is not None:
                raise RegistryConflict("unqueried_has_profile_source")
        else:
            if not isinstance(profile_sha, str) or not re.fullmatch("[0-9a-f]{64}", profile_sha):
                raise RegistryConflict("verified_profile_source_missing")
            if state == "VERIFIED_EMPTY_HISTORY" and features is not None:
                raise RegistryConflict("empty_history_has_features")
            if state == "VERIFIED_SOURCE_ROWS" and not isinstance(features, dict):
                raise RegistryConflict("parsed_profile_missing_features")
        prior = 0
        if state == "VERIFIED_SOURCE_ROWS":
            prior = features.get("prior_valid_finishes_available")
            if type(prior) is not int or prior <= 0:
                raise RegistryConflict("invalid_prior_row_count")
        bucket = by_race[race]
        bucket["total"] += 1
        bucket[statuses[state]] += 1
        bucket["valid_prior_rows"] += prior

    counts = {"with_history": sum(x["with_history"] for x in by_race.values()),
              "verified_empty": sum(x["verified_empty"] for x in by_race.values()),
              "unqueried": sum(x["unqueried"] for x in by_race.values())}
    verified = counts["with_history"] + counts["verified_empty"]
    if verified != status.get("profile_details_source_verified") or counts["unqueried"] != status.get("detailed_profiles_unqueried"):
        raise RegistryConflict("profile_totals_conflict")
    if sum(x["valid_prior_rows"] for x in by_race.values()) != status.get("total_finished_prior_rows"):
        raise RegistryConflict("prior_rows_conflict")
    archived_completed = status.get("completed_race_runner_counts")
    if not isinstance(archived_completed, dict):
        raise RegistryConflict("historic_completed_races_missing")
    if any(by_race[int(n)]["total"] != count or
           by_race[int(n)]["unqueried"] != 0 for n, count in archived_completed.items()
           if n.isdigit() and int(n) in by_race):
        raise RegistryConflict("completed_race_claim_disagrees_with_rows")
    return {"schema": "kyoto_p1_historical_registry_reconciliation.v1",
            "date": "2026-11-07", "race_count": 12, "runner_count": len(rows),
            "counts": counts, "verified": verified,
            "valid_prior_rows": status["total_finished_prior_rows"],
            "by_race": {str(k): v for k, v in by_race.items()},
            "prediction_ready": False, "network_requests": 0,
            "warning": "HISTORICAL_ARCHIVE_ONLY_NOT_A_LIVE_PREDICTION"}
