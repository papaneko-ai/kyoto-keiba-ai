"""Offline rehearsal of the exact manual four-job Turso claims entrypoint."""
import io,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
from diagnostics import kyoto_turso_claim_manual_crossrunner as cli
from tests.test_kyoto_turso_capture_claims import FakeRemote,URL,TOKEN
class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        root=Path(t.name)
        remote=FakeRemote(root/"isolated.sqlite")
        self.service=TursoCaptureClaims(url=URL,token=TOKEN,
                                        transport=remote,namespace="ISOLATED_LAB")
        self.env={"KYOTO_TURSO_LAB_CONFIRM":"YES-ISOLATED-CLAIMS-ONLY",
                  "GITHUB_RUN_ID":"44250000000",
                  "GITHUB_OUTPUT":str(root/"outputs.txt"),
                  "FIRST_STATE":"ACQUIRED","SECOND_STATE":"ACTIVE_LEASE"}
        self.env_context=patch.dict(os.environ,self.env)
        self.env_context.start();self.addCleanup(self.env_context.stop)
        self.mock_client=patch.object(cli,"client",return_value=self.service)
        self.mock_client.start();self.addCleanup(self.mock_client.stop)
    def test_exact_four_step_remote_claim_and_reuse(self):
        cli.main("setup")
        cli.main("contender-first")
        cli.main("contender-second")
        cli.main("verify")
        key=cli.synthetic_key()
        item=self.service.observe(key)
        self.assertEqual(item["state"],"DONE")
        self.assertTrue(item["receipt_sha256"])
    def test_no_second_owner_when_first_lease_active(self):
        cli.main("setup")
        cli.main("contender-first")
        cli.main("contender-second")
        outputs=Path(os.environ["GITHUB_OUTPUT"]).read_text()
        self.assertIn("state=ACQUIRED",outputs)
        self.assertIn("state=ACTIVE_LEASE",outputs)
    def test_failed_confirmation_is_denied_by_actual_client_function(self):
        self.mock_client.stop()
        # No network is initiated when explicit CLI approval is missing.
        with patch.dict(os.environ,{"KYOTO_TURSO_LAB_CONFIRM":"NO"}):
            with self.assertRaisesRegex(cli.ManualProofRejected,"approval"):
                cli.main("setup")
if __name__=="__main__":unittest.main()
