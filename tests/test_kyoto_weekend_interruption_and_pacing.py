"""Destructive no-JRA-HTTP tests for the two newly repaired incident roots."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from diagnostics.kyoto_weekend_capture import seal, capture
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence

class InterruptionAndPacingTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        p=patch.dict(os.environ,{"KYOTO_TARGET_DAY":"20261121"},clear=False)
        p.start()
        self.addCleanup(p.stop)

    def recover(self, source):
        dest=self.root/"sealed"
        key="ab"*32
        seal("20261121",str(source),str(dest),key=key,
             repo="papaneko-ai/kyoto-keiba-ai",run_id="123")
        decoded=self.root/"decoded"
        check=decrypt_evidence(dest,decoded,key_hex=key,
                               repo="papaneko-ai/kyoto-keiba-ai",run_id="123")
        self.assertTrue(check["authentication_tag_verified"])
        self.assertFalse(source.exists())
        return decoded

    def test_interrupted_pc_nested_raw_without_any_receipt_survives(self):
        source=self.root/"source"
        nested=source/"pc_originals"
        nested.mkdir(parents=True)
        (nested/"official_selection.html").write_bytes(b"captured but interrupted")
        d=self.recover(source)
        self.assertEqual((d/"official_selection.html").read_bytes(),b"captured but interrupted")
        receipt=json.loads((d/"receipt.json").read_text())
        self.assertEqual(receipt["actual_http_attempts"],"UNKNOWN")
        self.assertFalse(receipt["prediction_ready"])
        self.assertEqual(receipt["state"],"PARTIAL_OR_INTERRUPTED_CAPTURE_UNAUTHENTICATED")
        self.assertIn("official_selection.html",receipt["original_files_observed"])

    def test_nested_observer_receipt_is_preserved_not_overwritten(self):
        source=self.root/"source"
        nested=source/"pc_originals"
        nested.mkdir(parents=True)
        (nested/"receipt.json").write_bytes(b'{"in_progress":true}')
        (nested/"official_meeting.html").write_bytes(b"first bytes")
        (source/"receipt.json").write_text('{"state":"PC_CAPTURE_EXCEPTION"}')
        d=self.recover(source)
        self.assertEqual((d/"observer_partial_receipt.json").read_bytes(),b'{"in_progress":true}')
        self.assertEqual((d/"receipt.json").read_text(),'{"state":"PC_CAPTURE_EXCEPTION"}')
        self.assertEqual((d/"official_meeting.html").read_bytes(),b"first bytes")

    def test_sp_partial_original_without_receipt_is_kept_encrypted(self):
        source=self.root/"source"
        source.mkdir()
        (source/"official_sp_discovery_1.html").write_bytes(b"official-like mock")
        d=self.recover(source)
        self.assertEqual((d/"official_sp_discovery_1.html").read_bytes(),b"official-like mock")
        self.assertFalse(json.loads((d/"receipt.json").read_text())["source_verified"])

    def test_unknown_files_fail_closed_no_plaintext_upload(self):
        source=self.root/"source"
        source.mkdir()
        (source/"unknown_secret.txt").write_bytes(b"private")
        with self.assertRaises(Exception):
            self.recover(source)
        self.assertTrue(source.exists())
        self.assertFalse((self.root/"sealed"/"originals.tar.gz.aesgcm").exists())

    def test_known_sp_url_receives_shared_pacer(self):
        seen=[]
        def capture_sp(root,*,pacer,**kwargs):
            seen.append(pacer)
            (Path(root)/"sp_receipt.json").write_text('{"day":"20261121"}')
            return {"state":"SP_ORIGINAL_CAPTURED_NOT_ROSTER_VERIFIED",
                    "network_requests_started":1,"racecard_sha256":"ab"}
        with patch("diagnostics.kyoto_sp_observed_source.capture_verified_sp_seed",side_effect=capture_sp):
            result=capture("20261121","SP",str(self.root/"sp"),live=False,
                           opener=object(),sp_source_url="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race1220261121%2FBB")
        self.assertEqual(len(seen),1)
        self.assertTrue(callable(seen[0].before_request))
        self.assertEqual(result["observed_http_requests_started"],1)

    def test_official_discovery_and_racecard_share_same_pacer(self):
        observed=[]
        def discovery(root,*,pacer,**kwargs):
            observed.append(pacer)
            Path(root).mkdir()
            (Path(root)/"sp_discovery_receipt.json").write_text('{"day":"20261121"}')
            return {"state":"OBSERVED_UNIQUE_R12_SOURCE","network_requests_started":1,
                    "racecard_url":"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race1220261121%2FBB"}
        def capture_sp(root,*,pacer,**kwargs):
            observed.append(pacer)
            (Path(root)/"sp_receipt.json").write_text('{"day":"20261121"}')
            return {"state":"SP_ORIGINAL_CAPTURED_NOT_ROSTER_VERIFIED",
                    "network_requests_started":1,"racecard_sha256":"ab"}
        with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"schedule",
                   "GITHUB_RUN_ATTEMPT":"1","KYOTO_WEEKEND_HTTP_APPROVED":"YES",
                   "ARCHIVE_KEY":"ab"*32}),patch(
                "diagnostics.kyoto_weekend_capture.validate_day"),patch(
                "diagnostics.kyoto_weekend_sp_discovery.discover",side_effect=discovery),patch(
                "diagnostics.kyoto_sp_observed_source.capture_verified_sp_seed",side_effect=capture_sp):
            result=capture("20261121","SP",str(self.root/"sp"),live=True,opener=object())
        self.assertEqual(len(observed),2)
        self.assertIs(observed[0],observed[1])
        self.assertEqual(result["observed_http_requests_started"],2)

if __name__=="__main__":
    unittest.main()
