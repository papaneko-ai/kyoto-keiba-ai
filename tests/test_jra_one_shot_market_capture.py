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
 FUTURE_PC='https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13'
 FUTURE_SP='https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261114%2FA0'
 def spec(self, **changes):
  from diagnostics.jra_one_shot_market_capture import DEFAULT_RACE_SPEC
  from dataclasses import replace
  changes.setdefault('pc_racecard_url',self.FUTURE_PC if changes.get('race_day')=='20261114' else DEFAULT_RACE_SPEC.pc_racecard_url)
  changes.setdefault('sp_racecard_url',self.FUTURE_SP if changes.get('race_day')=='20261114' else DEFAULT_RACE_SPEC.sp_racecard_url)
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

 def test_wrong_jst_start_day_rejected_without_http(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(SourceChainError,'verified_start_day_does_not_match_race_spec'):
    capture(d,channel="PC",verified_start_utc="2026-11-15T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-13T10:00:00Z",
      opener=RefusalOpener(),race_spec=self.spec(race_day="20261114",
        race_id="2026-11-14_KYOTO_11R",
        normal_sales_open_utc="2026-11-13T09:30:00Z"))

 def test_duplicate_active_horse_rejected_without_http(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(SourceChainError,'independent_active_roster_required'):
    capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(1,2)),now_utc="2026-11-06T10:00:00Z",
      opener=RefusalOpener())

 def test_wrong_race_key_blocked(self):
  with self.assertRaises(SourceChainError):
   self.spec(race_id="2026-11-07_KYOTO_10R").validate()

class DiagnosticCliAndRedirectTests(unittest.TestCase):
 def test_diagnostic_cli_flag_is_wired_to_capture(self):
  from pathlib import Path
  source=Path("diagnostics/jra_one_shot_market_capture.py").read_text(encoding="utf8")
  self.assertIn("authorized_live_http=args.authorized_live_http",source)
  self.assertIn("if args.authorized_live_http and not args.race_spec_json:",source)
  self.assertIn("opener=build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))",source)

 def test_redirected_same_host_different_url_refused(self):
  stub=StubOpener([(HTML,"https://jra.jp/JRADB/accessD.html?CNAME=UNEXPECTED")])
  with self.assertRaisesRegex(SourceChainError,"official_http_response_invalid"):
   http_fetch(stub,"PC",PC_RACECARD_URL)

 def test_redirected_pc_to_www_refused(self):
  stub=StubOpener([(HTML,"https://www.jra.go.jp/JRADB/accessD.html")])
  with self.assertRaisesRegex(SourceChainError,"official_http_response_invalid"):
   http_fetch(stub,"PC",PC_RACECARD_URL)

 def test_redirected_post_outside_target_refused(self):
  stub=StubOpener([(HTML,"https://jra.jp/JRADB/accessO.html?unexpected=1")])
  with self.assertRaisesRegex(SourceChainError,"official_http_response_invalid"):
   http_fetch(stub,"PC","https://jra.jp/JRADB/accessO.html",cname="pw01/AB")

 def test_explicit_unverified_origin_refused_without_request(self):
  stub=StubOpener([])
  with self.assertRaisesRegex(SourceChainError,"invalid_target_origin"):
   http_fetch(stub,"PC","https://jra.jp.evil.invalid/JRADB/accessD.html")
  self.assertEqual(stub.requests,[])

 def test_http_post_with_query_refused(self):
  stub=StubOpener([])
  with self.assertRaisesRegex(SourceChainError,"invalid_target_origin"):
   http_fetch(stub,"PC","https://jra.jp/JRADB/accessO.html?a=1",cname="pw01/AB")
  self.assertEqual(stub.requests,[])

