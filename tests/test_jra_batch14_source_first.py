"""Prove new source-first capture retains bytes on parser error, no duplicates/retries."""
import hashlib,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from diagnostics.jra_p1_batch14_source_first import capture,preflight,CUTOFF

class Response:
    status=200
    headers={"Content-Type":"text/html; charset=Shift_JIS"}
    def __init__(self,raw):self.raw=raw
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.raw[:n]
    def geturl(self):return "https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103173/85"

class SourceFirst(unittest.TestCase):
    def test_preflight_two_unqueried_only(self):
        self.assertEqual([(i["race_number"],i["horse_number"]) for i in preflight()[0]],[(8,5),(8,6),(8,7),(8,8),(8,9),(9,2)])
    def test_expired_zero_get(self):
        def no_http(*a,**k):raise AssertionError("network_used")
        with tempfile.TemporaryDirectory() as t:
            r=capture(t,opener=no_http,clock=lambda:CUTOFF)
            self.assertEqual(r["official_network_requests"],0)
            self.assertEqual(r["reason"],"cutoff_expired_zero_requests")
    def test_original_retained_before_expected_parser_rejection(self):
        raw=b"<html><body>synthetic intentionally invalid horse identity</body></html>"
        calls=[]
        def opener(*a,**k):
            calls.append(1)
            return Response(raw)
        with tempfile.TemporaryDirectory() as t:
            r=capture(t,opener=opener,clock=lambda:datetime(2026,11,6,tzinfo=timezone.utc),sleep=lambda _:None)
            self.assertEqual(r["official_network_requests"],1)
            self.assertEqual(len(calls),1)
            self.assertEqual(r["failed_count"],1)
            self.assertEqual(r["verified_count"],0)
            self.assertEqual(r["items"][0]["state"],"BLOCKED")
            self.assertTrue(r["items"][0]["original_saved_before_parser"])
            self.assertEqual(r["items"][0]["source_sha256"],hashlib.sha256(raw).hexdigest())
            self.assertEqual((Path(t)/"race_08_horse_05.html").read_bytes(),raw)
if __name__=="__main__":unittest.main()
