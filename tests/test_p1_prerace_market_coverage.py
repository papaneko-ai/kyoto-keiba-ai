import copy
import unittest
from diagnostics.p1_prerace_market_coverage import inspect_quinella_coverage, MarketCoverageRejected

class MarketCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.s={"schema":"kyoto_p1_prerace_snapshot.v1","race":1,
                "runners":[{"number":1},{"number":2},{"number":3},{"number":4}],
                "odds":[{"first":a,"second":b,"decimal":3.3} for a in range(1,5) for b in range(a+1,5)]}
    def test_all_six_pairs_mathematically_complete(self):
        x=inspect_quinella_coverage(self.s)
        self.assertEqual(x["expected_quinella_pairs"],6)
        self.assertEqual(x["market_completeness"],"STRUCTURAL_COMPLETE")
        self.assertEqual(x["missing_quinella_pairs"],[])
        self.assertFalse(x["prediction_ready"])
    def test_one_missing_pair_detected(self):
        self.s["odds"].pop()
        x=inspect_quinella_coverage(self.s)
        self.assertEqual(x["market_completeness"],"INCOMPLETE")
        self.assertEqual(x["missing_quinella_pairs"],[[3,4]])
    def test_reversed_pair_duplicate_rejected(self):
        self.s["odds"].append({"first":2,"second":1,"decimal":2.1})
        with self.assertRaisesRegex(MarketCoverageRejected,"duplicate_pair"):
            inspect_quinella_coverage(self.s)
    def test_nonrunner_pair_rejected(self):
        self.s["odds"][0]["second"]=8
        with self.assertRaisesRegex(MarketCoverageRejected,"unknown_pair"):
            inspect_quinella_coverage(self.s)
    def test_nonfinite_price_rejected(self):
        self.s["odds"][0]["decimal"]=float("nan")
        with self.assertRaisesRegex(MarketCoverageRejected,"price_invalid"):
            inspect_quinella_coverage(self.s)
    def test_missing_market_is_incomplete_not_ready(self):
        self.s["odds"]=[]
        x=inspect_quinella_coverage(self.s)
        self.assertEqual(x["expected_quinella_pairs"],6)
        self.assertEqual(len(x["missing_quinella_pairs"]),6)
        self.assertFalse(x["prediction_ready"])
    def test_duplicate_horse_number_rejected(self):
        self.s["runners"][1]["number"]=1
        with self.assertRaisesRegex(MarketCoverageRejected,"runner_identity_invalid"):
            inspect_quinella_coverage(self.s)
    def test_eighteen_horses_153_pairs(self):
        self.s["runners"]=[{"number":i} for i in range(1,19)]
        self.s["odds"]=[{"first":a,"second":b,"decimal":2.0} for a in range(1,19) for b in range(a+1,19)]
        x=inspect_quinella_coverage(self.s)
        self.assertEqual(x["expected_quinella_pairs"],153)
        self.assertEqual(x["market_completeness"],"STRUCTURAL_COMPLETE")
        self.assertFalse(x["official_source_verified"])
        self.assertFalse(x["prediction_ready"])

if __name__=="__main__":
    unittest.main()
