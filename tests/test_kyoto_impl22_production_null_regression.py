"""Live collector regression: genuine Hrana NULL and no repeated mutation.

Runs completely offline; no Turso credentials, JRA HTTP or Secrets.
"""
import unittest
import tempfile
from pathlib import Path
from diagnostics.kyoto_turso_capture_claims import (
    _rows, TursoCaptureClaims, TursoClaimUnconfirmed
)
from diagnostics.kyoto_shared_capture_reservation import key
from tests.test_kyoto_turso_capture_claims import FakeRemote, URL, TOKEN

class ProductionHranaNullRegression(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.remote=FakeRemote(Path(self.tmp.name)/"remote.sqlite")
        self.gh=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote)
        self.other=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote)
        self.gh.prepare_schema()
        self.k=key(day="20261121",slot=0,race=1,channel="PC",market="quinella")
    def test_authentic_null_does_not_have_value(self):
        self.assertEqual(_rows({"rows":[[{"type":"null"},{"type":"integer","value":"2"},{"type":"text","value":"LEASED"}]]}),[[None,"2","LEASED"]])
    def test_competitor_reads_null_receipt_without_reacquisition(self):
        first=self.gh.claim(claim_key=self.k,owner="github_runner_1",now_epoch=15000)
        second=self.other.claim(claim_key=self.k,owner="streamlit_node_1",now_epoch=15001)
        self.assertEqual(first["state"],"ACQUIRED")
        self.assertEqual(second["state"],"ACTIVE_LEASE")
        self.assertIs(second["must_fetch"],False)
        self.assertIsNone(self.other.observe(self.k)["receipt_sha256"])
        inserts=[x for x in self.remote.history if x["requests"][0]["stmt"]["sql"].startswith("INSERT")]
        self.assertEqual(len(inserts),2) # one atomic attempt per independent caller, never blind replay
        done=self.gh.complete(claim_key=self.k,owner="github_runner_1",generation=first["generation"],sha256="a"*64)
        self.assertTrue(done["committed"])
        replay=self.other.claim(claim_key=self.k,owner="streamlit_node_1",now_epoch=15002)
        self.assertEqual(replay["state"],"DONE_REUSE_EXISTING")
        self.assertEqual(replay["receipt_sha256"],"a"*64)
    def test_malformed_cell_is_not_silent_success(self):
        for v in ({"type":"null","value":"unexpected"},{"type":"blob","base64":"AQ=="},{"type":"text"},{"type":"integer","value":7}):
            with self.subTest(v=v),self.assertRaisesRegex(TursoClaimUnconfirmed,"remote_rows_unconfirmed"):
                _rows({"rows":[[v]]})
    def test_ambiguous_insert_still_not_retried(self):
        self.remote.fail_after_commit=True
        with self.assertRaisesRegex(TursoClaimUnconfirmed,"no_blind_retry"):
            self.gh.claim(claim_key=self.k,owner="github_runner_1",now_epoch=15000)
        writes=[x for x in self.remote.history if x["requests"][0]["stmt"]["sql"].startswith("INSERT")]
        self.assertEqual(len(writes),1)

if __name__=="__main__":unittest.main()
