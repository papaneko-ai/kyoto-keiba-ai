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
 def test_403_429_and_redirect_do_not_switch_host(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid
  import tempfile
  for blocked in ("HTTPError:HTTP Error 403: Forbidden",
                  "HTTPError:HTTP Error 429: Too Many Requests",
                  "SourceChainError:redirect_forbidden",
                  "SourceChainError:official_http_response_invalid"):
   with self.subTest(blocked=blocked):
    calls=[]
    def stub(out,**kwargs):
     channel=kwargs["channel"]
     calls.append(channel)
     return {"channel":channel,"race_id":self.spec.race_id,
             "state":"CAPTURE_BLOCKED","reason":blocked,
             "pre_race_prices_accepted":False}
    with tempfile.TemporaryDirectory() as d:
     r=capture_hybrid(d,primary_channel="PC",
       verified_start_utc="2026-11-07T06:45:00Z",
       active_runners=self.runners,race_spec=self.spec,capture_fn=stub)
    self.assertEqual(calls,["PC"])
    self.assertEqual(r["state"],"SAFE_STOP")
    self.assertTrue(r["primary_semantic_conflict_blocked"])
 def test_404_can_use_preobserved_sp_one_time(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid
  calls=[]
  def stub(out,**kwargs):
   channel=kwargs["channel"]
   calls.append(channel)
   return {"channel":channel,"race_id":self.spec.race_id,
           "state":"CAPTURE_BLOCKED" if channel=="PC" else "SOURCE_FROZEN",
           "reason":"HTTPError:HTTP Error 404: Not Found" if channel=="PC" else None,
           "pre_race_prices_accepted":channel=="SP"}
  with tempfile.TemporaryDirectory() as d:
   r=capture_hybrid(d,primary_channel="PC",
       verified_start_utc="2026-11-07T06:45:00Z",
       active_runners=self.runners,race_spec=self.spec,capture_fn=stub)
  self.assertEqual(calls,["PC","SP"])
  self.assertEqual(r["state"],"SOURCE_ONLY_FALLBACK")
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
class CanonicalRacecardReuseTests(unittest.TestCase):
 def spec(self):
  from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec
  return ObservedRaceSpec("20261114",11,"2026-11-14_KYOTO_11R","京都",
    "https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13",
    "https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261114%2FA0",
    "2026-11-13T09:30:00Z")
 def verify(self,raw,channel,named=((1,1,"馬A"),(2,2,"馬B"))):
  from diagnostics.jra_one_shot_market_capture import verify_live_racecard_roster
  return verify_live_racecard_roster(
    raw,channel,self.spec(),((1,1),(2,2)),named,
    captured_at_utc="2026-11-13T10:00:00Z",
    observed_utc="2026-11-13T10:00:01Z",
    verified_start_utc="2026-11-14T06:45:00Z")
 def test_pc_reuses_existing_canonical_reconciler(self):
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))) as parser:
   result=self.verify(b"<html>saved</html>","PC")
   self.assertEqual(result["reused_reconciler"],"reconcile_saved_racecards")
   self.assertEqual(result["count"],2)
   parser.assert_called_once()
 def test_pc_wrong_frame_blocked_by_canonical_reconciler(self):
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
             return_value=((1,1,"馬A"),(2,3,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"official_racecard_three_column_mismatch"):
    self.verify(b"<html>saved</html>","PC")
 def test_pc_same_number_wrong_name_blocked_by_canonical_reconciler(self):
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
             return_value=((1,1,"異なる馬"),(2,2,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"official_racecard_three_column_mismatch"):
    self.verify(b"<html>saved</html>","PC")
 def test_sp_same_race_reuses_canonical_reconciler(self):
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.sp_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))) as parser:
   result=self.verify(html("2026年11月14日 京都 11レース"),"SP")
   self.assertEqual(result["reused_reconciler"],"reconcile_saved_racecards")
   parser.assert_called_once()
 def test_sp_wrong_date_blocked(self):
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.sp_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"sp_racecard_date_race_venue_not_proven"):
    self.verify(html("2026年11月7日 京都 11レース"),"SP")
 def test_sp_wrong_race_blocked(self):
  from unittest.mock import patch
  with patch("diagnostics.jra_pc_sp_benchmark.sp_rows",
             return_value=((1,1,"馬A"),(2,2,"馬B"))):
   with self.assertRaisesRegex(SourceChainError,"sp_racecard_date_race_venue_not_proven"):
    self.verify(html("2026年11月14日 京都 10レース"),"SP")
 def test_reference_missing_is_blocked(self):
  with self.assertRaisesRegex(SourceChainError,"official_named_roster_reference_required"):
   self.verify(b"<html>saved</html>","PC",None)
 def test_live_capture_stops_after_one_original_if_name_differs(self):
  from unittest.mock import patch
  spec=self.spec()
  stub=StubOpener([(html(LINK),spec.pc_racecard_url)])
  with tempfile.TemporaryDirectory() as d:
   with patch("diagnostics.jra_pc_sp_benchmark.pc_rows",
              return_value=((1,1,"別馬"),(2,2,"馬B"))):
    result=capture(d,channel="PC",verified_start_utc="2026-11-14T06:45:00Z",
      active_runners=((1,1),(2,2)),expected_named_runners=((1,1,"馬A"),(2,2,"馬B")),
      now_utc="2026-11-13T10:00:00Z",opener=stub,race_spec=spec,authorized_live_http=True)
  self.assertEqual(result["state"],"CAPTURE_BLOCKED")
  self.assertEqual(len(stub.requests),1)
  self.assertFalse(result["pre_race_prices_accepted"])
