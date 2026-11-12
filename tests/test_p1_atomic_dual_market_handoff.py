import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from test_p1_three_original_content_binding import StrictThreeOriginalContentTests
NOW='2026-11-13T04:05:00Z'
from diagnostics.p1_atomic_dual_market_handoff import (
  package_prerace_market_capture,verify_prerace_handoff_archive,
  save_immutable_archive,MarketHandoffRejected
)

class AtomicThreeMarketTests(unittest.TestCase):
 def setUp(self):
  self.fx=StrictThreeOriginalContentTests(methodName="test_all_three_originals_match")
  self.fx.setUp()
  self.addCleanup(self.fx.doCleanups)
 def captures(self):
  urls={"racecard":"https://jra.jp/JRADB/accessD.html",
        "pre_race_odds":"https://jra.jp/JRADB/accessO.html",
        "bracket_odds":"https://jra.jp/JRADB/accessO.html"}
  return {s["kind"]:{"raw":(self.fx.root/s["path"]).read_bytes(),
         "captured_utc":s["captured_utc"],"observed_url":urls[s["kind"]]}
          for s in self.fx.manifest["sources"]}
 def make(self,**kw):
  opts={"raw_sources":self.captures(),"snapshot":copy.deepcopy(self.fx.snapshot),
        "observed_utc":NOW,"channel":"PC"}
  opts.update(kw)
  return package_prerace_market_capture(**opts)
 def test_all_three_bytes_replay_and_no_fake_official_verification(self):
  v=self.make()
  digest=hashlib.sha256(v["archive_bytes"]).hexdigest()
  r=verify_prerace_handoff_archive(v["archive_bytes"],
       expected_sha256=digest,observed_utc=NOW,channel="PC")
  self.assertTrue(r["all_three_content_verified"])
  self.assertFalse(v["receipt"]["official_origin_authenticated"])
  self.assertFalse(v["receipt"]["prediction_ready"])
  self.assertEqual(v,self.make())
 def test_single_file_exclusive_save_and_restart(self):
  v=self.make()
  f=self.fx.root/"immutable.zip"
  sha=save_immutable_archive(f,v["archive_bytes"])
  self.assertEqual(verify_prerace_handoff_archive(f.read_bytes(),
       expected_sha256=sha,observed_utc=NOW,channel="PC")["archive_sha256"],sha)
  before=f.read_bytes()
  with self.assertRaisesRegex(MarketHandoffRejected,"archive_already_exists"):
   save_immutable_archive(f,b"new")
  self.assertEqual(f.read_bytes(),before)
 def test_missing_bracket_original_is_blocked(self):
  a=self.captures();a.pop("bracket_odds")
  with self.assertRaisesRegex(MarketHandoffRejected,"three_independent_sources_required"):
   self.make(raw_sources=a)
 def test_forged_bracket_price_fails_original_comparison(self):
  s=copy.deepcopy(self.fx.snapshot);s["bracket_odds"][0]["decimal"]=99.
  with self.assertRaisesRegex(MarketHandoffRejected,"strict_three_original_content_rejected"):
   self.make(snapshot=s)
 def test_forged_quinella_price_fails_original_comparison(self):
  s=copy.deepcopy(self.fx.snapshot);s["odds"][0]["decimal"]=99.
  with self.assertRaises(MarketHandoffRejected):
   self.make(snapshot=s)
 def test_unauthenticated_claim_cannot_override_receipt(self):
  s=copy.deepcopy(self.fx.snapshot)
  s["official_origin_authenticated"]=True
  a=self.make(snapshot=s)
  self.assertFalse(a["receipt"]["official_origin_authenticated"])
  self.assertFalse(a["receipt"]["prediction_ready"])
 def test_historical_final_is_not_prerace_market(self):
  a=self.captures()
  a["pre_race_odds"]["raw"]=a["pre_race_odds"]["raw"].replace(b"<body>",b"<body>"+ "最終オッズ".encode("cp932"))
  with self.assertRaises(MarketHandoffRejected):self.make(raw_sources=a)
 def test_expired_market_capture_rejected(self):
  a=self.captures();a["bracket_odds"]["captured_utc"]="2026-11-13T03:00:00Z"
  with self.assertRaisesRegex(MarketHandoffRejected,"market_capture_stale"):
   self.make(raw_sources=a)
 def test_future_time_rejected(self):
  a=self.captures();a["bracket_odds"]["captured_utc"]="2026-11-14T08:00:00Z"
  with self.assertRaisesRegex(MarketHandoffRejected,"post_cutoff_or_future_capture"):
   self.make(raw_sources=a)
 def test_unknown_host_rejected(self):
  a=self.captures();a["racecard"]["observed_url"]="https://evil.example"
  with self.assertRaisesRegex(MarketHandoffRejected,"claimed_original_url_invalid"):
   self.make(raw_sources=a)
 def test_both_markets_must_be_open(self):
  s=copy.deepcopy(self.fx.snapshot);s["market_states"]["bracket"]["sales"]="SUSPENDED"
  with self.assertRaises(MarketHandoffRejected):self.make(snapshot=s)
 def test_file_digest_mismatch_detected(self):
  v=self.make()
  with self.assertRaisesRegex(MarketHandoffRejected,"independent_archive_sha_required"):
   verify_prerace_handoff_archive(v["archive_bytes"],expected_sha256="0"*64,
                                   observed_utc=NOW,channel="PC")
 def test_tampered_archive_receipt_cannot_claim_real_trading(self):
  v=self.make()
  with zipfile.ZipFile(io.BytesIO(v["archive_bytes"])) as z:
   items={n:z.read(n) for n in z.namelist()}
  receipt=json.loads(items["handoff_receipt.json"])
  receipt["official_origin_authenticated"]=True
  items["handoff_receipt.json"]=json.dumps(receipt).encode()
  out=io.BytesIO()
  with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_STORED) as z:
   for k,val in items.items():z.writestr(k,val)
  payload=out.getvalue()
  with self.assertRaisesRegex(MarketHandoffRejected,"archive_verification_failed"):
   verify_prerace_handoff_archive(payload,expected_sha256=hashlib.sha256(payload).hexdigest(),
                                 observed_utc=NOW,channel="PC")
 def test_wrong_channel_replay_rejected(self):
  v=self.make()
  digest=hashlib.sha256(v["archive_bytes"]).hexdigest()
  with self.assertRaises(MarketHandoffRejected):
   verify_prerace_handoff_archive(v["archive_bytes"],expected_sha256=digest,
                                 observed_utc=NOW,channel="SP")
 def test_no_real_authorization_even_if_operator_says_official(self):
  v=self.make()
  self.assertFalse(v["receipt"]["paper_trade_ready"])
  self.assertFalse(v["receipt"]["official_sales_authenticated"])
  self.assertFalse(v["receipt"]["official_scratches_authenticated"])
  self.assertEqual(v["receipt"]["network_requests"],0)

