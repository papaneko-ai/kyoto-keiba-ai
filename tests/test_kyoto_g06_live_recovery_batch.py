"""Authorized G06 twelve-race batch executes one-market HTTP repair, not just plan."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hashlib import sha256
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.kyoto_g06_missing_market_retry import recover_one as actual_recover
from diagnostics.jra_one_shot_market_capture import DEFAULT_RACE_SPEC
from tests.test_kyoto_g06_item_level_recovery import setup,RUNNERS,START,TIME
from tests.test_jra_market_source_chain import B,html

def records():
    r={i:None for i in range(1,13)}
    r[11]={"race_spec":DEFAULT_RACE_SPEC,"verified_start_utc":START,
           "active_runners":RUNNERS,
           "expected_named_runners":tuple((n,f,"馬"+str(n)) for n,f in RUNNERS),
           "primary_channel":"PC"}
    return r
class BatchHttpRecovery(unittest.TestCase):
    def test_auto_collects_only_missing_market(self):
        calls=[]
        def initial(out,**kw):
            setup(out,"PC",["quinella"])
            return {"state":"SAFE_STOP","selected_channel":None,
                    "attempts":[{"channel":"PC","state":"CAPTURE_BLOCKED","reason":"TimeoutError"}]}
        def fake_http(opener,channel,url,**kw):
            calls.append((channel,kw["cname"]))
            raw=html("枠連オッズ",B)
            return {"raw":raw,"sha256":sha256(raw).hexdigest(),"bytes":len(raw),
                    "captured_at_utc":TIME,"requested_url":url,"response_url":url,
                    "http_status":200,"method":"POST","observed_action_token":kw["cname"],
                    "post_body_sha256":"a"*64,"post_body_size":20}
        def repair(**kw):
            return actual_recover(**dict(kw,opener=object(),now_utc=TIME))
        with tempfile.TemporaryDirectory() as td:
            with patch("diagnostics.kyoto_g06_all12_capture.capture_hybrid",side_effect=initial),patch(
                 "diagnostics.kyoto_g06_all12_capture.recover_one",side_effect=repair),patch(
                 "diagnostics.kyoto_g06_missing_market_retry.http_fetch",side_effect=fake_http):
                outcome=run_twelve(Path(td)/"batch",records=records(),authorized_live_http=True)
            from diagnostics.kyoto_g06_four_stage_inboxes import read_inboxes
            stages=read_inboxes(Path(td)/"batch")
            self.assertTrue(outcome["downstream_intake_created"])
            self.assertEqual(outcome["downstream_source_ready_races"],1)
            self.assertEqual(len(stages["P4"]["races"][10]["payload"]["markets"]),2)
            self.assertEqual(stages["G07"]["races"][10]["payload"]["horses"][0]["number"],1)
            self.assertFalse(stages["P5"]["prediction_or_trade_authorized"])
            self.assertFalse(stages["P6"]["prediction_or_trade_authorized"])
        self.assertEqual(outcome["verified_dual_market_races"],1)
        self.assertEqual(len(calls),1)
        self.assertEqual(outcome["records"][10]["live_market_recovery_attempts"][0]["state"],
                         "MARKET_RAW_CAPTURED_REQUIRES_INDEPENDENT_GATE")
    def test_403_refusal_blocks_market_retry(self):
        attempts=[]
        def initial(out,**kw):
            setup(out,"PC",["quinella"])
            return {"state":"SAFE_STOP","selected_channel":None,
                    "attempts":[{"reason":"HTTP Error 403","channel":"PC"}]}
        with tempfile.TemporaryDirectory() as td:
            with patch("diagnostics.kyoto_g06_all12_capture.capture_hybrid",side_effect=initial),patch(
                "diagnostics.kyoto_g06_all12_capture.recover_one",side_effect=lambda **kw: attempts.append(kw)):
                report=run_twelve(Path(td)/"batch",records=records(),authorized_live_http=True)
        self.assertEqual(attempts,[])
        self.assertEqual(report["records"][10]["live_market_recovery_attempts"][0]["state"],
                         "GLOBAL_ACCESS_REFUSAL_RETAIN_ORIGINALS")
    def test_non_authorized_mock_batch_never_http(self):
        def initial(out,**kw):
            setup(out,"PC",["quinella"])
            return {"state":"SAFE_STOP","selected_channel":None,"attempts":[]}
        with tempfile.TemporaryDirectory() as td:
            with patch("diagnostics.kyoto_g06_all12_capture.recover_one",
                       side_effect=AssertionError("illegal HTTP")):
                report=run_twelve(Path(td)/"batch",records=records(),
                                  authorized_live_http=False,runner=initial)
        self.assertEqual(report["verified_dual_market_races"],0)
        self.assertFalse(report["g06_certified"])
if __name__=="__main__":unittest.main()