class ExplicitDualSourceObservationTests(unittest.TestCase):
 def spec(self):
  from diagnostics.jra_one_shot_market_capture import DEFAULT_RACE_SPEC
  return DEFAULT_RACE_SPEC
 def run_check(self,states):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid
  calls=[]
  def runner(out,**kwargs):
   channel=kwargs["channel"]
   calls.append(channel)
   state=states[channel]
   return {"race_id":self.spec().race_id,"channel":channel,"state":state,
           "pre_race_prices_accepted":state=="SOURCE_FROZEN"}
  with tempfile.TemporaryDirectory() as d:
   result=capture_hybrid(d,primary_channel="SP",race_spec=self.spec(),
      verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),capture_fn=runner,
      independent_crosscheck=True)
  return result,calls
 def test_independent_crosscheck_observes_both_original_channels(self):
  r,calls=self.run_check({"SP":"SOURCE_FROZEN","PC":"SOURCE_FROZEN"})
  self.assertEqual(calls,["SP","PC"])
  self.assertTrue(r["dual_independent_source_originals"])
  self.assertEqual(r["selected_channel"],"SP")
  self.assertEqual(r["state"],"DUAL_SOURCES_CAPTURED_PRICE_PARITY_UNVERIFIED")
  self.assertFalse(r["market_value_parity_verified"])
  self.assertFalse(r["cross_time_odds_comparison_authorized"])
  self.assertFalse(r["prediction_ready"])
 def test_secondary_failure_does_not_hide_original_incident(self):
  r,calls=self.run_check({"SP":"SOURCE_FROZEN","PC":"CAPTURE_BLOCKED"})
  self.assertEqual(calls,["SP","PC"])
  self.assertFalse(r["dual_independent_source_originals"])
  self.assertEqual(r["attempts"][1]["state"],"CAPTURE_BLOCKED")
  self.assertEqual(r["state"],"SOURCE_ONLY_PRIMARY")
  self.assertFalse(r["market_value_parity_verified"])
 def test_publication_refusal_never_forces_secondary_get(self):
  r,calls=self.run_check({"SP":"OFFICIAL_NOT_PUBLISHED","PC":"SOURCE_FROZEN"})
  self.assertEqual(calls,["SP"])
  self.assertEqual(r["state"],"SAFE_STOP")
 def test_crosscheck_requires_explicit_boolean(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(SourceChainError,"crosscheck_boolean_required"):
    capture_hybrid(d,primary_channel="SP",race_spec=self.spec(),
       verified_start_utc="2026-11-07T06:45:00Z",active_runners=((1,1),(2,2)),
       independent_crosscheck="true")
class SemanticConflictsCannotFallbackTests(unittest.TestCase):
 def check(self,first_reason,first_state="CAPTURE_BLOCKED"):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid,DEFAULT_RACE_SPEC
  calls=[]
  def runner(out,**kw):
   channel=kw["channel"];calls.append(channel)
   if channel=="PC":
    return {"race_id":DEFAULT_RACE_SPEC.race_id,"channel":"PC",
            "state":first_state,"reason":first_reason,
            "pre_race_prices_accepted":False}
   return {"race_id":DEFAULT_RACE_SPEC.race_id,"channel":"SP",
           "state":"SOURCE_FROZEN","pre_race_prices_accepted":True}
  with tempfile.TemporaryDirectory() as d:
   result=capture_hybrid(d,primary_channel="PC",
     verified_start_utc="2026-11-07T06:45:00Z",
     active_runners=((1,1),(2,2)),race_spec=DEFAULT_RACE_SPEC,capture_fn=runner)
  return result,calls
 def test_named_roster_source_conflict_is_terminal(self):
  r,calls=self.check("SourceChainError:official_racecard_three_column_mismatch:ROSTER_MISMATCH")
  self.assertEqual(calls,["PC"])
  self.assertEqual(r["state"],"SAFE_STOP")
  self.assertTrue(r["primary_semantic_conflict_blocked"])
 def test_final_market_phase_conflict_is_terminal(self):
  r,calls=self.check("SourceChainError:conflicting_market_phases")
  self.assertEqual(calls,["PC"])
  self.assertTrue(r["primary_semantic_conflict_blocked"])
 def test_transport_error_preserves_conditional_fallback(self):
  r,calls=self.check("TimeoutError:timed_out")
  self.assertEqual(calls,["PC","SP"])
  self.assertEqual(r["state"],"SOURCE_ONLY_FALLBACK")

class SourceOriginalImmutabilityAndPostProofTests(unittest.TestCase):
 def test_official_post_retains_observed_action_and_wire_body_hash(self):
  from hashlib import sha256
  stub=StubOpener([(HTML,"https://jra.jp/JRADB/accessO.html")])
  r=http_fetch(stub,"PC","https://jra.jp/JRADB/accessO.html",cname="pw15fromHtml/AA")
  req=stub.requests[0]
  self.assertEqual(r["observed_action_token"],"pw15fromHtml/AA")
  self.assertEqual(r["requested_url"],"https://jra.jp/JRADB/accessO.html")
  self.assertEqual(r["response_url"],"https://jra.jp/JRADB/accessO.html")
  self.assertEqual(r["method"],"POST")
  self.assertEqual(r["post_body_sha256"],sha256(req.data).hexdigest())
  self.assertEqual(r["post_body_size"],len(req.data))
  self.assertIn(b"cname=pw15fromHtml%2FAA",req.data)
 def test_official_get_retains_exact_requested_url_and_no_post(self):
  stub=StubOpener([(HTML,PC_RACECARD_URL)])
  r=http_fetch(stub,"PC",PC_RACECARD_URL)
  self.assertEqual(r["requested_url"],PC_RACECARD_URL)
  self.assertIsNone(r["observed_action_token"])
  self.assertIsNone(r["post_body_sha256"])
  self.assertEqual(r["post_body_size"],0)
 def test_nonempty_previous_capture_is_rejected_before_network(self):
  from pathlib import Path
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/"official_racecard.html").write_bytes(b"old-original")
   with self.assertRaisesRegex(SourceChainError,"source_output_contains_existing_evidence"):
    capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-06T10:00:00Z",
      opener=RefusalOpener())
   self.assertEqual((Path(d)/"official_racecard.html").read_bytes(),b"old-original")
 def test_original_write_is_exclusive_even_if_prior_check_raced(self):
  from pathlib import Path
  from hashlib import sha256
  from diagnostics.jra_one_shot_market_capture import persist_original_once
  with tempfile.TemporaryDirectory() as d:
   receipt={"sha256":sha256(HTML).hexdigest()}
   persist_original_once(Path(d),"official_racecard.html",HTML,receipt)
   with self.assertRaisesRegex(SourceChainError,"source_original_already_exists"):
    persist_original_once(Path(d),"official_racecard.html",b"new-bytes",
                          {"sha256":sha256(b"new-bytes").hexdigest()})
   self.assertEqual((Path(d)/"official_racecard.html").read_bytes(),HTML)
 def test_original_sha_mismatch_never_written(self):
  from pathlib import Path
  from diagnostics.jra_one_shot_market_capture import persist_original_once
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(SourceChainError,"source_original_receipt_hash_disagrees"):
    persist_original_once(Path(d),"official_racecard.html",HTML,{"sha256":"a"*64})
   self.assertFalse((Path(d)/"official_racecard.html").exists())
 def test_second_attempt_after_completed_receipt_is_rejected(self):
  from pathlib import Path
  with tempfile.TemporaryDirectory() as d:
   a=capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-06T04:00:00Z",
      opener=RefusalOpener())
   self.assertEqual(a["state"],"WAIT_FOR_OFFICIAL_SALES")
   before=(Path(d)/"receipt.json").read_bytes()
   with self.assertRaisesRegex(SourceChainError,"source_output_contains_existing_evidence"):
    capture(d,channel="PC",verified_start_utc="2026-11-07T06:45:00Z",
      active_runners=((1,1),(2,2)),now_utc="2026-11-06T10:00:00Z",
      opener=RefusalOpener())
   self.assertEqual((Path(d)/"receipt.json").read_bytes(),before)

