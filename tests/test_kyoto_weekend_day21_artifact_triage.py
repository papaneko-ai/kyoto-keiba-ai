"""Triage authenticated artifact content, not merely workflow status."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import diagnostics.kyoto_nov15_encrypted_evidence as crypto
from diagnostics.kyoto_weekend_day21_artifact_triage import assess_lane

KEY="c"*64
REPO="papaneko-ai/kyoto-keiba-ai"
DAY="20261121"
RUN="4242"

class ActualEvidenceTriage(unittest.TestCase):
 def setUp(self):
    t=tempfile.TemporaryDirectory()
    self.addCleanup(t.cleanup)
    self.root=Path(t.name)
    self.source=self.root/"raw";self.source.mkdir()
    self.out=self.root/"sealed"
 def sealed(self,*,tamper=False,valid_postflight=True,both=False):
    raw=b"<html>offline mocked racecard</html>"
    name="official_sp_racecard.html"
    (self.source/name).write_bytes(raw)
    receipt={"day":DAY,"channel":"SP","state":"SP_ORIGINAL_CAPTURED_NOT_ROSTER_VERIFIED"}
    (self.source/"receipt.json").write_text(json.dumps(receipt))
    if both:
        (self.source/"official_sp_quinella_odds.html").write_bytes(b"mock odds A")
        (self.source/"official_sp_bracket_quinella_odds.html").write_bytes(b"mock odds B")
    if valid_postflight:
        rows=[{"filename":name,"sha256":("0"*64 if tamper else hashlib.sha256(raw).hexdigest()),
               "captured_at_utc":"2026-11-21T02:10:00+00:00"}]
        (self.source/"source_verification.json").write_text(json.dumps({
            "day":DAY,"channel":"SP","source_rows":rows}))
    with patch.object(crypto,"DAY",DAY):
        crypto.encrypt_evidence(self.source,self.out,key_hex=KEY,repo=REPO,run_id=RUN)
 def check(self,*,key=KEY):
    with patch.object(crypto,"DAY",DAY):
        return assess_lane(self.out,day=DAY,channel="SP",key=key,repo=REPO,run_id=RUN)
 def test_missing_artifact_is_not_success(self):
    r=self.check()
    self.assertEqual(r["state"],"NO_ARTIFACT")
    self.assertFalse(r["official_live_market_accepted"])
 def test_raw_source_postflight_integrity_not_predicted_market(self):
    self.sealed()
    r=self.check()
    self.assertTrue(r["ciphertext_authenticated"])
    self.assertTrue(r["source_original_sha_utc_checked"])
    self.assertEqual(r["state"],"VALID_ORIGINALS_WITH_INCOMPLETE_MARKETS")
    self.assertFalse(r["prediction_ready"])
 def test_both_market_raw_originals_still_not_authenticated_prediction(self):
    self.sealed(both=True)
    r=self.check()
    self.assertEqual(r["state"],"RAW_BOTH_MARKETS_PRESERVED_NOT_AUTHENTICATED")
    self.assertFalse(r["official_live_market_accepted"])
    self.assertFalse(r["prediction_ready"])
 def test_corrupted_source_sha_rejected(self):
    self.sealed(tamper=True)
    r=self.check()
    self.assertEqual(r["state"],"SOURCE_SHA_UTC_MISMATCH")
    self.assertFalse(r["source_original_sha_utc_checked"])
 def test_missing_postflight_not_silently_accepted(self):
    self.sealed(valid_postflight=False)
    self.assertEqual(self.check()["state"],"DECRYPTED_WITHOUT_POSTFLIGHT_RECORD")
 def test_wrong_key_rejected(self):
    self.sealed()
    r=self.check(key="d"*64)
    self.assertEqual(r["state"],"DECRYPT_OR_SOURCE_EVIDENCE_REJECTED")
 def test_truthful_pre_http_stop(self):
    self.out.mkdir()
    (self.out/"safe_stop.json").write_text(json.dumps({
        "race_day":DAY,"JRA_success":False,"state":"NO_CAPTURE_OR_PRE_HTTP_STOP"}))
    self.assertEqual(self.check()["state"],"PRE_HTTP_SAFE_STOP_NO_SOURCE")

if __name__=="__main__":
 unittest.main()
