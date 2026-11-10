"""Destructive research-only calibration acceptance; no real racing claims."""
import copy
import math
import unittest
from diagnostics.p3_research_calibration import (
    calibrate_holdout,CalibrationRejected,shrink_distribution,scores)


def fixtures():
    rows=[]
    for i in range(8):
        # Training winners are deliberately less likely under the base
        # distribution; holdout winners vary to expose non-guaranteed gains.
        p=(0.85,0.15) if i%2==0 else (0.75,0.25)
        rows.append({
            "race_id":"SYNTHETIC_R"+str(i+1),
            "prediction_cutoff_utc":f"2026-10-{i+1:02d}T05:00:00Z",
            "pre_result_frozen":True,
            "pairs":[{"pair":[1,2],"probability":p[0]},
                     {"pair":[1,3],"probability":p[1]}],
            "winning_pair":[1,3] if i<4 or i%3==0 else [1,2],
        })
    return rows


class CalibrationTests(unittest.TestCase):
    def test_research_holdout_proper_scores(self):
        result=calibrate_holdout(fixtures(),train_count=4)
        self.assertEqual(result["status"],"RESEARCH_HOLDOUT_SCORED_NOT_DEPLOYED")
        self.assertEqual(len(result["holdout_race_ids"]),4)
        self.assertGreater(result["selected_uniform_shrinkage"],0)
        self.assertFalse(result["prediction_ready"])
        self.assertFalse(result["real_money_authorized"])
        for k in ("brier","log_loss"):
            self.assertTrue(math.isfinite(result["calibrated_holdout"][k]))
        self.assertEqual(result,calibrate_holdout(fixtures(),train_count=4))

    def test_brier_and_log_loss_exact(self):
        b,l=scores({(1,2):0.8,(1,3):0.2},(1,2))
        self.assertAlmostEqual(b,0.08)
        self.assertAlmostEqual(l,-math.log(0.8))
        self.assertAlmostEqual(sum(shrink_distribution({(1,2):0.8,(1,3):0.2},0.5).values()),1)

    def test_holdout_labels_cannot_affect_fitted_alpha(self):
        rows=fixtures()
        base=calibrate_holdout(rows,train_count=4)
        for row in rows[4:]:
            row["winning_pair"]=[1,2] if row["winning_pair"]==[1,3] else [1,3]
        changed=calibrate_holdout(rows,train_count=4)
        self.assertEqual(base["selected_uniform_shrinkage"],changed["selected_uniform_shrinkage"])
        self.assertNotEqual(base["calibrated_holdout"],changed["calibrated_holdout"])

    def test_training_labels_change_alpha(self):
        rows=fixtures()
        base=calibrate_holdout(rows,train_count=4)
        for row in rows[:4]:
            row["winning_pair"]=[1,2]
        changed=calibrate_holdout(rows,train_count=4)
        self.assertNotEqual(base["selected_uniform_shrinkage"],changed["selected_uniform_shrinkage"])

    def test_refuse_unfrozen_predictions(self):
        rows=fixtures();rows[2]["pre_result_frozen"]=False
        with self.assertRaisesRegex(CalibrationRejected,"pre_result_prediction_receipt_required"):
            calibrate_holdout(rows,train_count=4)

    def test_refuse_duplicate_race(self):
        rows=fixtures();rows[1]["race_id"]=rows[0]["race_id"]
        with self.assertRaisesRegex(CalibrationRejected,"duplicate_or_invalid_race_id"):
            calibrate_holdout(rows,train_count=4)

    def test_refuse_shuffled_future_data(self):
        rows=fixtures();rows[0],rows[7]=rows[7],rows[0]
        with self.assertRaisesRegex(CalibrationRejected,"races_not_chronologically_sorted"):
            calibrate_holdout(rows,train_count=4)

    def test_refuse_invalid_normalization(self):
        rows=fixtures();rows[0]["pairs"][0]["probability"]=0.99
        with self.assertRaisesRegex(CalibrationRejected,"pair_probabilities_not_normalized"):
            calibrate_holdout(rows,train_count=4)

    def test_refuse_nan_and_zero_probability(self):
        for value in (float("nan"),0.0,1.0,-0.1):
            with self.subTest(value=value):
                rows=fixtures();rows[0]["pairs"][0]["probability"]=value
                with self.assertRaises(CalibrationRejected):
                    calibrate_holdout(rows,train_count=4)

    def test_refuse_missing_winner(self):
        rows=fixtures();rows[0]["winning_pair"]=[2,3]
        with self.assertRaisesRegex(CalibrationRejected,"winner_missing_from_predicted_pairs"):
            calibrate_holdout(rows,train_count=4)

    def test_refuse_insufficient_training_or_holdout(self):
        for n in (0,1,8,9,2.5):
            with self.subTest(n=n):
                with self.assertRaisesRegex(CalibrationRejected,"invalid_chronological_train_count"):
                    calibrate_holdout(fixtures(),train_count=n)

    def test_refuse_duplicate_cutoff(self):
        rows=fixtures();rows[2]["prediction_cutoff_utc"]=rows[1]["prediction_cutoff_utc"]
        with self.assertRaisesRegex(CalibrationRejected,"same_timestamp_races_require_explicit_order"):
            calibrate_holdout(rows,train_count=4)

if __name__=="__main__":
    unittest.main()
