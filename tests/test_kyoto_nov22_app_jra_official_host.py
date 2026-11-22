"""Independent official app.jra.jp (JRA public mobile) regression, no real HTTP."""
import unittest
from unittest.mock import Mock
from diagnostics.kyoto_weekend_sp_discovery import OFFICIAL_OBSERVED_NOV22_R1, official_sp_anchors, observed_kyoto_race_candidates
from diagnostics.jra_one_shot_market_capture import http_fetch, SourceChainError
from diagnostics.kyoto_sp_observed_source import capture_verified_sp_seed
from pathlib import Path
import tempfile

DAY="20261122"
URL=OFFICIAL_OBSERVED_NOV22_R1

class Response:
    status=200
    headers={"Content-Type":"text/html; charset=utf-8"}
    def __init__(self,url):self.url=url
    def read(self,n):return b"<html><body>KYOTO mobile official</body></html>"
    def geturl(self):return self.url
    def __enter__(self):return self
    def __exit__(self,*args):return False

class Client:
    def __init__(self):self.calls=[]
    def open(self,request,timeout=20):
        self.calls.append(request.full_url)
        return Response(request.full_url)

class AppJRAOfficialHost(unittest.TestCase):
    def test_real_jra_mobile_sp_r1_domain(self):
        self.assertIn("https://app.jra.jp/",URL)
        raw=('<html><a href="'+URL+'">京都 1R</a></html>').encode("utf-8")
        self.assertEqual(observed_kyoto_race_candidates(raw,"https://app.jra.jp/",DAY)["1"],[URL])
    def test_wrong_external_domain_is_rejected(self):
        raw=('<html><a href="'+URL.replace("app.jra.jp","evil.invalid")+'">京都 1R</a></html>').encode()
        self.assertEqual(official_sp_anchors(raw,"https://app.jra.jp/",DAY),[])
    def test_exact_mobile_url_is_fetched_and_original_archived(self):
        c=Client()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            result=capture_verified_sp_seed(root,race_day=DAY,race_number=1,
                                           source_url=URL,opener=c,pacer=Mock(),include_odds=False)
            self.assertTrue(result["racecard_fetched"])
            self.assertEqual(c.calls,[URL])
            self.assertTrue((root/"official_sp_racecard.html").is_file())
            self.assertFalse(result["market_verified"])
    def test_unknown_origin_does_not_send_http(self):
        c=Client()
        with self.assertRaisesRegex(SourceChainError,"invalid_target_origin"):
            http_fetch(c,"SP",URL.replace("app.jra.jp","bad.invalid"),pacer=Mock())
        self.assertEqual(c.calls,[])

if __name__=="__main__": unittest.main()
