"""Fail-closed completeness gate for Kyoto 12R live data receipts.

A green GitHub Actions run or saved original alone never proves structured
pre-start availability. Run after each acquisition, and on next-day replay.
Input JSON: {"day":"YYYYMMDD","races":{"1":{"racecard":{...},...}}}
Each family receipt must carry state, original_sha256, observed_at_utc.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path

FAMILIES = ("racecard", "roster", "horse_profile", "past_performances",
            "track_condition", "quinella_odds", "bracket_quinella_odds",
            "official_result", "official_payout")
PRESTART = {"racecard", "roster", "horse_profile", "past_performances",
            "track_condition", "quinella_odds", "bracket_quinella_odds"}
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
SUCCESS = "STRUCTURED_VERIFIED"
def parse_utc(value):
    if not isinstance(value, str):
        return None
    try:
        d = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.astimezone(dt.timezone.utc) if d.tzinfo else None
    except (ValueError, OverflowError):
        return None

def assess(doc):
    result = {"day": doc.get("day"), "races": {}, "missing": [],
              "complete": False, "required": 12 * len(FAMILIES), "verified": 0}
    races = doc.get("races", {})
    if not isinstance(races, dict):
        races = {}
    for n in range(1, 13):
        key = str(n)
        race = races.get(key, {})
        if not isinstance(race, dict):
            race = {}
        start = parse_utc(race.get("scheduled_start_utc"))
        states = {}
        for family in FAMILIES:
            receipt = race.get(family, {})
            if not isinstance(receipt, dict):
                receipt = {}
            state = receipt.get("state", "MISSING")
            observed = parse_utc(receipt.get("observed_at_utc"))
            sha = receipt.get("original_sha256", "")
            reasons = []
            if state != SUCCESS:
                reasons.append("NOT_STRUCTURED_VERIFIED")
            if not isinstance(sha, str) or not HEX64.fullmatch(sha):
                reasons.append("NO_VERIFIED_ORIGINAL_SHA256")
            if observed is None:
                reasons.append("NO_VALID_OBSERVED_UTC")
            if family in PRESTART:
                if start is None:
                    reasons.append("NO_VALID_SCHEDULED_START")
                if observed and start and observed >= start:
                    reasons.append("NOT_PRESTART")
            if reasons:
                result["missing"].append({"race": n, "family": family,
                                          "state": state, "reasons": reasons})
            else:
                result["verified"] += 1
            states[family] = "PASS" if not reasons else "FAIL"
        result["races"][key] = states
    result["complete"] = (result["verified"] == result["required"])
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipts", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = assess(json.loads(args.receipts.read_text(encoding="utf-8")))
    data = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(data + "\n", encoding="utf-8")
    print(data)
    raise SystemExit(0 if report["complete"] else 2)

if __name__ == "__main__":
    main()
