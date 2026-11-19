"""No-secret failure classification for isolated Turso SELECT, never writes."""
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims,TursoClaimUnconfirmed
from diagnostics.kyoto_shared_capture_reservation import key
from tests.test_kyoto_turso_capture_claims import FakeRemote,URL,TOKEN,Reply

class CategorizationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.remote=FakeRemote(Path(tmp.name)/"remote.sqlite")
        self.lab=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote,namespace="ISOLATED_LAB")
        self.lab.prepare_schema()
        self.k="lab:44441304774:"+key(day="20261121",slot=0,race=1,channel="PC",market="racecard")
        self.lab.claim(claim_key=self.k,owner="lab_runner_A",now_epoch=10000)
    def test_http_status_sanitized(self):
        old=self.remote.post
        def wrapper(*args,**kwargs):
            sql=kwargs["json"]["requests"][0]["stmt"]["sql"]
            if sql.startswith("SELECT "):
                r=Reply({})
                r.status_code=503
                return r
            return old(*args,**kwargs)
        with patch.object(self.remote,"post",side_effect=wrapper),patch("time.sleep"):
            with self.assertRaises(TursoClaimUnconfirmed) as ctx:
                self.lab.claim(claim_key=self.k,owner="lab_runner_B",now_epoch=10001)
        msg=str(ctx.exception)
        self.assertIn("isolated_read_http_503",msg)
        self.assertNotIn(TOKEN,msg)
    def test_transport_error_sanitized(self):
        old=self.remote.post
        def wrapper(*args,**kwargs):
            sql=kwargs["json"]["requests"][0]["stmt"]["sql"]
            if sql.startswith("SELECT "):
                raise TimeoutError("sensitive transport error "+TOKEN)
            return old(*args,**kwargs)
        with patch.object(self.remote,"post",side_effect=wrapper),patch("time.sleep"):
            with self.assertRaises(TursoClaimUnconfirmed) as ctx:
                self.lab.claim(claim_key=self.k,owner="lab_runner_B",now_epoch=10001)
        self.assertIn("isolated_read_transport",str(ctx.exception))
        self.assertNotIn(TOKEN,str(ctx.exception))
    def test_shape_error_sanitized(self):
        old=self.remote.post
        def wrapper(*args,**kwargs):
            sql=kwargs["json"]["requests"][0]["stmt"]["sql"]
            if sql.startswith("SELECT "):
                return Reply({"results":[]})
            return old(*args,**kwargs)
        with patch.object(self.remote,"post",side_effect=wrapper),patch("time.sleep"):
            with self.assertRaises(TursoClaimUnconfirmed) as ctx:
                self.lab.claim(claim_key=self.k,owner="lab_runner_B",now_epoch=10001)
        self.assertIn("isolated_read_response_shape",str(ctx.exception))
    def test_operational_error_message_unchanged(self):
        other=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote,namespace="OPERATIONAL")
        other.prepare_schema()
        base=self.k.split(":",2)[2]
        other.claim(claim_key=base,owner="runner_one",now_epoch=10000)
        old=self.remote.post
        def wrapper(*args,**kwargs):
            sql=kwargs["json"]["requests"][0]["stmt"]["sql"]
            if sql.startswith("SELECT "):raise TimeoutError("blocked")
            return old(*args,**kwargs)
        with patch.object(self.remote,"post",side_effect=wrapper):
            with self.assertRaisesRegex(TursoClaimUnconfirmed,"mutation_or_read_unconfirmed_no_blind_retry"):
                other.claim(claim_key=base,owner="runner_two",now_epoch=10001)

if __name__=="__main__":unittest.main()
