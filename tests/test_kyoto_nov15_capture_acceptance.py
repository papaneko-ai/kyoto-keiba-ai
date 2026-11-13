"""Nov15 fail-closed capture acceptance: source only, no false-positive CI."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_nov15_capture_acceptance import assess_saved_capture,CaptureAcceptanceRejected

class CaptureAcceptTests(unittest.TestCase):
 def setUp(self):
    self.t=tempfile.TemporaryDirectory()
    self.addCleanup(self.t.cleanup)
    self.root=Path(self.t.name)
    names={"official_racecard.html":"racecard",
           "quinella_original.html":"quinella",
           "bracket_quinella_original.html":"bracket_quinella"}
    self.request=[]
    for i,(filename,step) in enumerate(names.items()):
        raw=("SYNTHETIC_OFFLINE_"+step).encode("ascii")
        (self.root/filename).write_bytes(raw)
        self.request.append({"step":step,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)})
    self.doc={"race_id":"2026-11-15_KYOTO_11R","state":"SOURCE_FROZEN",
              "pre_race_prices_accepted":True,"prediction_ready":False,"training_ready":False,
              "market_receipt":{"classification":"VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED"},
              "request_receipts":self.request}
    self.save()
 def save(self):
    (self.root/"receipt.json").write_text(json.dumps(self.doc))
 def check(self):
    return assess_saved_capture(self.root,expected_race_id="2026-11-15_KYOTO_11R")
 def test_all_three_sources_have_consistent_receipts(self):
    x=self.check()
    self.assertEqual(x["state"],"OFFLINE_SOURCE_BYTES_MATCH_RECEIPT")
    self.assertFalse(x["independent_official_source_authenticated"])
    self.assertFalse(x["prediction_ready"])
 def test_capture_blocked_cannot_be_ci_success(self):
    self.doc["state"]="CAPTURE_BLOCKED";self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"no_complete"):
        self.check()
 def test_unpublished_market_cannot_be_ci_success(self):
    self.doc["state"]="OFFICIAL_NOT_PUBLISHED";self.save()
    with self.assertRaises(CaptureAcceptanceRejected):self.check()
 def test_other_race_wrong_identity_rejected(self):
    self.doc["race_id"]="2026-11-14_KYOTO_11R";self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"race_identity"):
        self.check()
 def test_missing_bracket_original_rejected(self):
    (self.root/"bracket_quinella_original.html").unlink()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"original_missing"):
        self.check()
 def test_modified_quinella_bytes_rejected(self):
    (self.root/"quinella_original.html").write_bytes(b"FORGED")
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"sha_or_size"):
        self.check()
 def test_forged_receipt_sha_rejected(self):
    self.doc["request_receipts"][0]["sha256"]="0"*64;self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"sha_or_size"):
        self.check()
 def test_duplicate_receipt_step_rejected(self):
    self.doc["request_receipts"].append(copy.deepcopy(self.doc["request_receipts"][0]));self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"request_step_duplicate"):
        self.check()
 def test_claiming_production_readiness_rejected(self):
    self.doc["prediction_ready"]=True;self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"research_scope"):
        self.check()
 def test_missing_receipt_rejected(self):
    (self.root/"receipt.json").unlink()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"receipt_missing"):
        self.check()
 def test_tampered_byte_count_rejected(self):
    self.doc["request_receipts"][2]["bytes"]+=1;self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"sha_or_size"):
        self.check()
 def test_replay_determinism(self):
    self.assertEqual(self.check(),self.check())
if __name__=="__main__":
 unittest.main()
