"""Hrana-v2 statement errors are not malformed success responses.

No network, credentials, or live database operations occur in these tests.
"""
from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims, TursoClaimUnconfirmed
from diagnostics.kyoto_shared_capture_reservation import key
from tests.test_kyoto_turso_capture_claims import FakeRemote, URL, TOKEN, Reply

class HranaStatementResultsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.remote=FakeRemote(Path(tmp.name)/"remote.sqlite")
        self.lab=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote,namespace="ISOLATED_LAB")
        self.lab.prepare_schema()
        self.k="lab:44441860125:"+key(day="20261121",slot=0,race=1,channel="PC",market="racecard")
        self.lab.claim(claim_key=self.k,owner="lab_runner_A",now_epoch=10000)
    def _failure(self,code,message):
        original=self.remote.post
        counts={"insert":0,"select":0}
        def response(*args,**kwargs):
            sql=kwargs["json"]["requests"][0]["stmt"]["sql"]
            if sql.startswith("INSERT"):counts["insert"]+=1
            if sql.startswith("SELECT "):
                counts["select"]+=1
                return Reply({"results":[
                   {"type":"error","error":{"code":code,"message":message}},
                   {"type":"ok","response":{"type":"close"}}]})
            return original(*args,**kwargs)
        with patch.object(self.remote,"post",side_effect=response),patch("time.sleep"):
            with self.assertRaises(TursoClaimUnconfirmed) as caught:
                self.lab.claim(claim_key=self.k,owner="lab_runner_B",now_epoch=10001)
        return str(caught.exception),counts
    def test_sqlite_busy_is_identified_without_secret(self):
        msg,c=self._failure("SQLITE_BUSY","hidden "+TOKEN)
        self.assertIn("isolated_read_sql_sqlite_busy",msg)
        self.assertNotIn(TOKEN,msg)
        self.assertEqual(c,{"insert":1,"select":3})
    def test_sqlite_locked_category(self):
        msg,c=self._failure("SQLITE_LOCKED","private row id")
        self.assertIn("isolated_read_sql_sqlite_locked",msg)
        self.assertNotIn("private row id",msg)
        self.assertEqual(c["insert"],1)
    def test_unrecognized_code_never_reflected(self):
        msg,c=self._failure("TOKEN_"+TOKEN,"private")
        self.assertIn("isolated_read_sql_other",msg)
        self.assertNotIn(TOKEN,msg)
        self.assertEqual(c["insert"],1)
    def test_existing_protocol_and_contention_tests_remain(self):
        self.assertEqual(self.lab.observe(self.k)["state"],"LEASED")

if __name__=="__main__":unittest.main()
