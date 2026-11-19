"""Offline cross-environment probe acceptance, no Streamlit runtime or network."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
from tests.test_kyoto_turso_capture_claims import FakeRemote,URL,TOKEN
from streamlit_turso_cross_environment_proof_impl22 import (
    proof_key,lab_client,observe_finished_gh_run,attempt_active_lease
)

class StreamlitCrossEnvTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.remote=FakeRemote(Path(tmp.name)/"isolated.sqlite")
        self.gh=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote,namespace="ISOLATED_LAB")
        self.st=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote,namespace="ISOLATED_LAB")
        self.gh.prepare_schema()
        self.id="44443836669"
        self.k=proof_key(self.id)
    def test_strict_run_id(self):
        for v in ("../x","123","44443836669 ","123456789012345678901"):
            with self.assertRaises(ValueError):proof_key(v)
    def test_test_host_only(self):
        with self.assertRaises(ValueError):
            lab_client("libsql://production.turso.io",TOKEN,self.remote)
    def test_read_gh_completion_from_streamlit(self):
        first=self.gh.claim(claim_key=self.k,owner="lab_"+self.id+"_contender_first",now_epoch=10000)
        sha=hashlib.sha256(("SYNTHETIC_NO_JRA:"+self.k).encode()).hexdigest()
        self.assertTrue(self.gh.complete(claim_key=self.k,owner="lab_"+self.id+"_contender_first",
            generation=first["generation"],sha256=sha)["committed"])
        result=observe_finished_gh_run(self.st,self.id)
        self.assertEqual(result["status"],"REMOTE_GITHUB_RECEIPT_OBSERVED")
        self.assertEqual(result["state"],"DONE")
    def test_reject_unfinished_lease(self):
        self.gh.claim(claim_key=self.k,owner="lab_"+self.id+"_contender_first",now_epoch=10000)
        self.assertEqual(observe_finished_gh_run(self.st,self.id)["status"],"NOT_VERIFIED")
    def test_no_duplicate_fetch_when_other_host_owns_lease(self):
        self.gh.claim(claim_key=self.k,owner="lab_"+self.id+"_contender_first",now_epoch=10000,lease_seconds=600)
        result=attempt_active_lease(self.st,self.id,now_epoch=10010)
        self.assertEqual(result,{"status":"REMOTE_LEASE_RESPECTED","must_fetch":False})
    def test_no_mutation_when_lease_expired(self):
        self.gh.claim(claim_key=self.k,owner="lab_"+self.id+"_contender_first",now_epoch=10000,lease_seconds=30)
        before=self.st.observe(self.k)
        out=attempt_active_lease(self.st,self.id,now_epoch=10031)
        self.assertEqual(out["reason"],"NO_ACTIVE_GITHUB_LEASE")
        self.assertEqual(self.st.observe(self.k),before)

if __name__=="__main__":unittest.main()
