"""Offline-only SP collector provenance and byte preservation tests."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote
from diagnostics.kyoto_sp_observed_source import capture_observed_sp, SPSourceError

DAY="20261115"
SOURCE="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dli00%2FTEST"
RACE="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605041220261115%2F8E"
NAV=f'<html><a href="{RACE}">京都 12R</a></html>'.encode("cp932")

class FakeResponse:
    status=200
    headers={"Content-Type":"text/html; charset=Shift_JIS"}
    def __init__(self,url):
        self.url=url
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def geturl(self):return self.url
    def read(self,n):return b"<html>sp original fixture</html>"

class FakeOpener:
    def __init__(self):self.urls=[]
    def open(self,request,timeout):
        self.urls.append(request.full_url)
        return FakeResponse(request.full_url)

class SPSourceTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.dir=Path(t.name)/"sp"
        self.opener=FakeOpener()
    def collect(self,**kwargs):
        options=dict(navigation_original=NAV,navigation_url=SOURCE,
                     race_day=DAY,race_number=12,
                     navigation_captured_utc="2026-11-15T02:00:00+00:00",
                     opener=self.opener)
        options.update(kwargs)
        return capture_observed_sp(self.dir,**options)
    def test_sp_original_and_provenance(self):
        r=self.collect()
        self.assertTrue(r["racecard_fetched"])
        self.assertEqual(r["network_requests_started"],1)
        self.assertEqual(self.opener.urls,[RACE])
        self.assertEqual((self.dir/"official_sp_navigation.html").read_bytes(),NAV)
        self.assertEqual((self.dir/"official_sp_racecard.html").read_bytes(),
                         b"<html>sp original fixture</html>")
        self.assertFalse(r["market_verified"])
        self.assertFalse(r["pc_sp_parity_verified"])
    def test_no_synthetic_sp_race_link(self):
        with self.assertRaisesRegex(SPSourceError,"not_independently_observed"):
            self.collect(race_number=11)
        self.assertEqual(self.opener.urls,[])
    def test_pc_host_navigation_rejected(self):
        with self.assertRaisesRegex(SPSourceError,"provenance_invalid"):
            self.collect(navigation_url=SOURCE.replace("sp.jra.jp","jra.jp"))
        self.assertEqual(self.opener.urls,[])
    def test_invalid_day_rejected(self):
        with self.assertRaisesRegex(SPSourceError,"provenance_invalid"):
            self.collect(race_day="20261114")
        self.assertEqual(self.opener.urls,[])
    def test_existing_destination_rejected(self):
        self.dir.mkdir()
        with self.assertRaisesRegex(SPSourceError,"existing_or_invalid"):
            self.collect()
        self.assertEqual(self.opener.urls,[])
    def test_verified_sp_seed_stored_exactly(self):
        from diagnostics.kyoto_sp_observed_source import capture_verified_sp_seed
        rec=capture_verified_sp_seed(
            self.dir,race_day=DAY,race_number=12,source_url=RACE,
            opener=self.opener)
        self.assertTrue(rec["racecard_fetched"])
        self.assertEqual(rec["racecard_sha256"],
                         __import__("hashlib").sha256(
                             b"<html>sp original fixture</html>").hexdigest())
        self.assertEqual(self.opener.urls,[RACE])
        self.assertEqual((self.dir/"official_sp_racecard.html").read_bytes(),
                         b"<html>sp original fixture</html>")
    def test_verified_sp_seed_rejects_pc_domain(self):
        from diagnostics.kyoto_sp_observed_source import capture_verified_sp_seed
        with self.assertRaisesRegex(SPSourceError,"sp_source_url_unverified"):
            capture_verified_sp_seed(
                self.dir,race_day=DAY,race_number=12,
                source_url=RACE.replace("sp.jra.jp","jra.jp"),
                opener=self.opener)
        self.assertEqual(self.opener.urls,[])
    def test_seed_requires_matching_date_and_race(self):
        from diagnostics.kyoto_sp_observed_source import capture_verified_sp_seed
        for day,num in (("20261114",12),(DAY,11)):
            with self.assertRaisesRegex(SPSourceError,"sp_source_url_unverified"):
                capture_verified_sp_seed(
                    self.dir,race_day=day,race_number=num,
                    source_url=RACE,opener=self.opener)
        self.assertEqual(self.opener.urls,[])
    def test_offline_comparison_no_originals(self):
        from diagnostics.kyoto_sp_observed_source import compare_saved_pc_sp
        self.dir.mkdir()
        result=compare_saved_pc_sp(self.dir,race_day=DAY)
        self.assertEqual(result["state"],"NEED_BOTH_ORIGINALS")
        self.assertFalse(result["channel_preference_certified"])
if __name__=="__main__":unittest.main()