class ImmutableTerminalReceiptTests(unittest.TestCase):
 def test_receipt_is_exclusively_created(self):
  from pathlib import Path
  from diagnostics.jra_one_shot_market_capture import persist_receipt_once
  with tempfile.TemporaryDirectory() as d:
   persist_receipt_once(Path(d),"receipt.json",{"state":"SAFE_STOP"})
   with self.assertRaisesRegex(SourceChainError,"source_receipt_already_exists"):
    persist_receipt_once(Path(d),"receipt.json",{"state":"SOURCE_FROZEN"})
   self.assertEqual(__import__("json").loads((Path(d)/"receipt.json").read_text())["state"],"SAFE_STOP")
 def test_reject_nan_in_evidence_receipt(self):
  from pathlib import Path
  from diagnostics.jra_one_shot_market_capture import persist_receipt_once
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):
    persist_receipt_once(Path(d),"receipt.json",{"unsafe":float("nan")})

class OfficialOneShotWorkflowHandoffContractTests(unittest.TestCase):
 def workflow(self):
  from pathlib import Path
  return Path(".github/workflows/jra-observed-odds-manual-oneshot.yml").read_text(encoding="utf8")
 def test_optional_independent_snapshot_is_wired_to_existing_three_original_cli(self):
  workflow=self.workflow()
  self.assertIn("snapshot_path:",workflow)
  self.assertIn("THREE_ORIGINAL_SNAPSHOT:",workflow)
  self.assertIn("diagnostics.p1_atomic_dual_market_handoff",workflow)
  self.assertIn("verified_three_originals.zip",workflow)
  self.assertIn("INDEPENDENT_SNAPSHOT_NOT_SAME_RACE",workflow)
  self.assertIn("P1_THREE_ORIGINAL_HANDOFF=SKIPPED_NO_INDEPENDENT_SNAPSHOT",workflow)
  self.assertIn("P1_THREE_ORIGINAL_HANDOFF=OFFLINE_CONTENT_VERIFIED_ONLY",workflow)
 def test_previous_three_day_archive_loss_is_removed(self):
  workflow=self.workflow()
  self.assertIn("retention-days: 30",workflow)
  self.assertNotIn("retention-days: 3\n",workflow)
  self.assertIn("if: always()",workflow)
 def test_manual_only_no_live_wager(self):
  workflow=self.workflow()
  self.assertIn("workflow_dispatch:",workflow)
  self.assertNotIn("schedule:",workflow)
  self.assertIn("ONE-SHOT-READ-ONLY",workflow)
  self.assertIn("contents: read",workflow)
  self.assertNotIn("wager",workflow.lower().replace("never submit wagers",""))

