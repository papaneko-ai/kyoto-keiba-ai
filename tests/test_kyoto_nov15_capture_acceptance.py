"""Nov15 fail-closed capture acceptance: source only, no false-positive CI."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_nov15_capture_acceptance import assess_saved_capture,assess_saved_hybrid_capture,CaptureAcceptanceRejected
from unittest.mock import patch

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
        self.request.append({"step":step,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
            "captured_at_utc":"2026-11-15T04:05:00+00:00",
            "http_status":200,"method":"POST","requested_url":"https://jra.jp/JRADB/accessO.html",
            "response_url":"https://jra.jp/JRADB/accessO.html"})
    self.doc={"race_id":"2026-11-15_KYOTO_11R","state":"SOURCE_FROZEN",
              "schema_version":"jra_one_shot_market_capture.v1","channel":"PC",
              "started_at_utc":"2026-11-15T04:00:00+00:00",
              "ended_at_utc":"2026-11-15T04:06:00+00:00",
              "verified_start_utc":"2026-11-15T06:40:00+00:00",
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
 def test_market_captured_after_start_refused(self):
    self.doc["request_receipts"][1]["captured_at_utc"]="2026-11-15T06:35:00Z"
    self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"capture_market_not_prerace"):
        self.check()
 def test_missing_capture_time_refused(self):
    del self.doc["request_receipts"][0]["captured_at_utc"];self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"capture_utc_invalid"):
        self.check()
 def test_capture_ended_after_cutoff_refused(self):
    self.doc["ended_at_utc"]="2026-11-15T06:39:00Z";self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"capture_run_not_prerace"):
        self.check()
 def test_local_timezone_not_accepted_as_utc(self):
    self.doc["request_receipts"][0]["captured_at_utc"]="2026-11-15T13:05:00+09:00";self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"capture_utc_invalid"):
        self.check()
 def test_changed_race_start_day_refused(self):
    self.doc["verified_start_utc"]="2026-11-16T06:40:00Z";self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"capture_run_not_prerace"):
        self.check()
 def test_http_provenance_missing_refused(self):
    self.doc["request_receipts"][0]["http_status"]=404;self.save()
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"capture_http_provenance_incomplete"):
        self.check()
 def test_valid_time_receipt_is_returned(self):
    self.assertEqual(self.check()["time_receipt"]["verified_race_start_utc"],
                     "2026-11-15T06:40:00+00:00")

class HybridCaptureHandoffTests(unittest.TestCase):
 def setUp(self):
    temp=tempfile.TemporaryDirectory()
    self.addCleanup(temp.cleanup)
    self.root=Path(temp.name)
    self.race="2026-11-15_KYOTO_11R"
 def save(self,selected,attempts,**changes):
    doc={"schema":"jra_pc_sp_one_shot_failover.v1",
         "race_id":self.race,"selected_channel":selected,
         "state":"SOURCE_ONLY_FALLBACK" if selected=="SP" else "SOURCE_ONLY_PRIMARY",
         "attempts":attempts}
    doc.update(changes)
    (self.root/"hybrid_receipt.json").write_text(json.dumps(doc))
 def attempt(self,channel,accepted=False):
    return {"channel":channel,"accepted":accepted,
            "state":"SOURCE_FROZEN" if accepted else "CAPTURE_BLOCKED"}
 def check(self):
    return assess_saved_hybrid_capture(self.root,expected_race_id=self.race)
 def test_pc_selected_calls_existing_original_gate(self):
    self.save("PC",[self.attempt("PC",True)])
    with patch("diagnostics.kyoto_nov15_capture_acceptance.assess_saved_capture",
               return_value={"state":"OFFLINE_SOURCE_BYTES_MATCH_RECEIPT"}) as gate:
        r=self.check()
    gate.assert_called_once_with(self.root/"pc",expected_race_id=self.race)
    self.assertEqual(r["selected_channel"],"PC")
    self.assertFalse(r["independent_official_source_authenticated"])
 def test_sp_fallback_calls_existing_original_gate(self):
    self.save("SP",[self.attempt("PC"),self.attempt("SP",True)])
    with patch("diagnostics.kyoto_nov15_capture_acceptance.assess_saved_capture",
               return_value={"state":"OFFLINE_SOURCE_BYTES_MATCH_RECEIPT"}) as gate:
        r=self.check()
    gate.assert_called_once_with(self.root/"sp",expected_race_id=self.race)
    self.assertEqual(r["selected_channel"],"SP")
    self.assertFalse(r["market_value_parity_verified"])
 def test_both_failed_never_release(self):
    self.save(None,[self.attempt("PC"),self.attempt("SP")],state="SAFE_STOP")
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"hybrid_no_valid_selected_channel"):
        self.check()
 def test_mismatched_selected_state_rejected(self):
    self.save("SP",[self.attempt("PC"),self.attempt("SP")])
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"hybrid_selected_source_not_frozen"):
        self.check()
 def test_forged_race_id_rejected(self):
    self.save("PC",[self.attempt("PC",True)],race_id="2026-11-14_KYOTO_11R")
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"hybrid_race_identity_conflict"):
        self.check()
 def test_duplicate_channel_attempt_rejected(self):
    self.save("PC",[self.attempt("PC",True),self.attempt("PC",True)])
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"hybrid_no_valid_selected_channel"):
        self.check()
 def test_selected_source_without_original_receipt_is_not_success(self):
    self.save("SP",[self.attempt("PC"),self.attempt("SP",True)])
    with self.assertRaisesRegex(CaptureAcceptanceRejected,"capture_folder_invalid"):
        self.check()

if __name__=="__main__":
 unittest.main()
