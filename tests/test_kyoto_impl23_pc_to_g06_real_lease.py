"""PC entrypoint -> real G06 batch -> shared ledger: only one collector call."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import capture
from diagnostics.kyoto_shared_capture_reservation import SharedLedger
from tests.test_kyoto_g06_full_twelve_reparse_e2e import records,capture_mock
DAY="20261121"
class NoNetwork:
    def open(self,*a,**kw):raise AssertionError("unexpected HTTP")
class Tests(unittest.TestCase):
    def test_two_pc_entrypoints_same_slot_one_market_collector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ledger=SharedLedger(root/"coordinator.sqlite")
            self.addCleanup(ledger.close)
            original=records()
            selected={r:original[r] if r==11 else None for r in range(1,13)}
            calls=[]
            def observer(path,**kw):
                p=Path(path);p.mkdir()
                (p/"receipt.json").write_text('{"selection_sha256":null}')
                return {"state":"SYNTHETIC_OBSERVER","http_requests_started":0,"selection_sha256":None}
            def fake_capture(out,**kw):
                calls.append(kw["race_spec"].race_number)
                return capture_mock(out,**kw)
            def activation(day):
                assert day==DAY
                return {"enabled":True,"claim_client":ledger,"claim_slot":0,
                        "claim_owner":os.environ["GITHUB_RUN_ID"]+"_pc",
                        "claim_now_epoch":10000}
            env={"KYOTO_TARGET_DAY":DAY,"GITHUB_EVENT_NAME":"schedule",
                 "KYOTO_WEEKEND_HTTP_APPROVED":"YES","ARCHIVE_KEY":"ab"*32,
                 "KYOTO_SHARED_CLAIM_ACTIVATE":"YES",
                 "KYOTO_SHARED_CLAIM_TARGET":"PRODUCTION"}
            with patch.dict(os.environ,env,clear=True),\
                patch("diagnostics.kyoto_weekend_capture.validate_day"),\
                patch("diagnostics.kyoto_nov15_two_original_observer.observe",observer),\
                patch("diagnostics.kyoto_g03_weekend_bridge.collect_after_observer",
                      return_value={"complete":False,"network_requests_started":0}),\
                patch("diagnostics.kyoto_g03_to_g06_input_adapter.records_from_g03",return_value=selected),\
                patch("diagnostics.kyoto_weekend_remote_claim_runtime.active_claims_for_weekend",activation),\
                patch("diagnostics.kyoto_g06_all12_capture.capture_hybrid",side_effect=fake_capture),\
                patch("diagnostics.jra_one_shot_market_capture.RequestPacer"):
                os.environ["GITHUB_RUN_ID"]="github_run_one"
                first=capture(DAY,"PC",str(root/"first"),live=True,opener=NoNetwork())
                os.environ["GITHUB_RUN_ID"]="github_run_two"
                second=capture(DAY,"PC",str(root/"second"),live=True,opener=NoNetwork())
            self.assertEqual(calls,[11])
            self.assertTrue(first["g06_twelve_race_market_attempted"])
            self.assertTrue(second["g06_twelve_race_market_attempted"])
            self.assertEqual(first["g06_paired_market_races"],1)
            self.assertEqual(second["g06_paired_market_races"],0)
            self.assertEqual(first["g06_shared_claim_state"],"CONFIGURED_PRODUCTION_TURSO")
            self.assertTrue((root/"first"/"g06_source_bundle.tar.gz").is_file())
            self.assertTrue((root/"second"/"g06_source_bundle.tar.gz").is_file())
if __name__=="__main__":unittest.main()