class PCOnlyPreviouslyAgreedRouteTests(unittest.TestCase):
 def spec(self,pc=None):
  from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec
  return ObservedRaceSpec("20261114",11,"2026-11-14_KYOTO_11R","京都",
       pc or "https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13",
       "", "2026-11-13T09:30:00Z")
 def test_single_observed_pc_link_can_be_used_without_sp_guess(self):
  spec=self.spec().validate(require_channels=("PC",))
  self.assertEqual(spec.sp_racecard_url,"")
  stub=StubOpener([(html(LINK),spec.pc_racecard_url),
                   (html("オッズは未発表"),"https://jra.jp/JRADB/accessO.html")])
  with tempfile.TemporaryDirectory() as d:
   result=capture(d,channel="PC",race_spec=spec,
      verified_start_utc="2026-11-14T06:45:00Z",
      active_runners=((1,1),(2,2)),opener=stub,
      now_utc="2026-11-13T10:00:00Z")
   self.assertEqual(result["state"],"OFFICIAL_NOT_PUBLISHED")
   self.assertEqual(len(stub.requests),2)
   self.assertFalse(result["pre_race_prices_accepted"])
 def test_hybrid_forbids_missing_sp_url_and_no_request(self):
  from diagnostics.jra_one_shot_market_capture import capture_hybrid
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(SourceChainError,"required_observed_racecard_url_missing"):
    capture_hybrid(d,primary_channel="PC",race_spec=self.spec(),
     verified_start_utc="2026-11-14T06:45:00Z",
     active_runners=((1,1),(2,2)))
 def test_single_sp_without_pc_remains_possible_if_sp_is_officially_observed(self):
  from dataclasses import replace
  sp="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261114%2FA0"
  obj=replace(self.spec(),pc_racecard_url="",sp_racecard_url=sp)
  self.assertEqual(obj.validate(require_channels=("SP",)).sp_racecard_url,sp)
  with self.assertRaisesRegex(SourceChainError,"required_observed_racecard_url_missing"):
   obj.validate()
 def test_unauthorized_pc_origin_not_accepted_as_optional_or_required(self):
  with self.assertRaisesRegex(SourceChainError,"unverified_official_racecard_url"):
   self.spec("https://jra.jp.evil.invalid/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13").validate(require_channels=("PC",))
 def test_no_empty_required_channels(self):
  with self.assertRaisesRegex(SourceChainError,"invalid_required_channels"):
   self.spec().validate(require_channels=())
 def test_manual_workflow_respects_pc_only_preflight(self):
  from pathlib import Path
  src=Path(".github/workflows/jra-observed-odds-manual-oneshot.yml").read_text(encoding="utf8")
  self.assertIn('channels=("PC","SP") if os.environ["HYBRID"]=="true" else (os.environ["OBSERVED_CHANNEL"],)',src)
  self.assertEqual(src.count("validate(require_channels=channels)"),2)

