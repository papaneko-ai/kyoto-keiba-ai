"""C09 SP observed-only all-race candidate coverage; no URL synthesis."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock
from diagnostics.kyoto_weekend_sp_discovery import (
    SEED,discover,observed_kyoto_race_candidates)
from tests.test_kyoto_weekend_sp_discovery import Stub,html

DAY="20261121"
def official(r,day=DAY,suffix="AA"):
    # Fixture string is an observed HTML href, never used as a generated URL
    # by production collectors.
    return "https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race%02d%s%%2F%s"%(r,day,suffix)

def anchor(r,label=None,suffix="AA"):
    return '<a href="%s">%s</a>'%(official(r,suffix=suffix),label or "京都 %dR"%r)

class C09ObservedCoverage(unittest.TestCase):
    def test_actual_saved_navigation_enumerates_multiple_horses_races(self):
        raw=html(anchor(1)+anchor(6)+anchor(12))
        result=observed_kyoto_race_candidates(raw,SEED,DAY)
        self.assertEqual([i for i,v in result.items() if v],["1","6","12"])
        self.assertEqual(result["1"],[official(1)])
        self.assertTrue(all(result[str(i)]==[] for i in range(2,6)))

    def test_wrong_day_host_label_never_promoted(self):
        raw=html(anchor(2,suffix="AA").replace("sp.jra.jp","evil.invalid")
            +anchor(3).replace(DAY,"20261122")
            +anchor(4,label="東京 4R")
            +anchor(5,label="京都 6R"))
        result=observed_kyoto_race_candidates(raw,SEED,DAY)
        self.assertTrue(all(not v for v in result.values()))

    def test_two_distinct_race_candidates_remain_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=html(anchor(5,suffix="AA")+anchor(5,suffix="BB")+anchor(12))
            op=Stub({SEED:first})
            receipt=discover(Path(tmp)/"sp",day=DAY,opener=op,pacer=Mock())
        self.assertEqual(receipt["per_race_observed_navigation_candidates"]["5"]["candidate_count"],2)
        self.assertEqual(receipt["per_race_observed_navigation_candidates"]["5"]["state"],
                         "AMBIGUOUS_OFFICIAL_SP_NAVIGATION_HINT_NOT_FETCHED")
        self.assertEqual(op.calls,[SEED])
        self.assertFalse(receipt["full_twelve_race_sp_fallback_verified"])

    def test_seed_r12_stays_only_current_automated_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=html(anchor(1)+anchor(2)+anchor(12))
            op=Stub({SEED:first})
            receipt=discover(Path(tmp)/"sp",day=DAY,opener=op,pacer=Mock())
        self.assertEqual(receipt["racecard_url"],official(12))
        self.assertEqual(receipt["per_race_observed_navigation_candidates"]["1"]["candidate_count"],1)
        self.assertTrue(receipt["observed_link_is_not_authenticated_racecard"])
        self.assertFalse(receipt["full_twelve_race_sp_fallback_verified"])
        self.assertEqual(op.calls,[SEED])

    def test_no_official_links_is_not_false_twelve_race_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt=discover(Path(tmp)/"sp",day=DAY,
                opener=Stub({SEED:html("<p>No official links</p>")}),pacer=Mock())
        self.assertEqual(len(receipt["per_race_observed_navigation_candidates"]),12)
        self.assertEqual(sum(v["candidate_count"] for v in receipt["per_race_observed_navigation_candidates"].values()),0)
        self.assertFalse(receipt["full_twelve_race_sp_fallback_verified"])

if __name__=="__main__":
    unittest.main()
