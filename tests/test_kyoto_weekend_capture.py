"""2026 Nov21/22 no-HTTP acceptance: independent lanes, time, crypto, failure."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import capture, seal


class WeekendCaptureTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.env=patch.dict(os.environ,{"KYOTO_TARGET_DAY":"20261121"},clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_day22_independent_binding(self):
        with patch.dict(os.environ,{"KYOTO_TARGET_DAY":"20261122"}):
            rec=capture("20261122","SP",str(self.root/"sp"),
                        live=False,opener=object())
        self.assertEqual(rec["state"],"SP_OFFICIAL_LINK_NOT_SUPPLIED_ZERO_HTTP")
        self.assertFalse(rec["prediction_ready"])

    def test_no_undiscovered_sp_url_and_no_network(self):
        class Trap:
            def open(self,*a,**kw):
                raise AssertionError("network forbidden")
        rec=capture("20261121","SP",str(self.root/"sp"),
                    live=False,opener=Trap())
        self.assertEqual(rec["observed_http_requests_started"],0)
        self.assertFalse(rec["both_markets_verified"])
        self.assertTrue((self.root/"sp"/"receipt.json").is_file())

    def test_date_mismatch_fail_closed_without_output(self):
        with self.assertRaisesRegex(ValueError,"capture_day_binding_invalid"):
            capture("20261122","SP",str(self.root/"sp"),
                    live=False,opener=object())
        self.assertFalse((self.root/"sp").exists())

    def test_pc_capture_preserves_exact_provenance_original_and_receipt(self):
        def fake_observe(path,**kwargs):
            path=Path(path)
            path.mkdir()
            (path/"official_selection.html").write_bytes(b"<html>synthetic</html>")
            (path/"receipt.json").write_text('{"selection_sha256":"abc","selection_captured_at_utc":"2026-11-21T02:00:00+00:00"}')
            return {"state":"NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD",
                    "http_requests_started":2,"selection_sha256":"abc"}
        with patch("diagnostics.kyoto_nov15_two_original_observer.observe",fake_observe):
            rec=capture("20261121","PC",str(self.root/"pc"),live=False,opener=object())
        self.assertEqual(rec["observed_http_requests_started"],2)
        self.assertEqual((self.root/"pc"/"official_selection.html").read_bytes(),b"<html>synthetic</html>")
        self.assertEqual(json.loads((self.root/"pc"/"receipt.json").read_text())["selection_sha256"],"abc")
        self.assertFalse((self.root/"pc"/"pc_originals").exists())

    def test_seal_and_decrypt_preserves_sources_without_plaintext_upload(self):
        from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
        source=self.root/"source"
        source.mkdir()
        (source/"receipt.json").write_text('{"state":"SYNTHETIC_ONLY"}')
        (source/"official_selection.html").write_bytes(b"<html>fake only</html>")
        out=self.root/"cipher"
        key="ab"*32
        result=seal("20261121",str(source),str(out),key=key,
                    repo="papaneko-ai/kyoto-keiba-ai",run_id="20261121")
        self.assertTrue(result["encrypted_only"])
        self.assertFalse(source.exists())
        self.assertFalse((out/"official_selection.html").exists())
        self.assertTrue((out/"originals.tar.gz.aesgcm").exists())
        decoded=self.root/"decoded"
        check=decrypt_evidence(out,decoded,key_hex=key,
                               repo="papaneko-ai/kyoto-keiba-ai",run_id="20261121")
        self.assertTrue(check["authentication_tag_verified"])
        self.assertEqual((decoded/"official_selection.html").read_bytes(),b"<html>fake only</html>")

    def test_seal_not_started_records_zero_http_safe_stop(self):
        p=self.root/"stop"
        seal("20261121",str(self.root/"missing"),str(p),key="",
             repo="papaneko-ai/kyoto-keiba-ai",run_id="1")
        receipt=json.loads((p/"safe_stop.json").read_text())
        self.assertFalse(receipt["JRA_success"])
        self.assertEqual(receipt["actual_jra_http_requests"],0)

    def test_seal_existing_destination_cannot_overwrite(self):
        source=self.root/"source"
        source.mkdir()
        (source/"receipt.json").write_text("{}")
        dest=self.root/"evidence"
        dest.mkdir()
        with self.assertRaisesRegex(ValueError,"seal_destination_must_not_exist"):
            seal("20261121",str(source),str(dest),key="ab"*32,
                 repo="papaneko-ai/kyoto-keiba-ai",run_id="1")

    def test_weekend_sp_terminal_discovery_preserves_original_without_more_http(self):
        def refused(folder,**kwargs):
            p=Path(folder);p.mkdir()
            (p/"official_sp_discovery_1.html").write_bytes(b"saved before refusal")
            (p/"sp_discovery_receipt.json").write_text('{"stop_followup_http":true}')
            return {"state":"OFFICIAL_R12_LINK_NOT_OBSERVED","network_requests_started":2,
                    "racecard_url":"observed-fixture","stop_followup_http":True}
        with patch.dict(os.environ,{"KYOTO_TARGET_DAY":"20261128","GITHUB_EVENT_NAME":"schedule","KYOTO_WEEKEND_HTTP_APPROVED":"YES","ARCHIVE_KEY":"ab"*32}),patch("diagnostics.kyoto_weekend_capture.validate_day"),patch("diagnostics.kyoto_weekend_sp_discovery.discover",side_effect=refused),patch("diagnostics.kyoto_sp_all12_observed_capture.capture_all") as acquire:
            root=self.root/"sp"
            result=capture("20261128","SP",str(root),live=True,opener=object())
        acquire.assert_not_called()
        self.assertEqual(result["state"],"SP_DISCOVERY_TERMINAL_HTTP_STOP")
        self.assertEqual(result["observed_http_requests_started"],2)
        self.assertEqual((root/"official_sp_discovery_1.html").read_bytes(),b"saved before refusal")
        self.assertFalse(result["prediction_ready"])

    def test_explicit_recovery_rerun_is_not_rejected_before_source_discovery(self):
        class NoNetwork:
            def open(self,*args,**kwargs):
                raise AssertionError("unexpected_JRA_HTTP")
        def no_link(folder,**kwargs):
            Path(folder).mkdir()
            return {"state":"OFFICIAL_R12_LINK_NOT_OBSERVED",
                    "network_requests_started":0,"racecard_url":""}
        with patch.dict(os.environ,{
            "GITHUB_EVENT_NAME":"schedule","GITHUB_RUN_ATTEMPT":"2",
            "KYOTO_WEEKEND_HTTP_APPROVED":"YES","ARCHIVE_KEY":"ab"*32
        }),patch("diagnostics.kyoto_weekend_capture.validate_day",return_value=None),patch(
            "diagnostics.kyoto_weekend_sp_discovery.discover",side_effect=no_link):
            rec=capture("20261121","SP",str(self.root/"sp"),
                        live=True,sp_source_url="",opener=NoNetwork())
        self.assertEqual(rec["state"],"OFFICIAL_R12_LINK_NOT_OBSERVED")
        self.assertEqual(rec["observed_http_requests_started"],0)
        self.assertTrue((self.root/"sp"/"receipt.json").is_file())


if __name__=="__main__":
    unittest.main()
