"""Operator handoff regression on the existing real parser fixture family."""
import copy,hashlib,json
from pathlib import Path
from test_p1_three_original_content_binding import StrictThreeOriginalContentTests,NOW,market_html
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.p1_operator_original_handoff import assess_originals,main,HandoffRejected
from diagnostics.p1_three_original_dual_intake import ThreeOriginalRejected

class OperatorHandoffTests(StrictThreeOriginalContentTests):
 def test_real_parser_handoff_counts_and_blocks_live_credit(self):
  raw=export_bundle(self.manifest,self.root,observed_utc=NOW)
  result=assess_originals(raw,self.snapshot,observed_utc=NOW,channel="PC")
  self.assertEqual(result["roster_count"],2)
  self.assertEqual(result["quinella_pair_count"],1)
  self.assertEqual(result["bracket_pair_count"],3)
  self.assertEqual(result["bundle_sha256"],hashlib.sha256(raw).hexdigest())
  self.assertFalse(result["real_operational_score_eligible"])
  self.assertFalse(result["prediction_ready"])
  self.assertFalse(result["official_origin_authenticated"])
  self.assertEqual(result["network_requests"],0)
  self.assertEqual(len(result["remaining_requirements"]),4)
 def test_cli_file_to_receipt_and_exclusive_write(self):
  b=self.root/"bundle.zip";b.write_bytes(export_bundle(self.manifest,self.root,observed_utc=NOW))
  s=self.root/"snapshot.json";s.write_text(json.dumps(self.snapshot),encoding="utf-8")
  out=self.root/"operator-receipt.json"
  args=["--bundle",str(b),"--snapshot",str(s),"--observed-utc",NOW,"--channel","PC","--out",str(out)]
  x=main(args)
  self.assertEqual(json.loads(out.read_text(encoding="utf-8")),x)
  with self.assertRaisesRegex(HandoffRejected,"immutable_output_already_exists"):main(args)
 def test_reject_overwrite_input(self):
  b=self.root/"bundle.zip";b.write_bytes(export_bundle(self.manifest,self.root,observed_utc=NOW))
  s=self.root/"snapshot.json";s.write_text(json.dumps(self.snapshot),encoding="utf-8")
  with self.assertRaisesRegex(HandoffRejected,"cannot_overwrite_original_inputs"):
   main(["--bundle",str(b),"--snapshot",str(s),"--observed-utc",NOW,"--channel","PC","--out",str(b)])
 def test_fake_market_does_not_write(self):
  b=self.root/"bundle.zip";b.write_bytes(export_bundle(self.manifest,self.root,observed_utc=NOW))
  s=self.root/"snapshot.json";bad=copy.deepcopy(self.snapshot);bad["odds"][0]["decimal"]=99
  s.write_text(json.dumps(bad),encoding="utf-8")
  out=self.root/"blocked.json"
  with self.assertRaisesRegex(ThreeOriginalRejected,"odds_original_prices_disagree"):
   main(["--bundle",str(b),"--snapshot",str(s),"--observed-utc",NOW,"--channel","PC","--out",str(out)])
  self.assertFalse(out.exists())
 def test_final_market_rejected(self):
  self.set_original(1,market_html("馬連オッズ","umaren",["1 2 3.1"],final=True))
  with self.assertRaisesRegex(ThreeOriginalRejected,"historical_final_forbidden"):
   assess_originals(export_bundle(self.manifest,self.root,observed_utc=NOW),self.snapshot,observed_utc=NOW,channel="PC")
