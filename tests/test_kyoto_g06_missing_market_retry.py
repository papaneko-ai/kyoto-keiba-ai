"""End-to-end mocked HTTP POST after verified PC source partial capture."""
import json
import tempfile
import unittest
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from diagnostics.kyoto_g06_missing_market_retry import recover_one
from diagnostics.kyoto_g06_item_level_recovery import recover_saved_markets
from tests.test_kyoto_g06_item_level_recovery import setup,SPEC,RUNNERS,START,TIME
from tests.test_jra_market_source_chain import html,B
from diagnostics.jra_market_source_chain import SourceChainError

class RecoveryHttpTests(unittest.TestCase):
    def response(self,opener,channel,url,**kwargs):
        self.calls.append((channel,url,kwargs.get("cname")))
        if channel!="PC" or not kwargs.get("cname"):
            raise AssertionError("unexpected HTTP")
        raw=html("枠連オッズ",B)
        return {"raw":raw,"sha256":sha256(raw).hexdigest(),"bytes":len(raw),
                "captured_at_utc":TIME,"requested_url":url,"response_url":url,
                "http_status":200,"method":"POST",
                "observed_action_token":kwargs["cname"],"post_body_sha256":"a"*64,
                "post_body_size":20}
    def setUp(self):self.calls=[]
    def test_partial_pc_market_is_restored_without_refetching_quinella(self):
        with tempfile.TemporaryDirectory() as td:
            setup(td,"PC",["quinella"])
            with patch("diagnostics.kyoto_g06_missing_market_retry.http_fetch",
                       side_effect=self.response):
                result=recover_one(root=td,channel="PC",market="bracket_quinella",
                     race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START,
                     opener=object(),now_utc=TIME)
            self.assertEqual(result["state"],"MARKET_RAW_CAPTURED_REQUIRES_INDEPENDENT_GATE")
            self.assertEqual(len(self.calls),1)
            self.assertEqual(self.calls[0][0],"PC")
            self.assertTrue((Path(td)/"pc"/"quinella_original.html").is_file())
            self.assertFalse((Path(td)/"pc"/"bracket_quinella_original.html").exists())
            self.assertTrue((Path(td)/"pc_recovery"/"bracket_quinella_original.html").is_file())
            verified=recover_saved_markets(td,race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START)
            self.assertTrue(verified["both_markets_verified"])
            self.assertFalse(verified["mixed_channel"])
            self.assertFalse(verified["simultaneous_snapshot_asserted"])
            self.assertEqual(verified["markets"]["bracket_quinella"]["selected"]["channel"],"PC")
    def test_existing_market_is_not_requested(self):
        with tempfile.TemporaryDirectory() as td:
            setup(td,"PC",["quinella"])
            with self.assertRaisesRegex(SourceChainError,"already_observed"):
                recover_one(root=td,channel="PC",market="quinella",race_spec=SPEC,
                  active_runners=RUNNERS,verified_start_utc=START,opener=object(),now_utc=TIME)
            self.assertEqual(self.calls,[])
    def test_tampered_navigation_stops_before_http(self):
        with tempfile.TemporaryDirectory() as td:
            setup(td,"PC",["quinella"])
            (Path(td)/"pc"/"official_odds_menu.html").write_bytes(b"tampered")
            with self.assertRaisesRegex(SourceChainError,"sha_mismatch"):
                recover_one(root=td,channel="PC",market="bracket_quinella",race_spec=SPEC,
                  active_runners=RUNNERS,verified_start_utc=START,opener=object(),now_utc=TIME)
            self.assertFalse((Path(td)/"pc_recovery").exists())
    def test_past_cutoff_stops_before_http(self):
        with tempfile.TemporaryDirectory() as td:
            setup(td,"PC",["quinella"])
            with self.assertRaisesRegex(SourceChainError,"cutoff"):
                recover_one(root=td,channel="PC",market="bracket_quinella",race_spec=SPEC,
                  active_runners=RUNNERS,verified_start_utc=START,
                  opener=object(),now_utc="2026-11-07T06:40:00Z")
            self.assertEqual(self.calls,[])
    def test_missing_live_authorization_without_injected_client_zero_http(self):
        with tempfile.TemporaryDirectory() as td:
            setup(td,"PC",["quinella"])
            with self.assertRaisesRegex(SourceChainError,"not_authorized"):
                recover_one(root=td,channel="PC",market="bracket_quinella",race_spec=SPEC,
                  active_runners=RUNNERS,verified_start_utc=START,now_utc=TIME)
            self.assertEqual(self.calls,[])
    def test_repeat_does_not_overwrite_original(self):
        with tempfile.TemporaryDirectory() as td:
            setup(td,"PC",["quinella"])
            with patch("diagnostics.kyoto_g06_missing_market_retry.http_fetch",
                       side_effect=self.response):
                recover_one(root=td,channel="PC",market="bracket_quinella",race_spec=SPEC,
                  active_runners=RUNNERS,verified_start_utc=START,opener=object(),now_utc=TIME)
                with self.assertRaisesRegex(SourceChainError,"destination_exists"):
                    recover_one(root=td,channel="PC",market="bracket_quinella",race_spec=SPEC,
                      active_runners=RUNNERS,verified_start_utc=START,opener=object(),now_utc=TIME)
            self.assertEqual(len(self.calls),1)
    def test_recovered_original_byte_tamper_rejected_by_independent_gate(self):
        with tempfile.TemporaryDirectory() as td:
            setup(td,"PC",["quinella"])
            with patch("diagnostics.kyoto_g06_missing_market_retry.http_fetch",side_effect=self.response):
                recover_one(root=td,channel="PC",market="bracket_quinella",race_spec=SPEC,
                  active_runners=RUNNERS,verified_start_utc=START,opener=object(),now_utc=TIME)
            (Path(td)/"pc_recovery"/"bracket_quinella_original.html").write_bytes(b"tampered")
            output=recover_saved_markets(td,race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START)
            self.assertFalse(output["both_markets_verified"])
    def test_error_preserves_originals_and_failure_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            setup(td,"PC",["quinella"])
            def fail(*a,**kw):raise TimeoutError("mock")
            with patch("diagnostics.kyoto_g06_missing_market_retry.http_fetch",side_effect=fail):
                result=recover_one(root=td,channel="PC",market="bracket_quinella",race_spec=SPEC,
                  active_runners=RUNNERS,verified_start_utc=START,opener=object(),now_utc=TIME)
            self.assertEqual(result["state"],"CAPTURE_BLOCKED")
            self.assertEqual(len(self.calls),0)
            self.assertTrue((Path(td)/"pc"/"quinella_original.html").exists())
            self.assertTrue((Path(td)/"pc_recovery"/"receipt.json").exists())
if __name__=="__main__":unittest.main()
