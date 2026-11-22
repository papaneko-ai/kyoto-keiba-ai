"""No-JRA-HTTP reproduction of Sunday saved SP originals and homepage failure."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from diagnostics.kyoto_sp_all12_observed_capture import capture_all
from diagnostics.kyoto_weekend_sp_discovery import discover, SEED, OFFICIAL_OBSERVED_NOV22_R1 as R1

DAY="20261122"
STAMP="2026-11-22T00:03:00Z"

def page(day="2026年11月22日",venue="京都",race="1R",headers=True):
    headings="<table><tr><th>馬番</th><th>馬名</th></tr><tr><td>1</td><td>見本</td></tr></table>" if headers else ""
    return f"<html><body><h1>{day} 5回{venue}6日</h1><h2>{race} 出馬表</h2>{headings}</body></html>".encode("utf-8")

class Response:
    status=200
    headers={"Content-Type":"text/html; charset=utf-8"}
    def __init__(self,url,raw):self.url,self.raw=url,raw
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.raw[:n]
    def geturl(self):return self.url

class Client:
    def __init__(self,pages):self.pages,self.calls=pages,[]
    def open(self,request,timeout=12):
        url=request.full_url;self.calls.append(url)
        if url not in self.pages:raise OSError("blocked homepage")
        return Response(url,self.pages[url])

class SPDay22SavedR1(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"sp"
        self.root.mkdir()

    def write_original(self,raw=None,day=DAY,url=R1,stamp=STAMP,sha=None):
        raw=raw if raw is not None else page()
        filename="official_sp_discovery_2.html"
        (self.root/filename).write_bytes(raw)
        self.root.joinpath("sp_discovery_receipt.json").write_text(json.dumps({
            "day":day,"attempts":[{"url":url,"file":filename,"sha256":sha or hashlib.sha256(raw).hexdigest(),"captured_at_utc":stamp}]
        }))
        return raw

    def test_current_day_original_is_kept_and_no_extra_jra_get(self):
        raw=self.write_original()
        client=Mock()
        result=capture_all(self.root,day=DAY,opener=client,pacer=Mock())
        self.assertEqual(result["races"]["1"]["state"],"SP_SAVED_R1_ORIGINAL_REUSED_ROSTER_UNVERIFIED")
        self.assertTrue(result["races"]["1"]["racecard_fetched"])
        self.assertEqual(result["races"]["1"]["network_requests_started"],0)
        self.assertEqual((self.root/"r01_official_sp_racecard.html").read_bytes(),raw)
        self.assertFalse(result["prediction_ready"])
        self.assertFalse(result["both_markets_verified"])
        client.assert_not_called()

    def test_wrong_date_venue_race_headings_never_promote_saved_page(self):
        for bad in [page(day="2026年11月21日"),page(venue="東京"),page(race="2R"),page(headers=False)]:
            with self.subTest(bad=bad[:90]):
                with tempfile.TemporaryDirectory() as td:
                    self.root=Path(td)/"sp"
                    self.root.mkdir()
                    self.write_original(raw=bad)
                    result=capture_all(self.root,day=DAY,opener=Mock(),pacer=Mock())
                    self.assertFalse(result["races"]["1"].get("racecard_fetched",False))

    def test_sha_tamper_is_rejected_before_any_race_get(self):
        self.write_original(sha="f"*64)
        with self.assertRaisesRegex(ValueError,"discovery_original_sha_mismatch"):
            capture_all(self.root,day=DAY,opener=Mock(),pacer=Mock())

    def test_archive_utc_is_mandatory(self):
        self.write_original(stamp="2026-11-21T23:59:00Z")
        result=capture_all(self.root,day=DAY,opener=Mock(),pacer=Mock())
        self.assertFalse(result["races"]["1"].get("racecard_fetched",False))

    def test_homepage_connection_failure_keeps_observed_r1_opportunity(self):
        client=Client({R1:page()})
        r=discover(self.root/"discovery",day=DAY,opener=client,pacer=Mock())
        self.assertEqual(client.calls,[SEED,R1])
        self.assertEqual(r["network_requests_started"],2)
        self.assertEqual(len([x for x in r["attempts"] if "sha256" in x]),1)
        self.assertFalse(r["prediction_ready"])
        root=self.root/"discovery"
        result=capture_all(root,day=DAY,opener=Mock(),pacer=Mock())
        self.assertTrue(result["races"]["1"]["racecard_fetched"])
        self.assertFalse(result["all_twelve_races_verified"])

if __name__=="__main__":unittest.main()
