"""Synthetic-only negative cases for official release-stage safety gate."""
import unittest
from diagnostics.kyoto_prerace_release_gate import evaluate, ReleaseGateRejected

BASE=dict(now_utc="2026-11-14T00:00:00Z",
    race_start_utc="2026-11-14T01:00:00Z",
    publication_not_before_utc="2026-11-13T01:00:00Z",
    publication_stage="LIVE_MARKET",observed_stage="LIVE_MARKET",
    authority_confirmed=True,permission_confirmed=True,
    raw_source_verified=True,horse_numbers_verified=True,odds_verified=True,
    source_captured_utc="2026-11-13T23:59:00Z")

class ReleaseTests(unittest.TestCase):
    def test_01_eligibility_is_not_authorization(self):
        self.assertEqual(evaluate(**BASE)["decision"],
                         "ELIGIBLE_FOR_FURTHER_INDEPENDENT_CHECKS_ONLY")
    def test_02_too_early(self):
        v={**BASE,"now_utc":"2026-11-12T00:00:00Z",
           "source_captured_utc":"2026-11-11T23:59:00Z"}
        self.assertEqual(evaluate(**v)["reason"],
                         "BEFORE_OFFICIALLY_VERIFIED_PUBLICATION_TIME")
    def test_03_unumbered_stage_stops(self):
        self.assertEqual(evaluate(**{**BASE,"observed_stage":"ENTRIES_WITHOUT_NUMBERS"})["decision"],"SAFE_STOP")
    def test_04_no_odds_stops(self):
        self.assertEqual(evaluate(**{**BASE,"odds_verified":False})["decision"],"SAFE_STOP")
    def test_05_missing_permission_stops(self):
        self.assertEqual(evaluate(**{**BASE,"permission_confirmed":False})["decision"],"SAFE_STOP")
    def test_06_unverified_source_stops(self):
        self.assertEqual(evaluate(**{**BASE,"raw_source_verified":False})["decision"],"SAFE_STOP")
    def test_07_started_race_stops(self):
        self.assertEqual(evaluate(**{**BASE,"now_utc":"2026-11-14T01:00:00Z"})["decision"],"SAFE_STOP")
    def test_08_invalid_timestamp_rejected(self):
        with self.assertRaises(ReleaseGateRejected):
            evaluate(**{**BASE,"publication_not_before_utc":"Friday"})
    def test_09_untrusted_flag_rejected(self):
        with self.assertRaises(ReleaseGateRejected):
            evaluate(**{**BASE,"permission_confirmed":"YES"})
    def test_10_future_source_stops(self):
        self.assertEqual(evaluate(**{**BASE,"source_captured_utc":"2026-11-14T00:01:00Z"})["decision"],"SAFE_STOP")

if __name__=="__main__":
    unittest.main()
