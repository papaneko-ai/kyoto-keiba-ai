"""P2 historical feature-materialization prototype from the locked P1 archive.

The output is intentionally UNSCORED, UNLABELED and NOT TRAINING READY.
It preserves verified empty history separately from profiles never queried.
No web access, post-race results, target labels, odds, fillna, model fitting.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from diagnostics.p1_registry_reconcile import reconcile

FIELDS = (
    "meeting_date", "race_number", "horse_number", "frame_number", "horse_name",
    "profile_state", "horse_profile_sha256", "racecard_sha256",
    "prior_valid_finishes", "recent_three_mean_distance_m",
    "recent_three_mean_finish_percentile", "recent_three_wins",
    "recent_three_turf_count", "recent_three_dirt_count",
    "recent_three_mixed_turf_dirt_count", "recent_three_jump_count", "recent_90day_date_count",
    "last_observed_prior_race_days_ago", "source_row_status",
)
FEATURES = (
    "prior_valid_finishes", "recent_three_mean_distance_m",
    "recent_three_mean_finish_percentile", "recent_three_wins",
    "recent_three_turf_count", "recent_three_dirt_count",
    "recent_three_mixed_turf_dirt_count", "recent_three_jump_count", "recent_90day_date_count",
    "last_observed_prior_race_days_ago",
)
PRESENT = "VERIFIED_SOURCE_ROWS"
EMPTY = "VERIFIED_EMPTY_HISTORY"
MISSING = "NOT_QUERIED"


def materialize(status, rows):
    check = reconcile(status, rows)
    output = []
    for row in sorted(rows, key=lambda x: (x["race_number"], x["horse_number"])):
        state = row["source_coverage"]["horse_profile"]
        perf = row.get("performance_features")
        dates = row.get("date_only_features")
        if not isinstance(dates, dict):
            raise ValueError("missing_date_only_record")
        if state == PRESENT:
            surfaces = perf.get("recent_three_surface_counts")
            if not isinstance(surfaces, dict):
                raise ValueError("invalid_surface_counts")
            if set(surfaces) - {"芝", "ダ", "ダート", "芝ダ", "障"}:
                raise ValueError("unknown_surface_category")
            surface_total = sum(v for v in surfaces.values() if type(v) is int and v >= 0)
            if any(type(v) is not int or v < 0 for v in surfaces.values()) or surface_total > 3:
                raise ValueError("invalid_surface_counts")
            dirt = surfaces.get("ダ", 0) + surfaces.get("ダート", 0)
            values = {
                "prior_valid_finishes": perf["prior_valid_finishes_available"],
                "recent_three_mean_distance_m": perf["recent_three_mean_distance_m"],
                "recent_three_mean_finish_percentile": perf["recent_three_mean_finish_percentile"],
                "recent_three_wins": perf["recent_three_wins"],
                "recent_three_turf_count": surfaces.get("芝", 0),
                "recent_three_dirt_count": dirt,
                "recent_three_mixed_turf_dirt_count": surfaces.get("芝ダ", 0),
                "recent_three_jump_count": surfaces.get("障", 0),
            }
            for field in ("prior_valid_finishes", "recent_three_wins", "recent_three_turf_count", "recent_three_dirt_count", "recent_three_mixed_turf_dirt_count", "recent_three_jump_count"):
                if type(values[field]) is not int or values[field] < 0:
                    raise ValueError("invalid_nonnegative_feature")
            from math import isfinite
            for field in ("recent_three_mean_distance_m", "recent_three_mean_finish_percentile"):
                v = values[field]
                if type(v) not in (float, int) or not isfinite(v):
                    raise ValueError("invalid_numeric_feature")
            if not 0 <= values["recent_three_mean_finish_percentile"] <= 1:
                raise ValueError("finish_percentile_out_of_range")
        else:
            values = {key: None for key in FEATURES}
        if state != MISSING:
            for key in ("recent_90day_date_count", "last_observed_prior_race_days_ago"):
                v = dates.get(key)
                if v is not None and (type(v) is not int or v < 0):
                    raise ValueError("invalid_date_only_feature")
                values[key] = v
        record = {
            "meeting_date": "2026-11-07", "race_number": row["race_number"],
            "horse_number": row["horse_number"], "frame_number": row["frame_number"],
            "horse_name": row["horse_name"], "profile_state": state,
            "horse_profile_sha256": row.get("profile_source_sha256"),
            "racecard_sha256": row["racecard_source_sha256"],
            "source_row_status": "HISTORICAL_NOT_MODEL_ELIGIBLE",
        }
        record.update(values)
        if state != PRESENT and any(record.get(key) is not None for key in FEATURES):
            # A verified-empty profile may have date-only evidence, but not
            # performance values. Never synthesize a zero-valued racing record.
            if any(record.get(key) is not None for key in FEATURES[:8]):
                raise ValueError("profile_without_history_has_performance")
        output.append(record)
    if len(output) != 148 or check["counts"] != {"with_history":77, "verified_empty":19, "unqueried":52}:
        raise ValueError("historic_feature_matrix_totals_conflict")
    return output


def render_csv(rows):
    writer_file = io.StringIO(newline="")
    writer = csv.DictWriter(writer_file, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: "" if row.get(k) is None else row[k] for k in FIELDS})
    return writer_file.getvalue().encode("utf-8")


def build_receipt(rows, csv_bytes):
    if len(rows) != 148:
        raise ValueError("invalid_matrix_size")
    availability = {key: sum(row.get(key) is not None for row in rows) for key in FEATURES}
    return {
        "schema": "kyoto_p2_historic_feature_matrix_receipt.v1",
        "archive_meeting_date": "2026-11-07",
        "runners": 148,
        "profile_with_history": 77,
        "verified_empty_history": 19,
        "unqueried": 52,
        "feature_nonnull_count": availability,
        "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "csv_rows": len(rows),
        "source_type": "PREEXISTING_P1_ARCHIVED_FEATURE_REGISTRY",
        "outcome_labels_included": False,
        "post_race_results_included": False,
        "prediction_ready": False,
        "training_ready": False,
        "network_requests": 0,
        "restrictions": ["HISTORICAL_DIAGNOSTIC_ONLY", "NOT_VALIDATED_RAW_HTML_REPARSE",
                         "NOT_AN_APPROVED_LIVE_FEED", "NO_MODEL_FITTING"],
    }



def audit_latest_family_coverage(status, rows, matrix):
    """Join the canonical eight P1 source families to the later 96-profile P2 matrix.

    This is the existing archival registry and existing feature schema only:
    no new parsers, no network and no future-source inference.
    """
    from diagnostics.jra_feature_coverage_148 import FIELDS as FAMILY_FIELDS
    from diagnostics.p1_registry_reconcile import reconcile
    verified = reconcile(status, rows)
    if len(matrix) != verified["runner_count"]:
        raise ValueError("archived_feature_matrix_size_disagreement")
    indexed={(r["race_number"],r["horse_number"]):r for r in rows}
    seen=set()
    group_counts={k:{"available":0,"missing":0,"not_applicable":0}
                  for k in FAMILY_FIELDS}
    state_counts={"VERIFIED_SOURCE_ROWS":0,"VERIFIED_EMPTY_HISTORY":0,"NOT_QUERIED":0}
    for item in matrix:
        key=(item["race_number"],item["horse_number"])
        if key in seen or key not in indexed:
            raise ValueError("feature_identity_duplicate_or_unmatched")
        seen.add(key)
        original=indexed[key]
        if (item["horse_name"]!=original["horse_name"]
            or item["frame_number"]!=original["frame_number"]
            or item["racecard_sha256"]!=original["racecard_source_sha256"]):
            raise ValueError("feature_original_identity_mismatch")
        groups=original["source_coverage"]
        if set(groups)!=set(FAMILY_FIELDS):
            raise ValueError("feature_family_schema_drift")
        status_value=groups["horse_profile"]
        if item["profile_state"]!=status_value or status_value not in state_counts:
            raise ValueError("source_profile_state_conflict")
        state_counts[status_value]+=1
        for family,raw_state in groups.items():
            if family=="racecard":
                if raw_state!="CONFIRMED":
                    raise ValueError("racecard_no_source")
                state="available"
            elif family=="horse_profile":
                state="available" if raw_state in ("VERIFIED_SOURCE_ROWS","VERIFIED_EMPTY_HISTORY") else "missing"
            elif family=="payout_result":
                if raw_state!="NOT_APPLICABLE_BEFORE_RACE":
                    raise ValueError("postrace_outcome_cannot_be_prerace_feature")
                state="not_applicable"
            else:
                if raw_state!="MISSING":
                    # A claim of new source completeness belongs in new
                    # independently verified evidence, never the 2026-11-07 archive.
                    raise ValueError("unverified_additional_feature_source")
                state="missing"
            group_counts[family][state]+=1
    if seen!=set(indexed) or state_counts!={"VERIFIED_SOURCE_ROWS":77,
                                           "VERIFIED_EMPTY_HISTORY":19,"NOT_QUERIED":52}:
        raise ValueError("archived_96_profile_baseline_conflict")
    return {
        "schema":"kyoto_p1_p2_archived_eight_family_handoff.v1",
        "source_day":"2026-11-07",
        "race_count":12,
        "runner_count":len(matrix),
        "source_verified_profile_count":96,
        "with_prior_performance":77,
        "verified_empty_history":19,
        "unqueried_profiles":52,
        "historical_prior_race_rows":verified["valid_prior_rows"],
        "family_coverage":{k:{"fields":list(FAMILY_FIELDS[k]),**v}
                           for k,v in group_counts.items()},
        "predictions_authorized":False,
        "training_authorized":False,
        "official_live_current_day_verified":False,
        "cross_time_source_merging_authorized":False,
        "network_requests":0,
        "warnings":[
            "Old 12-profile coverage report is a historical milestone, not the later 96-profile state",
            "VERIFIED_EMPTY_HISTORY is not equivalent to NOT_QUERIED",
            "Verified historical profiles are not 2026-11-14 current-day evidence",
            "Jockey/trainer aggregates, workout, weather/track and live odds are missing",
            "Payouts and current-race results are never prerace features",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.registry.read_text(encoding="utf-8"))
    status = json.loads(args.status.read_text(encoding="utf-8"))
    feature_rows = materialize(status, data)
    csv_bytes = render_csv(feature_rows)
    receipt = build_receipt(feature_rows, csv_bytes)
    family_coverage = audit_latest_family_coverage(status, data, feature_rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "historical_feature_matrix.csv").write_bytes(csv_bytes)
    (args.output_dir / "eight_family_coverage.json").write_text(
        json.dumps(family_coverage,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    (args.output_dir / "receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"HISTORICAL_FEATURES_ONLY {len(feature_rows)} runners; no predictions, no JRA GET")


if __name__ == "__main__":
    main()
