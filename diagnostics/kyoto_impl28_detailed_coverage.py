"""Strict fine-grained race/horse/market completeness; complements the 9-family gate.

Expected race: {"starters":[{"horse_number":1,"horse_id":"...", "fields":{...}}],
"markets":{"quinella":{"1-2":"12.3",...},"bracket_quinella":{"1-2":"8.1",...}},
"race_fields":{...}, "results":{...}}.
This module validates evidence; it does NOT download JRA data or invent missing values.
"""
from itertools import combinations
from diagnostics.kyoto_cancel_odds_classifier import classify_odds_cell

HORSE_FIELDS = ("horse_name", "frame_number", "jockey", "trainer", "sex",
                "age", "assigned_weight", "body_weight", "horse_profile",
                "pedigree", "past_races", "recent_form", "best_time",
                "running_style", "training", "distance_record", "course_record")
RACE_FIELDS = ("scheduled_start", "distance", "course", "weather",
               "going", "track_condition", "racecard_original_sha256",
               "observed_at_utc")
RESULT_FIELDS = ("official_order", "quinella_winning_pair",
                 "bracket_quinella_winning_pair", "quinella_payout",
                 "bracket_quinella_payout", "official_result_sha256")
def is_present(value):
    return value is not None and value != "" and value != [] and value != {}

def check_race(race):
    errors = []
    starters = race.get("starters", [])
    if not isinstance(starters, list) or not starters:
        return ["NO_STARTERS"]
    nums = []
    frames = []
    for horse in starters:
        num = horse.get("horse_number")
        if not isinstance(num, int) or isinstance(num, bool) or not 1 <= num <= 18 or num in nums:
            errors.append("INVALID_OR_DUPLICATE_HORSE_NUMBER")
        else:
            nums.append(num)
        frame = horse.get("fields", {}).get("frame_number")
        if isinstance(frame, int) and not isinstance(frame, bool) and 1 <= frame <= 8:
            frames.append(frame)
        for field in HORSE_FIELDS:
            if not is_present(horse.get("fields", {}).get(field)):
                errors.append(f"HORSE_{num}_MISSING_{field}")
        if not is_present(horse.get("horse_id")):
            errors.append(f"HORSE_{num}_MISSING_ID")
    for field in RACE_FIELDS:
        if not is_present(race.get("race_fields", {}).get(field)):
            errors.append("RACE_MISSING_" + field)
    # Complete markets include valid, cancelled and official unavailable cells,
    # with original strings retained. Do not mistake cancelled for a price.
    markets = race.get("markets", {})
    for market, members in (("quinella", nums), ("bracket_quinella", sorted(set(frames)))):
        observed = markets.get(market, {})
        if not isinstance(observed, dict):
            observed = {}
        expected = {f"{a}-{b}" for a,b in combinations(sorted(members), 2)}
        if market == "bracket_quinella":
            expected |= {f"{f}-{f}" for f in set(frames) if frames.count(f) >= 2}
        missing = expected - set(observed)
        if missing:
            errors.append(f"{market.upper()}_MISSING_PAIRS_{len(missing)}")
        for pair in expected & set(observed):
            cell = classify_odds_cell(observed[pair])
            if cell.state == "INVALID":
                errors.append(f"{market.upper()}_INVALID_{pair}")
            if cell.state == "UNAVAILABLE":
                errors.append(f"{market.upper()}_UNAVAILABLE_{pair}")
    for field in RESULT_FIELDS:
        if not is_present(race.get("results", {}).get(field)):
            errors.append("RESULT_MISSING_" + field)
    return sorted(set(errors))

def check_day(document):
    races = document.get("races", {})
    report = {str(n): check_race(races.get(str(n), {})) for n in range(1,13)}
    return {"complete": all(not issues for issues in report.values()),
            "race_errors": report,
            "failed_races": [n for n, issues in report.items() if issues]}
