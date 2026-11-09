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
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "historical_feature_matrix.csv").write_bytes(csv_bytes)
    (args.output_dir / "receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"HISTORICAL_FEATURES_ONLY {len(feature_rows)} runners; no predictions, no JRA GET")


if __name__ == "__main__":
    main()
