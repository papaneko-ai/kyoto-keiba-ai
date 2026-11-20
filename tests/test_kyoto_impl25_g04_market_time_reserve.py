"""G04 market-reserve gate: no late profile HTTP and truthful per-horse gaps."""
import unittest
from tests.test_kyoto_g04_all_horse_profiles import AllHorseProfile
from diagnostics.kyoto_g04_all_horse_profiles import capture,G04Rejected

class G04TimeBudget(unittest.TestCase):
    def setUp(self):
        AllHorseProfile.setUp(self)
        self.fetch=lambda url: AllHorseProfile.fetch(self,url)

    def run_g04(self,**extra):
        return capture(root=self.root,day="20261121",fetch=self.fetch,
            clock=lambda:"2026-11-21T00:01:00Z",allowed=True,**extra)

    def test_clock_exhaustion_skips_remaining_34_without_http(self):
        ticks=iter([1.0,2.0]+[101.0]*34)
        result=self.run_g04(deadline_monotonic=100.0,monotonic=lambda:next(ticks))
        self.assertEqual(result["expected_horses"],36)
        self.assertEqual(result["profile_verified_count"],2)
        self.assertEqual(result["time_budget_reserved_for_g06_count"],34)
        self.assertEqual(len(self.calls),2)
        self.assertEqual(len(result["missing_profiles"]),34)
        self.assertEqual(result["profiles"][2]["state"],"G04_TIME_BUDGET_RESERVED_FOR_G06")
        self.assertFalse(result["prediction_ready"])
        self.assertFalse(result["all_profiles_parsed"])
        self.assertEqual(len(list(self.root.glob("g04_profile_r*_h*.html"))),2)
        self.assertTrue((self.root/"g04_receipt.json").exists())

    def test_budget_exhausted_before_first_horse_zero_http(self):
        result=self.run_g04(deadline_monotonic=10.0,monotonic=lambda:10.0)
        self.assertEqual(result["profile_verified_count"],0)
        self.assertEqual(result["time_budget_reserved_for_g06_count"],36)
        self.assertEqual(self.calls,[])
        self.assertEqual(len(result["missing_profiles"]),36)

    def test_no_deadline_preserves_existing_success_path(self):
        result=self.run_g04()
        self.assertEqual(result["profile_verified_count"],36)
        self.assertEqual(result["time_budget_reserved_for_g06_count"],0)
        self.assertFalse(result["time_budget_deadline_enabled"])

    def test_invalid_budget_inputs_fail_before_any_fetch(self):
        with self.assertRaisesRegex(G04Rejected,"invalid_market_reserve_deadline"):
            self.run_g04(deadline_monotonic="bad")
        with self.assertRaisesRegex(G04Rejected,"invalid_market_reserve_clock"):
            self.run_g04(deadline_monotonic=10,monotonic="not-clock")
        self.assertEqual(self.calls,[])

    def test_received_original_before_expiry_stays_preserved(self):
        ticks=iter([99.0,101.0]+[101.0]*35)
        result=self.run_g04(deadline_monotonic=100.0,monotonic=lambda:next(ticks))
        self.assertEqual(result["profile_verified_count"],1)
        self.assertEqual(result["time_budget_reserved_for_g06_count"],35)
        self.assertTrue((self.root/"g04_profile_r01_h01.html").is_file())

if __name__=="__main__":
    unittest.main()
