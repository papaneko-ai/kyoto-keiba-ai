"""Tests against the actual stored 148-entry Kyoto P1 archive, not random racing data."""
import copy
import csv
import io
from decimal import Decimal
import hashlib
import json
import unittest
from pathlib import Path
from diagnostics.p2_historical_feature_matrix import (
    FIELDS, build_receipt, materialize, render_csv,
)

DATA = Path(__file__).resolve().parents[1] / "docs/diagnostics/jra_p1_batch14_96_profiles_20261106"


class HistoricalMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((DATA/"feature_rows_148.json").read_text(encoding="utf-8"))
        cls.status = json.loads((DATA/"status.json").read_text(encoding="utf-8"))

    def test_actual_148_features_and_states(self):
        records = materialize(self.status, self.rows)
        self.assertEqual(len(records),148)
        self.assertEqual(sum(r["profile_state"]=="VERIFIED_SOURCE_ROWS" for r in records),77)
        self.assertEqual(sum(r["profile_state"]=="VERIFIED_EMPTY_HISTORY" for r in records),19)
        self.assertEqual(sum(r["profile_state"]=="NOT_QUERIED" for r in records),52)
        self.assertEqual(sum(r["prior_valid_finishes"] or 0 for r in records),592)

    def test_absent_profile_stays_null(self):
        records = materialize(self.status, self.rows)
        self.assertTrue(all(r["prior_valid_finishes"] is None for r in records
                            if r["profile_state"] != "VERIFIED_SOURCE_ROWS"))
        self.assertTrue(all(r["recent_three_mean_finish_percentile"] is None for r in records
                            if r["profile_state"] != "VERIFIED_SOURCE_ROWS"))

    def test_real_archive_is_deterministic(self):
        left = render_csv(materialize(self.status,self.rows))
        right = render_csv(materialize(self.status,list(reversed(self.rows))))
        self.assertEqual(left,right)

    def test_no_labels_odds_or_future_result_in_columns(self):
        lower = " ".join(FIELDS).lower()
        for forbidden in ("payout","result","target","label","live_odds","winning"):
            self.assertNotIn(forbidden,lower)

    def test_receipt_rejects_predicted_ready_state(self):
        records = materialize(self.status,self.rows)
        receipt = build_receipt(records,render_csv(records))
        self.assertIs(receipt["prediction_ready"],False)
        self.assertIs(receipt["training_ready"],False)
        self.assertIs(receipt["post_race_results_included"],False)
        self.assertIs(receipt["outcome_labels_included"],False)

    def test_csv_receipt_hash(self):
        records=materialize(self.status,self.rows)
        data=render_csv(records)
        receipt=build_receipt(records,data)
        self.assertEqual(receipt["csv_sha256"],hashlib.sha256(data).hexdigest())

    def test_corrupt_horse_number_rejected_by_registry(self):
        rows=copy.deepcopy(self.rows)
        rows[1]["horse_number"]=rows[0]["horse_number"]
        with self.assertRaises(ValueError):
            materialize(self.status,rows)

    def test_corrupt_source_status_rejected(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["source_coverage"]["horse_profile"]=="VERIFIED_EMPTY_HISTORY")
        row["source_coverage"]["horse_profile"]="NOT_QUERIED"
        with self.assertRaises(ValueError):
            materialize(self.status,rows)

    def test_bad_finish_percentile_rejected(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["source_coverage"]["horse_profile"]=="VERIFIED_SOURCE_ROWS")
        row["performance_features"]["recent_three_mean_finish_percentile"]=1.2
        with self.assertRaisesRegex(ValueError,"finish_percentile_out_of_range"):
            materialize(self.status,rows)

    def test_real_mixed_turf_dirt_source_is_not_lost(self):
        records = materialize(self.status,self.rows)
        self.assertEqual(sum(r["recent_three_mixed_turf_dirt_count"] or 0 for r in records),8)

    def test_unknown_surface_category_rejected(self):
        rows = copy.deepcopy(self.rows)
        row=next(x for x in rows if x["source_coverage"]["horse_profile"]=="VERIFIED_SOURCE_ROWS")
        row["performance_features"]["recent_three_surface_counts"]["unknown"]=1
        with self.assertRaisesRegex(ValueError,"unknown_surface_category"):
            materialize(self.status,rows)

    def test_bad_surface_counts_rejected(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["source_coverage"]["horse_profile"]=="VERIFIED_SOURCE_ROWS")
        row["performance_features"]["recent_three_surface_counts"]["芝"]=100
        with self.assertRaisesRegex(ValueError,"invalid_surface_counts"):
            materialize(self.status,rows)

    def test_published_csv_semantically_matches_source_derived_matrix(self):
        derived = render_csv(materialize(self.status,self.rows)).decode("utf-8")
        published = (DATA.parent / "p2_historical_feature_matrix_20261107_148.csv").read_text(encoding="utf-8")
        expected = list(csv.DictReader(io.StringIO(derived)))
        actual = list(csv.DictReader(io.StringIO(published)))
        self.assertEqual(len(expected), 148)
        self.assertEqual(len(actual), 148)
        numeric = {
            "prior_valid_finishes", "recent_three_mean_distance_m",
            "recent_three_mean_finish_percentile", "recent_three_wins",
            "recent_three_turf_count", "recent_three_dirt_count",
            "recent_three_mixed_turf_dirt_count", "recent_three_jump_count", "recent_90day_date_count",
            "last_observed_prior_race_days_ago"
        }
        for a, b in zip(expected, actual):
            self.assertEqual(set(a), set(b))
            for key in a:
                if key in numeric and a[key] and b[key]:
                    self.assertEqual(Decimal(a[key]), Decimal(b[key]), (key, a["horse_name"]))
                else:
                    self.assertEqual(a[key], b[key], (key, a["horse_name"]))

    def test_no_nan_feature_permitted(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["source_coverage"]["horse_profile"]=="VERIFIED_SOURCE_ROWS")
        row["performance_features"]["recent_three_mean_distance_m"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid_numeric_feature"):
            materialize(self.status,rows)

if __name__=="__main__":
    unittest.main()
