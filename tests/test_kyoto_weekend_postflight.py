"""Offline source and timestamp integrity accept/reject fixtures."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_postflight import check_originals

class PostflightTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.day="20261121"

    def test_sp_original_hash_and_utc_accepted_without_market_claim(self):
        raw=b"<html>fixture</html>"
        (self.root/"official_sp_racecard.html").write_bytes(raw)
        (self.root/"sp_receipt.json").write_text(json.dumps({
            "day":self.day,"channel":"SP","racecard_sha256":hashlib.sha256(raw).hexdigest(),
            "racecard_captured_at_utc":"2026-11-21T02:00:00+00:00"}))
        result=check_originals(self.root,day=self.day,channel="SP")
        self.assertTrue(result["source_verified"])
        self.assertFalse(result["prediction_ready"])
        self.assertFalse(result["both_markets_verified"])

    def test_sp_changed_original_rejected(self):
        (self.root/"official_sp_racecard.html").write_bytes(b"mutated")
        (self.root/"sp_receipt.json").write_text(json.dumps({
            "day":self.day,"channel":"SP","racecard_sha256":"0"*64,
            "racecard_captured_at_utc":"2026-11-21T02:00:00+00:00"}))
        result=check_originals(self.root,day=self.day,channel="SP")
        self.assertEqual(result["state"],"SP_PROVENANCE_REJECTED")

    def test_sp_non_utc_rejected(self):
        raw=b"fixture"
        (self.root/"official_sp_racecard.html").write_bytes(raw)
        (self.root/"sp_receipt.json").write_text(json.dumps({
            "day":self.day,"channel":"SP","racecard_sha256":hashlib.sha256(raw).hexdigest(),
            "racecard_captured_at_utc":"2026-11-21T11:00:00+09:00"}))
        self.assertFalse(check_originals(self.root,day=self.day,channel="SP")["source_verified"])

    def test_sp_discovery_hash_tamper_rejected(self):
        raw=b"<html>offline SP homepage</html>"
        (self.root/"official_sp_discovery_1.html").write_bytes(raw)
        (self.root/"sp_discovery_receipt.json").write_text(json.dumps({
            "day":self.day,"not_pc_derived":True,
            "attempts":[{"file":"official_sp_discovery_1.html",
                         "sha256":"0"*64,
                         "captured_at_utc":"2026-11-21T02:00:00Z"}]}))
        self.assertEqual(check_originals(self.root,day=self.day,channel="SP")["state"],
                         "SP_PROVENANCE_REJECTED")

    def test_sp_discovery_sha_and_utc_verified(self):
        raw=b"<html>offline SP homepage</html>"
        (self.root/"official_sp_discovery_1.html").write_bytes(raw)
        (self.root/"sp_discovery_receipt.json").write_text(json.dumps({
            "day":self.day,"not_pc_derived":True,
            "attempts":[{"file":"official_sp_discovery_1.html",
                         "sha256":hashlib.sha256(raw).hexdigest(),
                         "captured_at_utc":"2026-11-21T02:00:00Z"}]}))
        r=check_originals(self.root,day=self.day,channel="SP")
        self.assertTrue(r["source_verified"])
        self.assertFalse(r["racecard_start_time_verified"])

    def test_pc_missing_and_false_receipt_rejected(self):
        self.assertEqual(check_originals(self.root,day=self.day,channel="PC")["state"],
                         "RECEIPT_MISSING")
        (self.root/"receipt.json").write_text('{"day":"20261122"}')
        self.assertEqual(check_originals(self.root,day=self.day,channel="PC")["state"],
                         "PC_PROVENANCE_REJECTED")

    def test_pc_authenticated_observer_still_not_prediction(self):
        (self.root/"receipt.json").write_text('{"day":"20261121"}')
        with patch("diagnostics.kyoto_nov15_two_original_observer.accept_observation",
                   return_value={"state":"TWO_ORIGINALS_MATCH_RECEIPT_ONLY"}):
            r=check_originals(self.root,day=self.day,channel="PC")
        self.assertTrue(r["source_verified"])
        self.assertFalse(r["prediction_ready"])

if __name__=="__main__":
    unittest.main()
