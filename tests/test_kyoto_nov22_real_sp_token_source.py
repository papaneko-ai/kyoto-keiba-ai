"""Nov22 actual official SP token and independent observer fallback tests.

The example Kyoto 1R URL was independently observed on sp.jra.jp.
Other fixture links here are synthetic and NOT evidence of successful HTTP.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from diagnostics.kyoto_weekend_sp_discovery import (
    SEED, OFFICIAL_OBSERVED_NOV22_R1, discover,
    official_sp_anchors, observed_kyoto_race_candidates
)

DAY="20261122"
R1=OFFICIAL_OBSERVED_NOV22_R1
R12="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605061220261122%2FA1"

def html(content,codec="utf-8"):
    return ("<html><body>"+content+"</body></html>").encode(codec)

class FakeResponse:
    status=200
    headers={"Content-Type":"text/html; charset=utf-8"}
    def __init__(self,url,raw):self.url,self.raw=url,raw
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def geturl(self):return self.url
    def read(self,n):return self.raw[:n]

class MockOpener:
    def __init__(self,pages):self.pages,self.calls=pages,[]
    def open(self,req,timeout=12):
        url=req.full_url
        self.calls.append(url)
        if url not in self.pages:raise OSError("unexpected source")
        return FakeResponse(url,self.pages[url])

class ActualMobileTokens(unittest.TestCase):
    def test_actual_sunday_r1_anchor_utf8(self):
        raw=html('<a href="'+R1+'">京都 1R</a>')
        self.assertEqual(observed_kyoto_race_candidates(raw,SEED,DAY)["1"],[R1])
    def test_actual_sunday_r1_anchor_cp932(self):
        raw=html('<a href="'+R1+'">京都 1R</a>',"cp932")
        self.assertEqual(observed_kyoto_race_candidates(raw,SEED,DAY)["1"],[R1])
    def test_wrong_day_and_wrong_venue_cannot_be_promoted(self):
        links='<a href="'+R1.replace("20261122","20261121")+'">京都 1R</a>'
        links+='<a href="'+R1.replace("0108","0105")+'">京都 1R</a>'
        links+='<a href="'+R1+'">京都 2R</a>'
        self.assertEqual(observed_kyoto_race_candidates(html(links),SEED,DAY)["1"],[])
    def test_observed_sunday_seed_only_after_no_official_home_navigation(self):
        homepage=html("<p>navigation not rendered</p>")
        official=html('<h1>2026年11月22日 京都</h1><a href="'+R1+'">京都 1R</a><a href="'+R12+'">京都 12R</a>')
        opener=MockOpener({SEED:homepage,R1:official})
        with tempfile.TemporaryDirectory() as folder:
            result=discover(Path(folder)/"saved",day=DAY,opener=opener,pacer=Mock())
            self.assertEqual(opener.calls,[SEED,R1])
            self.assertEqual(result["racecard_url"],R12)
            self.assertEqual(result["network_requests_started"],2)
            self.assertEqual(result["per_race_observed_navigation_candidates"]["1"]["candidate_count"],1)
            self.assertEqual(result["per_race_observed_navigation_candidates"]["12"]["candidate_count"],1)
            self.assertFalse(result["full_twelve_race_sp_fallback_verified"])
            self.assertFalse(result["prediction_ready"])
    def test_fallback_unavailable_does_not_claim_racecard(self):
        opener=MockOpener({SEED:html("home")})
        with tempfile.TemporaryDirectory() as folder:
            result=discover(Path(folder)/"saved",day=DAY,opener=opener,pacer=Mock())
            self.assertEqual(result["racecard_url"],"")
            self.assertEqual(result["state"],"OFFICIAL_R12_LINK_NOT_OBSERVED")
            self.assertFalse(result["prediction_ready"])

if __name__=="__main__":unittest.main()
