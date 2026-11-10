"""One-shot JRA odds collection: offline fail-closed smoke tests."""
import unittest,tempfile
from datetime import datetime,timezone
from diagnostics.jra_one_shot_market_capture import (
  capture,exact_odds_action,http_fetch,SourceChainError,
  PC_RACECARD_URL,SP_RACECARD_URL,ObservedRaceSpec
)
HTML=(b"<html><title>Odds</title></html>")
class RefusalOpener:
 def open(self,request,timeout=None):
  raise AssertionError("network should not be used")
class StubResponse:
 def __init__(self,raw,final):
  self.raw=raw;self.url=final;self.status=200
  self.headers={"Content-Type":"text/html; charset=Shift_JIS"}
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):return self.raw[:n]
 def geturl(self):return self.url
class StubOpener:
 def __init__(self,raws):self.raws=list(raws);self.requests=[]
 def open(self,request,timeout=None):
  self.requests.append(request)
  if not self.raws:raise AssertionError("unexpected extra HTTP")
  raw,final=self.raws.pop(0)
  return StubResponse(raw,final)
def html(body):
 return ("<html><title>出馬表 JRA</title><body>"+body+"</body></html>").encode("cp932")
LINK="""<a href="#" onclick="return doAction('/JRADB/accessO.html', 'pw15oli00/6D')">オッズ</a>"""
class OneShotTests(unittest.TestCase):
 def test_before_sales_no_http(self):
  with tempfile.TemporaryDirectory() as d:
   r=capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-06T04:00:00Z",opener=RefusalOpener())
   self.assertEqual(r["state"],"WAIT_FOR_OFFICIAL_SALES")
   self.assertEqual(r["request_receipts"],[])
 def test_cutoff_no_http(self):
  with tempfile.TemporaryDirectory() as d:
   r=capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-07T06:40:00Z",opener=RefusalOpener())
   self.assertEqual(r["state"],"CUTOFF_PASSED_NO_HTTP")
 def test_exact_official_odds_link(self):
  self.assertEqual(exact_odds_action(html(LINK),"PC"),"pw15oli00/6D")
 def test_duplicated_different_menu_tokens_are_blocked(self):
  with self.assertRaises(SourceChainError):
   exact_odds_action(html(LINK+LINK.replace("6D","XX")),"PC")
 def test_cross_channel_token_is_blocked(self):
  with self.assertRaises(SourceChainError):
   exact_odds_action(html(LINK),"SP")
 def test_official_unpublished_stops_after_two_requests(self):
  race=html(LINK)
  menu=html("今週のオッズは未発表です。")
  stub=StubOpener([(race,PC_RACECARD_URL),(menu,"https://jra.jp/JRADB/accessO.html")])
  with tempfile.TemporaryDirectory() as d:
   r=capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-06T10:00:00Z",opener=stub)
   self.assertEqual(r["state"],"OFFICIAL_NOT_PUBLISHED")
   self.assertEqual(len(stub.requests),2)
   self.assertFalse(r["pre_race_prices_accepted"])
 def test_official_menu_without_race_link_never_guesses(self):
  stub=StubOpener([(html(LINK),PC_RACECARD_URL),
     (html("今週のオッズは公開されています。"),"https://jra.jp/JRADB/accessO.html")])
  with tempfile.TemporaryDirectory() as d:
   r=capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-06T10:00:00Z",opener=stub)
   self.assertEqual(r["state"],"OFFICIAL_MENU_NEEDS_RACE_NAVIGATION")
   self.assertEqual(len(stub.requests),2)
 def test_unofficial_final_host_rejected(self):
  stub=StubOpener([(html(LINK),"https://jra.jp.evil.example/JRADB/accessD.html")])
  with tempfile.TemporaryDirectory() as d:
   r=capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-06T10:00:00Z",opener=stub)
   self.assertEqual(r["state"],"CAPTURE_BLOCKED")
 def test_original_capture_timestamp_always_present(self):
  stub=StubOpener([(html(LINK),PC_RACECARD_URL),
                   (html("今週のオッズは未発表です"),"https://jra.jp/JRADB/accessO.html")])
  with tempfile.TemporaryDirectory() as d:
   r=capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-06T10:00:00Z",opener=stub)
   self.assertTrue(all(x["captured_at_utc"] for x in r["request_receipts"]))

class FutureRaceCaptureTests(unittest.TestCase):
 def spec(self, **changes):
  from diagnostics.jra_one_shot_market_capture import DEFAULT_RACE_SPEC
  from dataclasses import replace
  return replace(DEFAULT_RACE_SPEC,**changes)

 def test_future_day_needs_verified_sales_time(self):
  with self.assertRaises(SourceChainError):
   self.spec(race_day="20261114",race_id="2026-11-14_KYOTO_11R").validate()

 def test_valid_future_day_blocks_http_without_authorization(self):
  with tempfile.TemporaryDirectory() as d:
   r=capture(d,channel="PC",verified_start_utc="2026-11-14T06:45:00Z",
     active_runners=((1,1),(2,2)),now_utc="2026-11-13T10:00:00Z",
     race_spec=self.spec(race_day="20261114",race_id="2026-11-14_KYOTO_11R",
                        normal_sales_open_utc="2026-11-13T09:30:00Z"))
   self.assertEqual(r["state"],"LIVE_HTTP_NOT_AUTHORIZED")
   self.assertEqual(r["request_receipts"],[])
   self.assertFalse(r["prediction_ready"])

 def test_future_day_uses_supplied_official_navigation_with_stub(self):
  url="https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13"
  stub=StubOpener([(html(LINK),url),
       (html("今週のオッズは未発表です"),"https://jra.jp/JRADB/accessO.html")])
  with tempfile.TemporaryDirectory() as d:
   r=capture(d,channel="PC",verified_start_utc="2026-11-14T06:45:00Z",
     active_runners=((1,1),(2,2)),now_utc="2026-11-13T10:00:00Z",opener=stub,
     race_spec=self.spec(race_day="20261114",race_id="2026-11-14_KYOTO_11R",
       normal_sales_open_utc="2026-11-13T09:30:00Z",pc_racecard_url=url))
   self.assertEqual(r["state"],"OFFICIAL_NOT_PUBLISHED")
   self.assertEqual(r["race_id"],"2026-11-14_KYOTO_11R")
   self.assertEqual(len(stub.requests),2)

 def test_unofficial_future_url_blocked_before_http(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(SourceChainError):
    capture(d,channel="PC",verified_start_utc="2026-11-14T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-13T10:00:00Z",
      opener=RefusalOpener(),race_spec=self.spec(
        pc_racecard_url="https://jra.jp.evil.example/JRADB/accessD.html?CNAME=pw1%2F13"))

 def test_missing_future_navigation_token_blocked(self):
  with self.assertRaises(SourceChainError):
   self.spec(pc_racecard_url="https://jra.jp/JRADB/accessD.html").validate()

 def test_wrong_race_key_blocked(self):
  with self.assertRaises(SourceChainError):
   self.spec(race_id="2026-11-07_KYOTO_10R").validate()

if __name__=="__main__":unittest.main()