class ExistingCaptureToAtomicThreeOriginalTests(AtomicThreeMarketTests):
 def stage(self, *, state="SOURCE_FROZEN", wrong_sha=False, wrong_token=False):
  from urllib.parse import urlencode
  root=self.fx.root/"captured-current"
  root.mkdir()
  names={"racecard":"official_racecard.html",
         "pre_race_odds":"quinella_original.html",
         "bracket_odds":"bracket_quinella_original.html"}
  steps={"racecard":"racecard","pre_race_odds":"quinella",
         "bracket_odds":"bracket_quinella"}
  entries=[]
  for kind,item in self.captures().items():
   raw=item["raw"];(root/names[kind]).write_bytes(raw)
   url=item["observed_url"]
   observed_tokens={"pre_race_odds":"pw154ou1008202604100120261114Z/BB",
                    "bracket_odds":"pw153ou1008202604100120261114Z/37"}
   token=None if kind=="racecard" else ("pw15wrong/XX" if wrong_token and kind=="bracket_odds" else observed_tokens[kind])
   if kind=="racecard":
    url="https://jra.jp/JRADB/accessD.html?CNAME=pw01/AA"
   body=None if token is None else urlencode({"cname":token}).encode("ascii")
   entries.append({"step":steps[kind],"method":"GET" if token is None else "POST",
     "sha256":("0"*64 if wrong_sha and kind=="racecard" else hashlib.sha256(raw).hexdigest()),
     "bytes":len(raw),"captured_at_utc":item["captured_utc"],
     "requested_url":url,"response_url":url,
     "observed_action_token":token,
     "post_body_sha256":None if body is None else hashlib.sha256(body).hexdigest(),
     "post_body_size":0 if body is None else len(body)})
  odds_menu=('''<html><title>単勝・複勝オッズ JRA</title><body>
  <a onclick="return doAction('/JRADB/accessO.html', 'pw154ou1008202604100120261114Z/BB');">馬連</a>
  <a onclick="return doAction('/JRADB/accessO.html', 'pw153ou1008202604100120261114Z/37');">枠連</a>
  </body></html>''').encode("cp932")
  (root/"official_odds_menu.html").write_bytes(odds_menu)
  entries.insert(1,{"step":"odds_menu","method":"POST",
    "sha256":hashlib.sha256(odds_menu).hexdigest(),"bytes":len(odds_menu),
    "captured_at_utc":self.fx.manifest["sources"][1]["captured_utc"],
    "requested_url":"https://jra.jp/JRADB/accessO.html",
    "response_url":"https://jra.jp/JRADB/accessO.html",
    "observed_action_token":"pw15menu/AA",
    "post_body_sha256":hashlib.sha256(b"cname=pw15menu%2FAA").hexdigest(),
    "post_body_size":len(b"cname=pw15menu%2FAA")})
  info={"state":state,"pre_race_prices_accepted":state=="SOURCE_FROZEN",
        "channel":"PC",
        "race_id":f"{self.fx.snapshot['meeting_date']}_KYOTO_{self.fx.snapshot['race']:02d}R",
        "request_receipts":entries}
  (root/"receipt.json").write_text(json.dumps(info),encoding="utf8")
  return root
 def test_saved_real_capture_receipts_reuse_canonical_atomic_handoff(self):
  from diagnostics.p1_atomic_dual_market_handoff import package_saved_observed_market_capture
  staged=self.stage()
  v=package_saved_observed_market_capture(capture_directory=staged,
      snapshot=self.fx.snapshot,observed_utc=NOW)
  digest=hashlib.sha256(v["archive_bytes"]).hexdigest()
  self.assertTrue(verify_prerace_handoff_archive(v["archive_bytes"],
      expected_sha256=digest,observed_utc=NOW,channel="PC")["all_three_content_verified"])
  self.assertEqual(v["capture_receipt_sha256"],
       hashlib.sha256((staged/"receipt.json").read_bytes()).hexdigest())
  self.assertFalse(v["receipt"]["prediction_ready"])
 def test_forged_market_post_token_detected_against_saved_menu(self):
  from diagnostics.p1_atomic_dual_market_handoff import package_saved_observed_market_capture
  staged=self.stage(wrong_token=True)
  with self.assertRaisesRegex(MarketHandoffRejected,"observed_market_action_not_in_saved_menu"):
   package_saved_observed_market_capture(capture_directory=staged,
      snapshot=self.fx.snapshot,observed_utc=NOW)
 def test_saved_menu_digest_tampering_detected(self):
  from diagnostics.p1_atomic_dual_market_handoff import package_saved_observed_market_capture
  staged=self.stage()
  with (staged/"official_odds_menu.html").open("ab") as o:o.write(b"forged")
  with self.assertRaisesRegex(MarketHandoffRejected,"observed_market_menu_digest_mismatch"):
   package_saved_observed_market_capture(capture_directory=staged,
      snapshot=self.fx.snapshot,observed_utc=NOW)
 def test_original_sha_mismatch_rejected_before_canonical_packaging(self):
  from diagnostics.p1_atomic_dual_market_handoff import package_saved_observed_market_capture
  staged=self.stage(wrong_sha=True)
  with self.assertRaisesRegex(MarketHandoffRejected,"capture_receipt_original_hash_conflict"):
   package_saved_observed_market_capture(capture_directory=staged,
      snapshot=self.fx.snapshot,observed_utc=NOW)
 def test_not_frozen_never_released(self):
  from diagnostics.p1_atomic_dual_market_handoff import package_saved_observed_market_capture
  staged=self.stage(state="CAPTURE_BLOCKED")
  with self.assertRaisesRegex(MarketHandoffRejected,"original_capture_not_frozen"):
   package_saved_observed_market_capture(capture_directory=staged,
      snapshot=self.fx.snapshot,observed_utc=NOW)
 def test_response_url_redirection_rejected(self):
  from diagnostics.p1_atomic_dual_market_handoff import package_saved_observed_market_capture
  staged=self.stage()
  p=staged/"receipt.json"
  receipt=json.loads(p.read_text())
  receipt["request_receipts"][2]["response_url"]="https://evil.invalid"
  p.write_text(json.dumps(receipt),encoding="utf8")
  with self.assertRaisesRegex(MarketHandoffRejected,"redirect_or_missing_url_receipt"):
   package_saved_observed_market_capture(capture_directory=staged,
      snapshot=self.fx.snapshot,observed_utc=NOW)
 def test_operator_cli_replays_immutable_originals_without_network(self):
  from diagnostics.p1_atomic_dual_market_handoff import main
  captured=self.stage()
  snapshot=self.fx.root/"operator_snapshot.json"
  snapshot.write_text(json.dumps(self.fx.snapshot),encoding="utf8")
  output=self.fx.root/"operator_archive.zip"
  receipt=main(["--capture-directory",str(captured),"--snapshot",str(snapshot),
                "--observed-utc",NOW,"--output-archive",str(output)])
  self.assertTrue(output.exists())
  self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),receipt["archive_sha256"])
  self.assertFalse(receipt["prediction_ready"])
  self.assertEqual(receipt["network_requests"],0)
  before=output.read_bytes()
  with self.assertRaisesRegex(MarketHandoffRejected,"immutable_archive_must_be_new"):
   main(["--capture-directory",str(captured),"--snapshot",str(snapshot),
         "--observed-utc",NOW,"--output-archive",str(output)])
  self.assertEqual(output.read_bytes(),before)
 def test_official_menu_redirect_rejected(self):
  from diagnostics.p1_atomic_dual_market_handoff import package_saved_observed_market_capture
  staged=self.stage()
  p=staged/"receipt.json"
  receipt=json.loads(p.read_text())
  receipt["request_receipts"][1]["response_url"]="https://evil.invalid/JRADB/accessO.html"
  p.write_text(json.dumps(receipt),encoding="utf8")
  with self.assertRaisesRegex(MarketHandoffRejected,"observed_menu_redirect_or_wrong_host"):
   package_saved_observed_market_capture(capture_directory=staged,
      snapshot=self.fx.snapshot,observed_utc=NOW)
 def test_market_capture_time_conflict_rejected_by_existing_validator(self):
  from diagnostics.p1_atomic_dual_market_handoff import package_saved_observed_market_capture
  staged=self.stage()
  p=staged/"receipt.json"
  receipt=json.loads(p.read_text())
  receipt["request_receipts"][-1]["captured_at_utc"]="2026-11-14T08:00:00Z"
  p.write_text(json.dumps(receipt),encoding="utf8")
  with self.assertRaisesRegex(MarketHandoffRejected,"post_cutoff_or_future_capture"):
   package_saved_observed_market_capture(capture_directory=staged,
      snapshot=self.fx.snapshot,observed_utc=NOW)

if __name__=="__main__":unittest.main()
