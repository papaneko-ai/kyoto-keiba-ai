import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from test_p1_three_original_content_binding import StrictThreeOriginalContentTests,NOW
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
  a["pre_race_odds"]["raw"]+=b" final "
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
if __name__=="__main__":unittest.main()
