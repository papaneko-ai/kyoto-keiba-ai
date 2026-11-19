"""Regression for the Nov19 real isolated-Turso read-after-collision failure.

The mock injects transport failures only on SELECT. Verify that no INSERT,
UPDATE or DDL is repeated, and production semantics are unchanged.
"""
from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims,TursoClaimUnconfirmed
from diagnostics.kyoto_shared_capture_reservation import key
from tests.test_kyoto_turso_capture_claims import FakeRemote,URL,TOKEN

class IsolatedReadReconciliationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.remote=FakeRemote(Path(tmp.name)/"claims.sqlite")
        self.lab=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote,namespace="ISOLATED_LAB")
        self.lab.prepare_schema()
        self.k="lab:44440761782:"+key(day="20261121",slot=0,race=1,channel="PC",market="racecard")
        self.lab.claim(claim_key=self.k,owner="lab_runner_alpha",now_epoch=10000)
    def _run_with_failed_selects(self,failures,client):
        original=self.remote.post
        counts={"select":0,"insert":0}
        def faulty(*args,**kwargs):
            sql=kwargs["json"]["requests"][0]["stmt"]["sql"]
            if sql.startswith("INSERT"):counts["insert"]+=1
            if sql.startswith("SELECT"):
                counts["select"]+=1
                if counts["select"]<=failures:raise TimeoutError("synthetic read-only contention")
            return original(*args,**kwargs)
        with patch.object(self.remote,"post",side_effect=faulty),patch("time.sleep"):
            result=client.claim(claim_key=self.k,owner="lab_runner_beta",now_epoch=10001)
        return result,counts
    def test_one_read_failure_recovers_without_second_insert(self):
        result,c=self._run_with_failed_selects(1,self.lab)
        self.assertEqual(result["state"],"ACTIVE_LEASE")
        self.assertFalse(result["must_fetch"])
        self.assertEqual(c["insert"],1)
        self.assertEqual(c["select"],2)
    def test_two_read_failures_recovers_on_third_read(self):
        result,c=self._run_with_failed_selects(2,self.lab)
        self.assertEqual(result["state"],"ACTIVE_LEASE")
        self.assertEqual(c["insert"],1)
        self.assertEqual(c["select"],3)
    def test_persistent_failure_fails_closed_without_repeating_insert(self):
        original=self.remote.post
        counts={"insert":0,"select":0}
        def fault(*args,**kwargs):
            sql=kwargs["json"]["requests"][0]["stmt"]["sql"]
            if sql.startswith("INSERT"):counts["insert"]+=1
            if sql.startswith("SELECT"):
                counts["select"]+=1
                raise TimeoutError("unconfirmed select")
            return original(*args,**kwargs)
        with patch.object(self.remote,"post",side_effect=fault),patch("time.sleep"):
            with self.assertRaisesRegex(TursoClaimUnconfirmed,"after_3_safe_attempts"):
                self.lab.claim(claim_key=self.k,owner="lab_runner_beta",now_epoch=10001)
        self.assertEqual(counts,{"insert":1,"select":3})
    def test_operational_namespace_remains_single_read(self):
        prod=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote,namespace="OPERATIONAL")
        prod.prepare_schema()
        base=self.k.split(":",2)[2]
        prod.claim(claim_key=base,owner="runner_alpha",now_epoch=10000)
        original=self.remote.post
        counts={"select":0,"insert":0}
        def fault(*args,**kwargs):
            sql=kwargs["json"]["requests"][0]["stmt"]["sql"]
            if sql.startswith("INSERT"):counts["insert"]+=1
            if sql.startswith("SELECT"):
                counts["select"]+=1
                raise TimeoutError("read failure")
            return original(*args,**kwargs)
        with patch.object(self.remote,"post",side_effect=fault):
            with self.assertRaisesRegex(TursoClaimUnconfirmed,"no_blind_retry"):
                prod.claim(claim_key=base,owner="runner_beta",now_epoch=10001)
        self.assertEqual(counts,{"insert":1,"select":1})

if __name__=="__main__":unittest.main()
