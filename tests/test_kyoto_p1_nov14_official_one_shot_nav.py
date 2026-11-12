"""One-off upcoming JRA meeting discovery safeguards, no actual network in tests."""
import tempfile,unittest
from datetime import datetime,timezone
AFTER_PUBLICATION=lambda:datetime(2026,11,12,8,0,tzinfo=timezone.utc)
BEFORE_PUBLICATION=lambda:datetime(2026,11,12,2,34,tzinfo=timezone.utc)
from diagnostics.kyoto_p1_nov14_official_one_shot_nav import (
    SOURCE,strict_link_from_official,inspect_once,DiscoveryRejected,LIMIT
)
def html(body):
    return ('<html><title>出馬表 JRA</title><body>'+body+'</body></html>').encode("cp932")
GOOD='<a href="/JRADB/accessD.html?CNAME=pw01dde0108202605030720261114%2FAA">5回京都3日</a>'
class StubReply:
    status=200
    headers={"Content-Type":"text/html; charset=Shift_JIS"}
    def __init__(self,payload,url=SOURCE):
        self.raw=payload;self.url=url
    def read(self,n):return self.raw[:n]
    def geturl(self):return self.url
    def __enter__(self):return self
    def __exit__(self,*a):pass
class StubOpener:
    def __init__(self,response):
        self.response=response;self.calls=0
    def open(self,request,timeout=0):
        self.calls+=1
        assert timeout==12 and request.full_url==SOURCE and request.get_method()=="GET"
        return self.response
class Nov14NavigationTests(unittest.TestCase):
 def test_kyoto_current_link_from_actual_anchor_only(self):
    r=strict_link_from_official(html(GOOD))
    self.assertEqual(r["status"],"OFFICIAL_NOV14_KYOTO_MEETING_LINK_OBSERVED")
    self.assertEqual(len(r["observed_links"]),1)
    self.assertFalse(r["specific_racecard_url_verified"])
 def test_unpublished_no_guess(self):
    r=strict_link_from_official(html('<a href="#">前の開催</a>'))
    self.assertEqual(r["status"],"NOT_YET_VISIBLE")
    self.assertEqual(r["observed_links"],[])
 def test_tokyo_same_day_excluded(self):
    r=strict_link_from_official(html(GOOD.replace("京都","東京")))
    self.assertEqual(r["observed_links"],[])
 def test_future_date_not_guess(self):
    r=strict_link_from_official(html(GOOD.replace("20261114","20261115")))
    self.assertEqual(r["observed_links"],[])
 def test_multiple_kyoto_current_links_block(self):
    with self.assertRaises(DiscoveryRejected):
        strict_link_from_official(html(GOOD+GOOD.replace("%2FAA","%2FBB")))
 def test_offsite_link_with_correct_label_refused(self):
    bad=GOOD.replace("/JRADB/accessD.html","https://jra.jp.evil.invalid/JRADB/accessD.html")
    with self.assertRaises(DiscoveryRejected):
        strict_link_from_official(html(bad))
 def test_nonspecific_action_does_not_count(self):
    bad="<a onclick=\"doActionS('/JRADB/accessD.html','pw20261114/AA')\">京都</a>"
    self.assertEqual(strict_link_from_official(html(bad))["observed_links"],[])
 def test_invalid_cname_refused(self):
    bad=GOOD.replace("pw01dde0108202605030720261114%2FAA","someinvalid20261114")
    with self.assertRaises(DiscoveryRejected):
        strict_link_from_official(html(bad))
 def test_empty_html_refused(self):
    with self.assertRaises(DiscoveryRejected):strict_link_from_official(b"")
 def test_oversize_html_refused(self):
    with self.assertRaises(DiscoveryRejected):strict_link_from_official(b"x"*(LIMIT+1))
 def test_one_request_only_and_original_sha(self):
    opener=StubOpener(StubReply(html(GOOD)))
    with tempfile.TemporaryDirectory() as d:
        r=inspect_once(d,opener=opener,clock=AFTER_PUBLICATION)
        self.assertEqual(opener.calls,1)
        self.assertEqual(r["status"],"OFFICIAL_NOV14_KYOTO_MEETING_LINK_OBSERVED")
        self.assertFalse(r["current_prerace_market_verified"])
        self.assertTrue(r["source_sha256"])
 def test_redirect_rejected_without_pretending_success(self):
    opener=StubOpener(StubReply(html(GOOD),"https://evil.invalid/"))
    with tempfile.TemporaryDirectory() as d:
        r=inspect_once(d,opener=opener,clock=AFTER_PUBLICATION)
        self.assertEqual(r["status"],"FAILED_CLOSED")
        self.assertFalse(r["current_meeting_racecards_verified"])
 def test_bad_html_shape_blocked(self):
    opener=StubOpener(StubReply(b""))
    with tempfile.TemporaryDirectory() as d:
        r=inspect_once(d,opener=opener,clock=AFTER_PUBLICATION)
        self.assertEqual(r["status"],"FAILED_CLOSED")
 def test_prepublication_never_connects(self):
    opener=StubOpener(StubReply(html(GOOD)))
    with tempfile.TemporaryDirectory() as d:
        r=inspect_once(d,opener=opener,clock=BEFORE_PUBLICATION)
        self.assertEqual(r["status"],"WAIT_FOR_JRA_OFFICIAL_PUBLICATION_NO_HTTP")
        self.assertEqual(r["attempted_GET"],0)
        self.assertEqual(opener.calls,0)
 def test_after_publication_without_authorization_no_http(self):
    with tempfile.TemporaryDirectory() as d:
        r=inspect_once(d,clock=AFTER_PUBLICATION)
        self.assertEqual(r["status"],"LIVE_HTTP_NOT_EXPLICITLY_AUTHORIZED")
        self.assertEqual(r["attempted_GET"],0)
 def test_stale_meeting_discovery_never_connects(self):
    opener=StubOpener(StubReply(html(GOOD)))
    with tempfile.TemporaryDirectory() as d:
        r=inspect_once(d,opener=opener,
             clock=lambda:datetime(2026,11,14,1,0,tzinfo=timezone.utc))
        self.assertEqual(r["status"],"STALE_MEETING_DISCOVERY_NO_HTTP")
        self.assertEqual(opener.calls,0)
 def test_no_bet_or_prediction_claim(self):
    opener=StubOpener(StubReply(html(GOOD)))
    with tempfile.TemporaryDirectory() as d:
        r=inspect_once(d,opener=opener,clock=AFTER_PUBLICATION)
        self.assertFalse(r["paper_trade_authorized"])
        self.assertFalse(r["current_meeting_racecards_verified"])
if __name__=="__main__":unittest.main()
