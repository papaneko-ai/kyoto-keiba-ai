"""Regression tests use the actual 148-row archived JRA-derived feature registry."""
import copy
import json
import unittest
from pathlib import Path
from diagnostics.p1_registry_reconcile import reconcile, RegistryConflict

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs/diagnostics/jra_p1_batch14_96_profiles_20261106"

class RegistryReconcileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((DIR / "feature_rows_148.json").read_text(encoding="utf-8"))
        cls.status = json.loads((DIR / "status.json").read_text(encoding="utf-8"))

    def test_real_registry_totals(self):
        r = reconcile(self.status, self.rows)
        self.assertEqual(r["runner_count"], 148)
        self.assertEqual(r["counts"], {"with_history":77,"verified_empty":19,"unqueried":52})
        self.assertEqual(r["valid_prior_rows"],592)
        self.assertFalse(r["prediction_ready"])
        self.assertEqual(r["network_requests"],0)

    def test_real_race_5_and_6_are_verified_empty_not_missing(self):
        r = reconcile(self.status, self.rows)
        self.assertEqual(r["by_race"]["5"]["verified_empty"],8)
        self.assertEqual(r["by_race"]["6"]["verified_empty"],11)
        self.assertEqual(r["by_race"]["5"]["unqueried"],0)
        self.assertEqual(r["by_race"]["6"]["unqueried"],0)

    def test_additional_five_profiles_really_in_races_9_12(self):
        r = reconcile(self.status, self.rows)
        self.assertEqual([r["by_race"][str(n)]["with_history"] for n in (9,10,11,12)],[2,1,1,1])
        self.assertEqual(sum(r["by_race"][str(n)]["with_history"] for n in (9,10,11,12)),5)

    def test_idempotence(self):
        self.assertEqual(reconcile(self.status,self.rows),reconcile(self.status,self.rows))

    def test_duplicate_runner_refused(self):
        rows=copy.deepcopy(self.rows)
        rows[1]["horse_number"]=rows[0]["horse_number"]
        with self.assertRaisesRegex(RegistryConflict,"duplicate_horse_in_race"):
            reconcile(self.status,rows)

    def test_no_history_misclassified_as_unqueried_is_rejected(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["source_coverage"]["horse_profile"]=="VERIFIED_EMPTY_HISTORY")
        row["source_coverage"]["horse_profile"]="NOT_QUERIED"
        with self.assertRaises(RegistryConflict):
            reconcile(self.status,rows)

    def test_edited_profile_hash_rejected(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["source_coverage"]["horse_profile"]=="VERIFIED_SOURCE_ROWS")
        row["profile_source_sha256"]="a"
        with self.assertRaisesRegex(RegistryConflict,"verified_profile_source_missing"):
            reconcile(self.status,rows)

    def test_historical_prediction_is_never_enabled(self):
        status=copy.deepcopy(self.status)
        status["prediction_ready"]=True
        with self.assertRaisesRegex(RegistryConflict,"historical_readiness_flag_invalid"):
            reconcile(status,self.rows)

    def test_summary_count_tamper_rejected(self):
        status=copy.deepcopy(self.status)
        status["profile_details_source_verified"]=97
        with self.assertRaisesRegex(RegistryConflict,"profile_totals_conflict"):
            reconcile(status,self.rows)

if __name__ == "__main__":
    unittest.main()
