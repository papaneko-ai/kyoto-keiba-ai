"""P8-03 integration from actual existing P1/P4/P5/P6 LAB parsers."""
import copy
import hashlib
import json
import unittest
from streamlit.testing.v1 import AppTest
from test_p4_source_bound_model_ev_research import SourceBoundMarketResearch
from diagnostics.p1_atomic_dual_market_handoff import package_prerace_market_capture
from diagnostics.p8_uploaded_archive_replay_lab import replay_user_supplied_lab_archive,IntegrationReplayRejected
from diagnostics.p6_final_html_settlement_lab import FinalResultRejected

class UploadedArchiveLabTests(unittest.TestCase):
 def setUp(self):
  self.fx=SourceBoundMarketResearch(methodName="test_both_markets_original_bound_same_model_comparison")
  self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  urls={"racecard":"https://jra.jp/JRADB/accessD.html",
        "pre_race_odds":"https://jra.jp/JRADB/accessO.html",
        "bracket_odds":"https://jra.jp/JRADB/accessO.html"}
  raw={s["kind"]:{"raw":(self.fx.fixture.root/s["path"]).read_bytes(),
       "captured_utc":s["captured_utc"],"observed_url":urls[s["kind"]]}
        for s in self.fx.fixture.manifest["sources"]}
  self.observed="2026-11-13T04:05:00Z"
  pkg=package_prerace_market_capture(raw_sources=raw,
      snapshot=copy.deepcopy(self.fx.fixture.snapshot),observed_utc=self.observed,channel="PC")
  self.original=pkg["archive_bytes"]
  self.input={"archive_bytes":self.original,
      "archive_sha256":hashlib.sha256(self.original).hexdigest(),
      "observed_utc":self.observed,"channel":"PC",
      "frozen_model":copy.deepcopy(self.fx.model),
      "commit_utc":"2026-11-13T04:07:00Z","ticket_type":"QUINELLA",
      "daily_budget_yen":1000}
  self.result=(b"<html><body>"+ "2026年11月14日 京都 1レース 払戻金 単勝 1 100 円 馬連 1-2 500 円 馬単 1-2 700 円 枠連 1-2 400 円 ワイド 1-2 200 円".encode("cp932")+b"</body></html>")
 def replay(self,**kw):
  args={**self.input,**kw}
  return replay_user_supplied_lab_archive(**args)
 def test_full_original_market_to_research_result(self):
  r=self.replay(final_result_bytes=self.result,final_result_utc="2026-11-14T05:10:00Z")
  self.assertEqual(r["selected_ticket_count"],1)
  self.assertEqual(r["research_stake_yen"],100)
  self.assertEqual(r["research_result"]["settled_fixture_payout_yen"],500)
  self.assertEqual(r["research_result"]["settled_fixture_profit_yen"],400)
  self.assertFalse(r["official_source_authenticated"])
  self.assertFalse(r["official_payout_authenticated"])
  self.assertFalse(r["actual_purchase_authorized"])
  self.assertEqual(r["network_requests"],0)
  self.assertEqual(r,self.replay(final_result_bytes=self.result,final_result_utc="2026-11-14T05:10:00Z"))
 def test_before_result_only_frozen_no_settlement(self):
  a=self.replay()
  self.assertIsNone(a["research_result"])
  self.assertEqual(a["selected_race_count"],1)
  self.assertFalse(a["real_paper_trade_verified"])
 def test_bracket_path_uses_bracket_market(self):
  r=self.replay(ticket_type="BRACKET",final_result_bytes=self.result,
                 final_result_utc="2026-11-14T05:10:00Z")
  self.assertEqual(r["ticket_type"],"BRACKET")
  self.assertEqual(r["research_result"]["settled_fixture_payout_yen"],400)
 def test_bad_zip_digest_refused(self):
  with self.assertRaises(IntegrationReplayRejected):
   self.replay(archive_sha256="0"*64)
 def test_corrupted_zip_bytes_refused(self):
  with self.assertRaises(ValueError):
   self.replay(archive_bytes=self.original+b"forgery",
               archive_sha256=hashlib.sha256(self.original+b"forgery").hexdigest())
 def test_untrusted_model_origin_never_promoted(self):
  m=copy.deepcopy(self.fx.model);m["provenance"]="OFFICIAL_LIVE"
  with self.assertRaises(ValueError):self.replay(frozen_model=m)
 def test_changed_model_frozen_time_rejected(self):
  m=copy.deepcopy(self.fx.model);m["frozen_utc"]="2026-11-14T05:00:00Z"
  with self.assertRaises(ValueError):self.replay(frozen_model=m)
 def test_result_without_time_rejected(self):
  with self.assertRaisesRegex(IntegrationReplayRejected,"result_bytes_and_time_must_be_together"):
   self.replay(final_result_bytes=self.result)
 def test_wrong_result_day_rejected(self):
  payload=self.result.replace("2026年11月14日".encode("cp932"),"2026年11月15日".encode("cp932"))
  with self.assertRaises(FinalResultRejected):
   self.replay(final_result_bytes=payload,final_result_utc="2026-11-14T05:10:00Z")
 def test_post_cutoff_freeze_rejected(self):
  with self.assertRaises(ValueError):
   self.replay(commit_utc="2026-11-14T05:00:00Z")
 def test_zero_budget_skip_no_orders(self):
  r=self.replay(daily_budget_yen=0)
  self.assertEqual(r["selected_ticket_count"],0)
  self.assertEqual(r["research_stake_yen"],0)
  self.assertFalse(r["actual_purchase_authorized"])
 def test_shadow_app_no_upload_safe(self):
  from pathlib import Path
  app=Path(__file__).resolve().parents[1]/"diagnostics/p8_uploaded_archive_shadow_app.py"
  out=AppTest.from_file(str(app),default_timeout=20).run()
  self.assertFalse(out.exception)
  self.assertTrue(len(out.warning)>=1)
  self.assertTrue(out.button[0].disabled)
  self.assertEqual(len(out.file_uploader),3)
 def test_shadow_app_has_no_network_or_order_paths(self):
  from pathlib import Path
  app=Path(__file__).resolve().parents[1]/"diagnostics/p8_uploaded_archive_shadow_app.py"
  src=app.read_text()
  self.assertNotIn("requests.get",src)
  self.assertNotIn("turso",src.lower())
  self.assertNotIn("place_bet",src)
  self.assertNotIn("submit_order",src)
if __name__=="__main__":unittest.main()
