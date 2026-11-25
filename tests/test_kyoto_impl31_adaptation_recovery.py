"""Actual capture entrypoint: adaptation failure must not veto acquisition."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import capture,seal
from diagnostics import kyoto_nov15_encrypted_evidence as crypto

DAY="20261129"
REPO="papaneko-ai/kyoto-keiba-ai"
KEY="ab"*32
ENV={"KYOTO_TARGET_DAY":DAY,"KYOTO_WEEKEND_HTTP_APPROVED":"YES",
     "GITHUB_EVENT_NAME":"schedule","ARCHIVE_KEY":KEY,"GITHUB_REPOSITORY":REPO,
     "COLLECTOR_SHA":"a"*40}

def discover(root,**kwargs):
    root.mkdir()
    (root/"sp_discovery_receipt.json").write_text("{}")
    return {"network_requests_started":0,"racecard_url":"observed-fixture"}

class Recovery(unittest.TestCase):
    def test_sp_exception_invalid_decision_and_valid_recovery(self):
        cases=[(RuntimeError("DO_NOT_STORE_SECRET"),None,"BASELINE","ADAPTATION_RUNTIME_EXCEPTION",240),
               (None,("UNKNOWN","fixture"),"BASELINE","ADAPTATION_DECISION_INVALID",240),
               (None,("MARKET_OR_ROSTER_RECOVERY","fixture_verified"),"MARKET_OR_ROSTER_RECOVERY","fixture_verified",360)]
        for err,response,mode,reason,seconds in cases:
            with self.subTest(mode=mode,reason=reason),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,ENV),patch.object(crypto,"DAY",DAY),patch("diagnostics.kyoto_weekend_capture.validate_day"),patch("diagnostics.kyoto_weekend_capture.time.monotonic",return_value=1000),patch("diagnostics.kyoto_impl30_nextday_adaptation.recover",side_effect=err,return_value=response),patch("diagnostics.kyoto_weekend_sp_discovery.discover",side_effect=discover),patch("diagnostics.kyoto_sp_all12_observed_capture.capture_all",return_value={"races":{}}) as acquire:
                root=Path(tmp)/"source"
                capture(DAY,"SP",str(root),live=True,opener=object())
                acquire.assert_called_once()
                self.assertEqual(acquire.call_args.kwargs["deadline_monotonic"],1000+seconds)
                evidence=json.loads((root/"nextday_applied_policy.json").read_text())
                self.assertEqual((evidence["selected_policy"],evidence["reason"],evidence["sp_seconds"]),(mode,reason,seconds))
                self.assertFalse(evidence["source_coverage_proved"])
                self.assertFalse(evidence["improvement_proved"])
                cipher=Path(tmp)/"cipher"
                seal(DAY,str(root),str(cipher),key=KEY,repo=REPO,run_id="31")
                self.assertFalse((cipher/"nextday_applied_policy.json").exists())
                decoded=Path(tmp)/"decoded"
                crypto.decrypt_evidence(cipher,decoded,key_hex=KEY,repo=REPO,run_id="31")
                self.assertEqual(json.loads((decoded/"nextday_applied_policy.json").read_text()),evidence)
                self.assertNotIn("DO_NOT_STORE_SECRET",json.dumps(evidence))
    def test_pc_entrypoint_still_attempts_capture_after_adaptation_error(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,ENV),patch("diagnostics.kyoto_weekend_capture.validate_day"),patch("diagnostics.kyoto_impl30_nextday_adaptation.recover",side_effect=RuntimeError),patch("diagnostics.kyoto_nov15_two_original_observer.observe",side_effect=RuntimeError) as acquire:
            root=Path(tmp)/"source"
            capture(DAY,"PC",str(root),live=True,opener=object())
            acquire.assert_called_once()
            evidence=json.loads((root/"nextday_applied_policy.json").read_text())
            self.assertEqual((evidence["selected_policy"],evidence["pc_market_seconds"]),("BASELINE",720))
    def test_optional_receipt_failure_does_not_block_baseline(self):
        original=Path.open
        def fail_policy(path,*args,**kwargs):
            if path.name=="nextday_applied_policy.json":raise OSError("fixture")
            return original(path,*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,ENV),patch("diagnostics.kyoto_weekend_capture.validate_day"),patch("diagnostics.kyoto_weekend_capture.time.monotonic",return_value=1000),patch("diagnostics.kyoto_impl30_nextday_adaptation.recover",return_value=("PROFILE_RECOVERY","fixture_verified")),patch("diagnostics.kyoto_weekend_sp_discovery.discover",side_effect=discover),patch("diagnostics.kyoto_sp_all12_observed_capture.capture_all",return_value={"races":{}}) as acquire,patch.object(Path,"open",fail_policy):
            capture(DAY,"SP",str(Path(tmp)/"source"),live=True,opener=object())
            self.assertEqual(acquire.call_args.kwargs["deadline_monotonic"],1240)

if __name__=="__main__":unittest.main()