class EmptyAlternateSourceMustNeverVerifyRosterTests(unittest.TestCase):
 def test_empty_sp_source_does_not_certify_pc_only_roster(self):
  from diagnostics.jra_one_shot_market_capture import verified_roster_from_snapshot,ObservedRaceSpec
  obj=ObservedRaceSpec("20261114",11,"2026-11-14_KYOTO_11R","京都",
     "https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261114%2F13",
     "", "2026-11-13T09:30:00Z").validate(require_channels=("PC",))
  roster={"race_date":"2026-11-14","race_number":11,"venue":"京都",
      "source_url":"","source_sha256":"a"*64,"source_bytes":123,
      "fetched_at_utc":"2026-11-13T10:00:00Z",
      "runners":[{"horse_number":1,"frame_number":1,"horse_name":"A"},
                 {"horse_number":2,"frame_number":2,"horse_name":"B"}]}
  with self.assertRaisesRegex(SourceChainError,"roster_meeting_race_source_mismatch"):
   verified_roster_from_snapshot(roster,obj,race_start_utc="2026-11-14T06:45:00Z")
  roster["source_url"]=obj.pc_racecard_url
  self.assertEqual(verified_roster_from_snapshot(roster,obj,
      race_start_utc="2026-11-14T06:45:00Z"),((1,1),(2,2)))

if __name__=="__main__":unittest.main()
