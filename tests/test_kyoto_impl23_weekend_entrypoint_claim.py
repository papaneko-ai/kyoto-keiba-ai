"""Verify production PC entrypoint forwards coordinator to G06, without network."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import capture

DAY="20261121"
HOST="kyoto-claims-prod.example.turso.io"  # synthetic; no external I/O
class NoNetwork:
    def open(self,*a,**kw):raise AssertionError("UNEXPECTED_HTTP")
class Tests(unittest.TestCase):
    def scenario(self,activated):
        with tempfile.TemporaryDirectory() as tmp:
            env={"KYOTO_TARGET_DAY":DAY,"GITHUB_EVENT_NAME":"schedule",
                 "GITHUB_EVENT_SCHEDULE":"15 0 21 11 *",
                 "GITHUB_RUN_ID":"44444444000","GITHUB_JOB":"pc-originals-independent",
                 "KYOTO_WEEKEND_HTTP_APPROVED":"YES","ARCHIVE_KEY":"ab"*32,
                 "KYOTO_SHARED_CLAIM_ACTIVATE":"YES" if activated else "NO"}
            if activated:
                env.update({"KYOTO_SHARED_CLAIM_TARGET":"PRODUCTION",
                    "KYOTO_SHARED_CLAIM_PRODUCTION_APPROVED":"YES",
                    "KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST":HOST,
                    "KYOTO_SHARED_CLAIM_TURSO_URL":"libsql://"+HOST,
                    "KYOTO_SHARED_CLAIM_TURSO_TOKEN":"synthetic_not_real_secret"})
            called=[]
            def observe(path,**kw):
                p=Path(path);p.mkdir()
                (p/"receipt.json").write_text('{"selection_sha256":null}')
                return {"state":"MOCK_ORIGINALS","http_requests_started":0,
                        "selection_sha256":None}
            def fake_g06(root,**kw):
                called.append(kw)
                p=Path(root);p.mkdir()
                (p/"g06_batch_receipt.json").write_text('{"mock":true}')
                return {"verified_dual_market_races":0,
                        "downstream_intake_created":False}
            with patch.dict(os.environ,env,clear=True),\
                patch("diagnostics.kyoto_weekend_capture.validate_day"),\
                patch("diagnostics.kyoto_nov15_two_original_observer.observe",observe),\
                patch("diagnostics.kyoto_g03_weekend_bridge.collect_after_observer",
                      return_value={"complete":False,"network_requests_started":0}),\
                patch("diagnostics.kyoto_g03_to_g06_input_adapter.records_from_g03",
                      return_value={r: ({"mock":True} if r==11 else None) for r in range(1,13)}),\
                patch("diagnostics.kyoto_g06_all12_capture.run_twelve",fake_g06),\
                patch("diagnostics.jra_one_shot_market_capture.RequestPacer"):
                result=capture(DAY,"PC",str(Path(tmp)/"originals"),live=True,opener=NoNetwork())
            self.assertEqual(len(called),1)
            return result,called[0]
    def test_enabled_production_entrypoint_forwards_claim_scope(self):
        result,args=self.scenario(True)
        self.assertEqual(args["claim_slot"],0)
        self.assertEqual(args["claim_client"].endpoint,"https://"+HOST+"/v2/pipeline")
        self.assertEqual(args["claim_owner"],"github_44444444000_pc-originals-independent")
        self.assertEqual(result["g06_shared_claim_state"],"CONFIGURED_PRODUCTION_TURSO")
    def test_inactive_production_entrypoint_preserves_existing_path(self):
        result,args=self.scenario(False)
        self.assertNotIn("claim_client",args)
        self.assertEqual(result["g06_shared_claim_state"],"OPTIONAL_COORDINATION_NOT_CONFIGURED")
if __name__=="__main__":unittest.main()
