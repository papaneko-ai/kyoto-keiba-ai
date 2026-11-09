"""Read-only bridge from locked 2026-11-07 JRA racecards to market readiness.

No JRA GET; old odds-not-published observation is not a global or later
no-odds claim. Official October final odds may NEVER be priced as Nov-7 quotes.
"""
from datetime import datetime, timezone
import json
from pathlib import Path


class DayHandoffRejected(ValueError):
    pass


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _utc(timestamp):
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if dt.utcoffset() != timezone.utc.utcoffset(None):
        raise DayHandoffRejected("timestamp_not_utc")
    return dt


def _snapshot_path(root, number):
    if number == 7:
        return root / "JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json"
    if number in (1, 6, 12):
        return root / f"multirace_20261106/kyoto_{number:02d}_snapshot.json"
    return root / f"remaining8_20261106/kyoto_{number:02d}_snapshot.json"


def evaluate(root):
    root = Path(root)
    accepted = _load(root / "JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json")
    odds = _load(root / "JRA_ODDS_READINESS_ACCEPTANCE_20261106.json")
    menu = _load(root / "JRA_PC_SP_ODDS_MENU_20261106.json")
    final = _load(root / "JRA_HISTORICAL_MATRIX_EVIDENCE_20261106.json")
    rows = _load(root / "jra_p1_batch14_96_profiles_20261106/feature_rows_148.json")
    if (accepted.get("date") != "2026-11-07" or accepted.get("venue") != "KYOTO"
            or accepted.get("race_count") != 12 or accepted.get("runner_count") != 148
            or accepted.get("prediction_ready") is not False):
        raise DayHandoffRejected("acceptance_identity_mismatch")
    if (odds.get("status") != "OFFICIAL_UNPUBLISHED_CONFIRMED"
            or odds.get("pre_race_odds_available") is not False
            or odds.get("market_capture_success") is not False
            or odds.get("prediction_ready") is not False
            or odds.get("historical_final_as_prerace_forbidden") is not True):
        raise DayHandoffRejected("unpublished_odds_evidence_contradicted")
    sources = odds.get("source_channels")
    if not isinstance(sources, list) or {x["channel"] for x in sources} != {"PC", "SP"}:
        raise DayHandoffRejected("source_channels_missing")
    menus = {x["channel"]: x for x in menu["sources"]}
    for item in sources:
        m = menus.get(item["channel"])
        if (not m or item["menu_sha256"] != m["content_sha256"]
                or item["status"] != "NOT_PUBLISHED"
                or item["market_price_verified"] is not False
                or item["market_matrix_captured"] is not False
                or m.get("pre_race_odds_verified") is not False):
            raise DayHandoffRejected("odds_menu_source_mismatch")
        if _utc(item["captured_at_utc"]) >= _utc(odds["normal_sale_start_utc"]):
            raise DayHandoffRejected("unpublished_quote_after_sale_start_needs_review")
    if (final.get("source_classification") != "HISTORICAL_FINAL_NOT_PRERACE"
            or final.get("prediction_ready") is not False
            or final.get("markets", {}).get("quinella", {}).get("pre_race_quote_accepted") is not False
            or final.get("markets", {}).get("bracket_quinella", {}).get("pre_race_quote_accepted") is not False):
        raise DayHandoffRejected("historical_final_quotes_not_quarantined")
    by_race = {n: [] for n in range(1, 13)}
    for row in rows:
        race = row.get("race_number")
        if race not in by_race:
            raise DayHandoffRejected("registry_outside_12_races")
        by_race[race].append(row)
    reports = []
    sources_checked = []
    total_prior_dates = 0
    for race in range(1, 13):
        path = _snapshot_path(root, race)
        if not path.is_file():
            raise DayHandoffRejected(f"saved_snapshot_missing:{race}")
        doc = _load(path)
        if (doc.get("race_date") != "2026-11-07" or doc.get("venue") != "KYOTO"
                or doc.get("race_number") != race
                or doc.get("runner_count") != accepted["counts_by_race"][str(race)]):
            raise DayHandoffRejected(f"racecard_identity_disagreement:{race}")
        runners = doc["runners"]
        if len(runners) != doc["runner_count"] or len(by_race[race]) != len(runners):
            raise DayHandoffRejected(f"racecard_runner_count_disagreement:{race}")
        timestamp = doc.get("fetched_at_utc", doc.get("captured_at_utc"))
        if _utc(timestamp).date() >= datetime(2026, 11, 7, tzinfo=timezone.utc).date():
            raise DayHandoffRejected(f"racecard_not_previous_day:{race}")
        if len(doc["source_sha256"]) != 64:
            raise DayHandoffRejected(f"racecard_source_sha_missing:{race}")
        indexed = {x["horse_number"]: x for x in by_race[race]}
        if len(indexed) != len(runners):
            raise DayHandoffRejected(f"duplicate_registry_number:{race}")
        dates = 0
        for horse in runners:
            n = horse["horse_number"]
            stored = indexed.get(n)
            if (stored is None or horse.get("horse_name") != stored["horse_name"]
                    or horse.get("frame_number") != stored["frame_number"]
                    or horse.get("horse_profile_href") != stored["profile_href"]
                    or doc["source_sha256"] != stored["racecard_source_sha256"]):
                raise DayHandoffRejected(f"horse_identity_or_origin_disagreement:{race}:{n}")
            prior = horse.get("past_race_dates", horse.get("prior_race_dates"))
            if not isinstance(prior, list):
                raise DayHandoffRejected("prior_dates_missing")
            if any(x >= "2026-11-07" for x in prior):
                raise DayHandoffRejected("future_race_date")
            dates += len(prior)
        total_prior_dates += dates
        sources_checked.append(path.relative_to(root).as_posix())
        reports.append({"race": race, "runners": len(runners),
                        "source_sha256": doc["source_sha256"], "prior_dates": dates,
                        "odds_evidence": "PC_SP_UNPUBLISHED_OBSERVATION_FOR_11R_ONLY",
                        "quinella_prerace_prices_verified": False,
                        "bracket_prerace_prices_verified": False,
                        "prediction_ready": False})
    if total_prior_dates != accepted["prior_date_count"]:
        raise DayHandoffRejected("historical_prior_dates_count_disagreement")
    return {"schema": "kyoto_p1_historical_racecard_market_crosswalk.v1",
            "day": "2026-11-07", "venue": "KYOTO",
            "race_count": 12, "runner_count": 148,
            "historical_prior_dates": total_prior_dates,
            "sources_checked": sources_checked, "race_statuses": reports,
            "existing_official_market_parse_20261031": {
                "quinella_pairs": final["markets"]["quinella"]["pair_count"],
                "bracket_pairs": final["markets"]["bracket_quinella"]["pair_count"],
                "classification": "FINAL_HISTORICAL_NOT_PRERACE"},
            "actual_20261107_prerace_quinella_prices": 0,
            "actual_20261107_prerace_bracket_prices": 0,
            "live_quote_state": "NO_VALID_PRERACE_QUOTES_IN_CHECKED_ARCHIVE",
            "real_prediction_ready": False, "virtual_tickets": [], "jra_requests": 0,
            "source_type": "PREVIOUSLY_CAPTURED_OFFICIAL_STRUCTURED_EVIDENCE",
            "important_limit": "RACECARD STRUCTURED SNAPSHOTS RECONCILED; RAW HTML BYTES NOT REPARSED"}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir",type=Path,default=Path("docs/diagnostics"))
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    receipt=evaluate(args.source_dir)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("P1_HISTORICAL_CROSSWALK: 12 races, 148 horses, 396 prior dates; NO verified pre-race market quotes")


if __name__=="__main__":
    main()
