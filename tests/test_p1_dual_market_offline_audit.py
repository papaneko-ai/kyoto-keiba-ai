import copy
import unittest
from diagnostics.p1_dual_market_offline_audit import inspect_dual_market, DualMarketRejected

NOW = "2026-11-13T05:00:00Z"


class DualMarketAuditTests(unittest.TestCase):
    def setUp(self):
        self.s = {
            "schema": "kyoto_p1_prerace_snapshot.v1",
            "captured_utc": "2026-11-13T04:05:00Z",
            "prediction_cutoff_utc": "2026-11-14T04:50:00Z",
            "runners": [
                {"number": 1, "bracket": 1, "status": "ACTIVE"},
                {"number": 2, "bracket": 2, "status": "ACTIVE"},
                {"number": 3, "bracket": 2, "status": "ACTIVE"},
            ],
            "odds": [
                {"first": 1, "second": 2, "decimal": 3.1},
                {"first": 1, "second": 3, "decimal": 4.1},
                {"first": 2, "second": 3, "decimal": 5.1},
            ],
            "bracket_odds": [
                {"first": 1, "second": 2, "decimal": 2.5},
                {"first": 2, "second": 2, "decimal": 6.0},
            ],
            "market_states": {
                "quinella": {"sales": "OPEN", "observed_utc": "2026-11-13T04:01:00Z"},
                "bracket": {"sales": "OPEN", "observed_utc": "2026-11-13T04:02:00Z"}
            }
        }

    def audit(self):
        return inspect_dual_market(self.s, observed_utc=NOW)

    def test_full_same_bracket_still_not_prediction(self):
        r = self.audit()
        self.assertEqual((r["expected_quinella_pairs"], r["expected_bracket_pairs"]), (3, 2))
        self.assertTrue(r["structural_complete"])
        self.assertFalse(r["prediction_ready"])
        self.assertEqual(r["network_requests"], 0)

    def test_missing_bracket_pair_blocks(self):
        self.s["bracket_odds"].pop()
        r = self.audit()
        self.assertEqual(r["missing_bracket_pairs"], [[2, 2]])
        self.assertEqual(r["status"], "BLOCKED")

    def test_duplicated_reversed_bracket_pair_rejected(self):
        self.s["bracket_odds"].append({"first": 2, "second": 1, "decimal": 5})
        with self.assertRaisesRegex(DualMarketRejected, "bracket_duplicate_pair"):
            self.audit()

    def test_withdrawal_requires_rebuilt_market(self):
        self.s["runners"][2]["status"] = "WITHDRAWN"
        with self.assertRaisesRegex(DualMarketRejected, "quinella_unavailable_pair"):
            self.audit()

    def test_valid_withdrawn_changes_pairs(self):
        self.s["runners"][2]["status"] = "WITHDRAWN"
        self.s["odds"] = self.s["odds"][:1]
        self.s["bracket_odds"] = self.s["bracket_odds"][:1]
        r = self.audit()
        self.assertEqual(r["inactive_horses"], 1)
        self.assertEqual(r["expected_bracket_pairs"], 1)
        self.assertFalse(r["withdrawal_authenticity_verified"])

    def test_sales_suspended_blocks(self):
        self.s["market_states"]["bracket"]["sales"] = "SUSPENDED"
        self.assertEqual(self.audit()["status"], "BLOCKED")

    def test_market_state_time_after_capture_rejected(self):
        self.s["market_states"]["bracket"]["observed_utc"] = "2026-11-13T04:06:00Z"
        with self.assertRaisesRegex(DualMarketRejected, "market_state_time_invalid"):
            self.audit()

    def test_cutoff_already_passed_rejected(self):
        with self.assertRaisesRegex(DualMarketRejected, "observation_outside_prerace_window"):
            inspect_dual_market(self.s, observed_utc="2026-11-14T04:51:00Z")

    def test_missing_sales_state_rejected(self):
        del self.s["market_states"]
        with self.assertRaisesRegex(DualMarketRejected, "market_states_missing"):
            self.audit()

    def test_unknown_bracket_rejected(self):
        self.s["runners"][0]["bracket"] = 9
        with self.assertRaisesRegex(DualMarketRejected, "horse_identity_bracket_or_status_invalid"):
            self.audit()

    def test_price_nan_rejected(self):
        self.s["bracket_odds"][0]["decimal"] = float("nan")
        with self.assertRaisesRegex(DualMarketRejected, "bracket_price_invalid"):
            self.audit()

    def test_18_horses_all_eight_brackets_36_pairs(self):
        self.s["runners"] = [
            {"number": n, "bracket": min(8, (n+1)//2), "status": "ACTIVE"}
            for n in range(1, 19)]
        self.s["odds"] = [{"first": a, "second": b, "decimal": 4.0}
                           for a in range(1, 19) for b in range(a+1, 19)]
        pairs = {(min(a["bracket"], b["bracket"]), max(a["bracket"], b["bracket"]))
                 for a in self.s["runners"] for b in self.s["runners"]
                 if a["number"] < b["number"]}
        self.s["bracket_odds"] = [{"first": a, "second": b, "decimal": 4.0}
                                  for a, b in sorted(pairs)]
        r = self.audit()
        self.assertEqual(r["expected_quinella_pairs"], 153)
        self.assertEqual(r["expected_bracket_pairs"], 36)
        self.assertFalse(r["prediction_ready"])

    def test_deterministic(self):
        self.assertEqual(self.audit(), self.audit())


if __name__ == "__main__":
    unittest.main()