class ExistingHybridOddsTests(unittest.TestCase):
 def setUp(self):
  from diagnostics.jra_one_shot_market_capture import DEFAULT_RACE_SPEC
  self.spec=DEFAULT_RACE_SPEC
  self.runners=((1,1),(2,2))
 def run_hybrid(self,primary="PC",states=None):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid
  calls=[]
  states=states or {}
  def stub(out,**kwargs):
   channel=kwargs["channel"]
   calls.append(channel)
   state=states.get(channel,"CAPTURE_BLOCKED")
   return {"channel":channel,"race_id":self.spec.race_id,"state":state,
           "pre_race_prices_accepted":state=="SOURCE_FROZEN"}
  with tempfile.TemporaryDirectory() as d:
   result=capture_hybrid(d,primary_channel=primary,
          verified_start_utc="2026-11-07T06:45:00Z",
          active_runners=self.runners,race_spec=self.spec,
          capture_fn=stub)
   import json,pathlib
   saved=json.loads((pathlib.Path(d)/"hybrid_receipt.json").read_text())
   self.assertEqual(saved,result)
  return result,calls
 def test_primary_success_no_duplicate_sp(self):
  r,calls=self.run_hybrid(states={"PC":"SOURCE_FROZEN"})
  self.assertEqual(calls,["PC"])
  self.assertEqual(r["state"],"SOURCE_ONLY_PRIMARY")
 def test_pc_error_sp_success(self):
  r,calls=self.run_hybrid(states={"PC":"CAPTURE_BLOCKED","SP":"SOURCE_FROZEN"})
  self.assertEqual(calls,["PC","SP"])
  self.assertEqual(r["selected_channel"],"SP")
  self.assertEqual(r["state"],"SOURCE_ONLY_FALLBACK")
 def test_sp_error_pc_success(self):
  r,calls=self.run_hybrid(primary="SP",
          states={"SP":"CAPTURE_BLOCKED","PC":"SOURCE_FROZEN"})
  self.assertEqual(calls,["SP","PC"])
  self.assertEqual(r["selected_channel"],"PC")
 def test_both_fail_no_third_try(self):
  r,calls=self.run_hybrid()
  self.assertEqual(calls,["PC","SP"])
  self.assertIsNone(r["selected_channel"])
  self.assertEqual(r["state"],"SAFE_STOP")
 def test_official_not_published_no_retry(self):
  for status in ("OFFICIAL_NOT_PUBLISHED","WAIT_FOR_OFFICIAL_SALES",
                 "CUTOFF_PASSED_NO_HTTP","REJECT_FINAL_ODDS",
                 "LIVE_HTTP_NOT_AUTHORIZED"):
   with self.subTest(status=status):
    r,calls=self.run_hybrid(states={"PC":status})
    self.assertEqual(calls,["PC"])
    self.assertIsNone(r["selected_channel"])
 def test_navigation_error_one_fallback(self):
  r,calls=self.run_hybrid(states={
   "PC":"OFFICIAL_MENU_NEEDS_RACE_NAVIGATION","SP":"SOURCE_FROZEN"})
  self.assertEqual(calls,["PC","SP"])
  self.assertEqual(r["state"],"SOURCE_ONLY_FALLBACK")
 def test_wrong_race_receipt_rejected_and_fallback(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid
  calls=[]
  def stub(out,**kwargs):
   calls.append(kwargs["channel"])
   return {"channel":kwargs["channel"],"race_id":"WRONG",
           "state":"SOURCE_FROZEN","pre_race_prices_accepted":True}
  with tempfile.TemporaryDirectory() as d:
   r=capture_hybrid(d,primary_channel="PC",
       verified_start_utc="2026-11-07T06:45:00Z",
       active_runners=self.runners,race_spec=self.spec,capture_fn=stub)
   self.assertEqual(calls,["PC"])
   self.assertEqual(r["state"],"SAFE_STOP")
 def test_refuse_fake_accepted_flag(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid
  def stub(out,**kwargs):
   return {"channel":kwargs["channel"],"race_id":self.spec.race_id,
           "state":"SOURCE_FROZEN","pre_race_prices_accepted":False}
  with tempfile.TemporaryDirectory() as d:
   r=capture_hybrid(d,primary_channel="PC",
       verified_start_utc="2026-11-07T06:45:00Z",
       active_runners=self.runners,race_spec=self.spec,capture_fn=stub)
   self.assertEqual(r["state"],"SAFE_STOP")
 def test_hybrid_never_authorizes_bet(self):
  r,_=self.run_hybrid(states={"PC":"SOURCE_FROZEN"})
  self.assertFalse(r["paper_trade_authorized"])
  self.assertFalse(r["actual_wager_authorized"])
  self.assertFalse(r["prediction_ready"])
class MeasuredSourceRouterIntegrationTests(unittest.TestCase):
 def test_auto_uses_previously_certified_sp_candidate(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid,DEFAULT_RACE_SPEC
  calls=[]
  def stub(out,**kw):
   calls.append(kw["channel"])
   return {"channel":kw["channel"],"race_id":DEFAULT_RACE_SPEC.race_id,
           "state":"SOURCE_FROZEN","pre_race_prices_accepted":True}
  with tempfile.TemporaryDirectory() as folder:
   result=capture_hybrid(folder,primary_channel="AUTO",
     verified_start_utc="2026-11-07T06:45:00Z",active_runners=((1,1),(2,2)),
     race_spec=DEFAULT_RACE_SPEC,capture_fn=stub)
  self.assertEqual(calls,["SP"])
  self.assertEqual(result["primary_channel"],"SP")
  self.assertEqual(result["route_basis"]["selection"],"HISTORICAL_MEASURED_CANDIDATE_ONLY")
  self.assertEqual(result["route_basis"]["sp_bytes_reduction_pct"],35.4)
  self.assertEqual(result["route_basis"]["sp_end_to_end_gain_pct"],17.4)
  self.assertFalse(result["prediction_ready"])
 def test_compromised_historical_benchmark_does_not_select_route(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid,DEFAULT_RACE_SPEC
  from unittest.mock import patch
  with patch("diagnostics.jra_benchmark_acceptance.audit_report",
             side_effect=ValueError("forged_sample")):
   with tempfile.TemporaryDirectory() as folder:
    with self.assertRaisesRegex(SourceChainError,"historical_route_evidence_unverified"):
     capture_hybrid(folder,primary_channel="AUTO",
       verified_start_utc="2026-11-07T06:45:00Z",
       active_runners=((1,1),(2,2)),race_spec=DEFAULT_RACE_SPEC)
 def test_manual_pc_override_remains_supported(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid,DEFAULT_RACE_SPEC
  calls=[]
  def stub(out,**kw):
   calls.append(kw["channel"])
   return {"channel":kw["channel"],"race_id":DEFAULT_RACE_SPEC.race_id,
           "state":"SOURCE_FROZEN","pre_race_prices_accepted":True}
  with tempfile.TemporaryDirectory() as folder:
   result=capture_hybrid(folder,primary_channel="PC",
      verified_start_utc="2026-11-07T06:45:00Z",active_runners=((1,1),(2,2)),
      race_spec=DEFAULT_RACE_SPEC,capture_fn=stub)
  self.assertEqual(calls,["PC"])
  self.assertEqual(result["route_basis"]["selection"],"EXPLICIT")
class ReceiptPersistenceRegressionTests(unittest.TestCase):
 def test_no_permission_receipt_is_valid_json_and_keeps_stop_reason(self):
  from pathlib import Path
  import json
  with tempfile.TemporaryDirectory() as folder:
   result=capture(folder,channel="PC",
      verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),
      now_utc="2026-11-06T10:00:00Z")
   saved=json.loads((Path(folder)/"receipt.json").read_text(encoding="utf8"))
   self.assertEqual(saved,result)
   self.assertEqual(saved["state"],"LIVE_HTTP_NOT_AUTHORIZED")
   self.assertFalse(saved["pre_race_prices_accepted"])
class ObservedOddsMenuTraversalTests(unittest.TestCase):
 def observed(self,channel,kind="meeting",day="2026年11月14日",duplicates=False):
  prefix="pw" if channel=="PC" else "sw"
  token=prefix+"15observed/AA"
  label="京都 11月14日 開催" if kind=="meeting" else "京都 11レース"
  a=f"""<a onclick="return doAction('/JRADB/accessO.html','{token}')">{label}</a>"""
  if duplicates:
   a+=f"""<a onclick="return doAction('/JRADB/accessO.html','{prefix}15other/BB')">{label}</a>"""
  return html(day+" 京都 "+a)
 def spec(self):
  from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec
  return ObservedRaceSpec(
   "20261114",11,"2026-11-14_KYOTO_11R","京都",
   "https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13",
   "https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261114%2FA0",
   "2026-11-13T09:30:00Z")
 def next_action(self,raw,channel,step):
  from diagnostics.jra_one_shot_market_capture import observed_next_market_action
  return observed_next_market_action(raw,channel,self.spec(),step=step)
 def test_pc_meeting_action_comes_from_html(self):
  self.assertEqual(self.next_action(self.observed("PC"),"PC",0),"pw15observed/AA")
 def test_sp_meeting_action_comes_from_html(self):
  self.assertEqual(self.next_action(self.observed("SP"),"SP",0),"sw15observed/AA")
 def test_pc_exact_11_race_from_html(self):
  self.assertEqual(self.next_action(self.observed("PC","race"),"PC",1),"pw15observed/AA")
 def test_sp_exact_11_race_from_html(self):
  self.assertEqual(self.next_action(self.observed("SP","race"),"SP",1),"sw15observed/AA")
 def test_unobserved_date_never_guessed(self):
  with self.assertRaisesRegex(SourceChainError,"market_navigation_day_not_visible"):
   self.next_action(self.observed("PC",day="2026年11月7日").replace("11月14日".encode("cp932"),"11月7日".encode("cp932")),"PC",0)
 def test_conflicting_official_links_are_quarantined(self):
  with self.assertRaisesRegex(SourceChainError,"ambiguous"):
   self.next_action(self.observed("PC",duplicates=True),"PC",0)
 def test_other_channel_token_rejected(self):
  with self.assertRaisesRegex(SourceChainError,"link_missing"):
   self.next_action(self.observed("SP"),"PC",0)
 def test_unbound_race_label_from_other_meeting_is_not_selected(self):
  raw=self.observed("PC","race").replace("京都 11レース".encode("cp932"),"11レース".encode("cp932"))
  with self.assertRaisesRegex(SourceChainError,"link_missing"):
   self.next_action(raw,"PC",1)
 def test_other_race_label_not_selected(self):
  raw=self.observed("PC","race").replace("11レース".encode("cp932"),"10レース".encode("cp932"))
  with self.assertRaisesRegex(SourceChainError,"link_missing"):
   self.next_action(raw,"PC",1)
 def test_final_odds_not_used_as_navigation(self):
  raw=self.observed("PC").replace("京都 ".encode("cp932"),"最終オッズ 京都 ".encode("cp932"),1)
  with self.assertRaisesRegex(SourceChainError,"market_navigation_not_live"):
   self.next_action(raw,"PC",0)
 def test_unsupported_third_link_refused(self):
  with self.assertRaisesRegex(SourceChainError,"unsupported_market_navigation_step"):
   self.next_action(self.observed("PC"),"PC",2)

class BoundedObservedMenuIntegrationTests(unittest.TestCase):
 def test_two_live_menu_hops_are_saved_without_guessing(self):
  from unittest.mock import patch
  from pathlib import Path
  from datetime import datetime,timezone
  from diagnostics.jra_one_shot_market_capture import capture,ObservedRaceSpec
  from diagnostics.jra_one_shot_market_capture import MOBILE_UA
  spec=ObservedRaceSpec("20261114",11,"2026-11-14_KYOTO_11R","京都",
   "https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13",
   "https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261114%2FA0",
   "2026-11-13T09:30:00Z")
  def menu(label,token):
   return html("2026年11月14日 京都 "+f"""<a onclick="return doAction('/JRADB/accessO.html','{token}')">{label}</a>""")
  now=datetime(2026,11,13,10,tzinfo=timezone.utc)
  pages=[
   (html(LINK),spec.pc_racecard_url),
   (menu("京都 11月14日 開催","pw15meeting/AA"),"https://jra.jp/JRADB/accessO.html"),
   (menu("京都 11レース","pw15race/BB"),"https://jra.jp/JRADB/accessO.html"),
   (menu("開催済レース一覧","pw15end/CC"),"https://jra.jp/JRADB/accessO.html")
  ]
  stub=StubOpener(pages)
  with tempfile.TemporaryDirectory() as d:
   with patch("diagnostics.jra_one_shot_market_capture.datetime") as clock:
    clock.now.return_value=now
    result=capture(d,channel="PC",verified_start_utc="2026-11-14T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc=now.isoformat(),opener=stub,race_spec=spec)
   self.assertEqual(len(stub.requests),4)
   self.assertEqual(result["state"],"OFFICIAL_MENU_NEEDS_RACE_NAVIGATION")
   self.assertEqual([x["step"] for x in result["request_receipts"]],
     ["racecard","odds_menu","odds_navigation_1","odds_navigation_2"])
   self.assertEqual((Path(d)/"official_odds_navigation_1.html").read_bytes(),pages[2][0])
   self.assertEqual((Path(d)/"official_odds_navigation_2.html").read_bytes(),pages[3][0])
   self.assertFalse(result["pre_race_prices_accepted"])
class VerifiedNumberedRosterHandoffTests(unittest.TestCase):
 def spec(self):
  from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec
  return ObservedRaceSpec("20261114",11,"2026-11-14_KYOTO_11R","京都",
    "https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13",
    "https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261114%2FA0",
    "2026-11-13T09:30:00Z")
 def roster(self):
  return {"race_date":"2026-11-14","race_number":11,"venue":"KYOTO",
    "source_url":self.spec().sp_racecard_url,"source_sha256":"a"*64,
    "source_bytes":60000,"fetched_at_utc":"2026-11-13T03:00:00Z",
    "runners":[{"horse_number":1,"frame_number":1,"horse_name":"A"},
               {"horse_number":2,"frame_number":2,"horse_name":"B"}]}
 def check(self,r):
  from diagnostics.jra_one_shot_market_capture import verified_roster_from_snapshot
  return verified_roster_from_snapshot(r,self.spec(),race_start_utc="2026-11-14T06:45:00Z")
 def test_current_numbered_official_bound_roster(self):
  self.assertEqual(self.check(self.roster()),((1,1),(2,2)))
 def test_old_nov7_roster_blocked_before_network(self):
  r=self.roster();r["race_date"]="2026-11-07"
  with self.assertRaisesRegex(SourceChainError,"roster_meeting_race_source_mismatch"):
   self.check(r)
 def test_old_pc_racecard_url_blocked(self):
  r=self.roster();r["source_url"]="https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261107%2F13"
  with self.assertRaisesRegex(SourceChainError,"roster_meeting_race_source_mismatch"):
   self.check(r)
 def test_different_race_number_blocked(self):
  r=self.roster();r["race_number"]=10
  with self.assertRaisesRegex(SourceChainError,"roster_meeting_race_source_mismatch"):
   self.check(r)
 def test_unproven_source_original_rejected(self):
  r=self.roster();r["source_sha256"]="notverified"
  with self.assertRaisesRegex(SourceChainError,"roster_original_provenance_missing"):
   self.check(r)
 def test_duplicate_horse_numbers_rejected(self):
  r=self.roster();r["runners"][1]["horse_number"]=1
  with self.assertRaisesRegex(SourceChainError,"roster_number_sequence_invalid"):
   self.check(r)
 def test_race_started_roster_rejected(self):
  r=self.roster();r["fetched_at_utc"]="2026-11-14T07:00:00Z"
  with self.assertRaisesRegex(SourceChainError,"roster_capture_not_before_start"):
   self.check(r)
 def test_withdrawal_needs_fresh_status_not_stale_roster(self):
  r=self.roster();r["runners"][1]["status"]="取消"
  with self.assertRaisesRegex(SourceChainError,"roster_withdrawal_needs_current_independent_proof"):
   self.check(r)

class OfficialTwoSecondPacingTests(unittest.TestCase):
 def test_bounded_sequence_waits_between_requests(self):
  from diagnostics.jra_one_shot_market_capture import RequestPacer
  state=[0.0];waits=[]
  def sleep(delay):
   waits.append(delay);state[0]+=delay
  pacer=RequestPacer(clock=lambda:state[0],sleep=sleep)
  pacer.before_request()
  pacer.before_request()
  self.assertEqual(waits,[2.0])
  state[0]+=2.25
  pacer.before_request()
  self.assertEqual(waits,[2.0])
 def test_gap_shorter_than_two_seconds_is_rejected(self):
  from diagnostics.jra_one_shot_market_capture import RequestPacer
  with self.assertRaisesRegex(SourceChainError,"jra_request_gap_under_two_seconds"):
   RequestPacer(min_gap_seconds=1)
 def test_pacer_is_used_by_existing_official_http_fetch(self):
  from diagnostics.jra_one_shot_market_capture import http_fetch,RequestPacer
  state=[0.0];waits=[]
  def sleep(delay):
   waits.append(delay);state[0]+=delay
  pacer=RequestPacer(clock=lambda:state[0],sleep=sleep)
  stub=StubOpener([(HTML,PC_RACECARD_URL),(HTML,PC_RACECARD_URL)])
  http_fetch(stub,"PC",PC_RACECARD_URL,pacer=pacer)
  http_fetch(stub,"PC",PC_RACECARD_URL,pacer=pacer)
  self.assertEqual(len(stub.requests),2)
  self.assertEqual(waits,[2.0])
class RealChannelRosterBindingTests(unittest.TestCase):
 def spec(self):
  from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec
  return ObservedRaceSpec("20261114",11,"2026-11-14_KYOTO_11R","京都",
    "https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13",
    "https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261114%2FA0",
    "2026-11-13T09:30:00Z")
 def test_pc_uses_existing_parser_and_matches_numbers_and_frames(self):
  from diagnostics.jra_one_shot_market_capture import verify_live_racecard_roster
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))) as parser:
   r=verify_live_racecard_roster(b"<html>saved</html>","PC",self.spec(),((1,1),(2,2)),((1,1,"馬A"),(2,2,"馬B")))
   self.assertEqual(r["count"],2)
   parser.assert_called_once()
 def test_pc_roster_disagreement_is_blocked(self):
  from diagnostics.jra_one_shot_market_capture import verify_live_racecard_roster
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
             return_value=((1,1,"馬A"),(2,3,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"official_racecard_numbered_roster_mismatch"):
    verify_live_racecard_roster(b"<html>saved</html>","PC",self.spec(),((1,1),(2,2)),((1,1,"馬A"),(2,2,"馬B")))
 def test_sp_accepts_same_race_original(self):
  from diagnostics.jra_one_shot_market_capture import verify_live_racecard_roster
  from unittest.mock import patch
  raw=html("2026年11月14日 京都 11レース")
  with patch("diagnostics.jra_pc_sp_benchmark.sp_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))) as parser:
   r=verify_live_racecard_roster(raw,"SP",self.spec(),((1,1),(2,2)),((1,1,"馬A"),(2,2,"馬B")))
   self.assertEqual(r["channel"],"SP")
   parser.assert_called_once()
 def test_sp_other_date_blocked_even_if_numbers_match(self):
  from diagnostics.jra_one_shot_market_capture import verify_live_racecard_roster
  from unittest.mock import patch
  raw=html("2026年11月7日 京都 11レース")
  with patch("diagnostics.jra_pc_sp_benchmark.sp_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"sp_racecard_date_race_venue_not_proven"):
    verify_live_racecard_roster(raw,"SP",self.spec(),((1,1),(2,2)),((1,1,"馬A"),(2,2,"馬B")))
 def test_sp_wrong_race_blocked_even_if_numbers_match(self):
  from diagnostics.jra_one_shot_market_capture import verify_live_racecard_roster
  from unittest.mock import patch
  raw=html("2026年11月14日 京都 10レース")
  with patch("diagnostics.jra_pc_sp_benchmark.sp_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"sp_racecard_date_race_venue_not_proven"):
    verify_live_racecard_roster(raw,"SP",self.spec(),((1,1),(2,2)),((1,1,"馬A"),(2,2,"馬B")))
 def test_live_capture_blocks_before_odds_menu_if_new_original_is_wrong(self):
  from unittest.mock import patch
  spec=self.spec()
  stub=StubOpener([(html(LINK),spec.pc_racecard_url)])
  with tempfile.TemporaryDirectory() as d:
   with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
       return_value=((1,1,"馬A"),(2,3,"馬B"))):
    r=capture(d,channel="PC",verified_start_utc="2026-11-14T06:45:00Z",
     active_runners=((1,1),(2,2)),now_utc="2026-11-13T10:00:00Z",
     opener=stub,race_spec=spec,authorized_live_http=True,
     expected_named_runners=((1,1,"馬A"),(2,2,"馬B")))
  self.assertEqual(r["state"],"CAPTURE_BLOCKED")
  self.assertEqual(len(stub.requests),1)
  self.assertFalse(r["pre_race_prices_accepted"])
 def test_pc_same_numbers_but_wrong_horse_name_is_rejected(self):
  from diagnostics.jra_one_shot_market_capture import verify_live_racecard_roster
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
             return_value=((1,1,"異なる馬"),(2,2,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"official_racecard_named_roster_mismatch"):
    verify_live_racecard_roster(b"<html>saved</html>","PC",self.spec(),
       ((1,1),(2,2)),((1,1,"馬A"),(2,2,"馬B")))
 def test_unverified_reference_cannot_authorize_live_racecard(self):
  from diagnostics.jra_one_shot_market_capture import verify_live_racecard_roster
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"official_named_roster_reference_required"):
    verify_live_racecard_roster(b"<html>saved</html>","PC",self.spec(),((1,1),(2,2)),None)
if __name__=="__main__":unittest.main()
