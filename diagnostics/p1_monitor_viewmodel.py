"""Pure validation of P1 historical status for read-only UI. No network or database."""
EXPECTED_SCHEMA = "jra_kyoto_p1_96_profiles_eight_complete_races.v1"
REQUIRED_UNVERIFIED = {"race_conditions", "jockey_trainer", "track_weather", "market_odds",
                       "training_workouts", "official_live_scratches"}


class StatusInvalid(ValueError):
    pass


def summarize(status):
    if not isinstance(status, dict) or status.get("schema_version") != EXPECTED_SCHEMA:
        raise StatusInvalid("schema_mismatch")
    def count(key):
        value = status.get(key)
        if type(value) is not int or value < 0:
            raise StatusInvalid("invalid_" + key)
        return value
    total = count("runner_count")
    done = count("profile_details_source_verified")
    missing = count("detailed_profiles_unqueried")
    races = count("race_count")
    prior = count("total_finished_prior_rows")
    if total != 148 or races != 12 or done + missing != total:
        raise StatusInvalid("historical_totals_conflict")
    if status.get("date") != "2026-11-07":
        raise StatusInvalid("historical_date_conflict")
    if status.get("prediction_ready") is not False or status.get("training_ready") is not False:
        raise StatusInvalid("historical_prediction_flag_conflict")
    if status.get("feature_complete") is not False:
        raise StatusInvalid("feature_completeness_conflict")
    groups = status.get("unverified_groups")
    if not isinstance(groups, list) or not REQUIRED_UNVERIFIED.issubset(set(groups)):
        raise StatusInvalid("unverified_groups_missing")
    completed = status.get("completed_race_runner_counts")
    if not isinstance(completed, dict) or set(completed) != {str(i) for i in range(1, 9)}:
        raise StatusInvalid("completed_races_conflict")
    if status.get("completed_races") != list(range(1, 9)):
        raise StatusInvalid("completed_race_list_conflict")
    for race, qty in completed.items():
        if type(qty) is not int or not 1 <= qty <= 18:
            raise StatusInvalid("invalid_completed_race_count")
    completed_sum = sum(completed.values())
    if completed_sum > done:
        raise StatusInvalid("completed_race_sum_exceeds_verified")
    if status.get("permanent_html_archive_completed") is not False:
        raise StatusInvalid("archive_status_changed")
    return {
        "runner_count": total, "verified": done, "unqueried": missing,
        "prior_rows": prior, "race_count": races, "completed_race_counts": completed,
        "completed_race_sum": completed_sum,
        "verified_not_allocated_to_completed_races": done - completed_sum,
        "unverified_groups": tuple(groups),
        "prediction_ready": False,
    }
