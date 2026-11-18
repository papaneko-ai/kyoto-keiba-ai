"""Two independent Turso-v2 client transports against same fake remote SQL DB.

Contract tests are deliberately OFFLINE; real Turso is never contacted.
"""
from __future__ import annotations
import sqlite3,tempfile,threading,unittest
from pathlib import Path
from diagnostics.kyoto_turso_capture_claims import (
    TursoCaptureClaims,TursoClaimUnconfirmed,ReservationError)
from diagnostics.kyoto_shared_capture_reservation import key
URL="libsql://kyoto-ai-test-fixture.turso.io"
TOKEN="mock-private-credential-no-real-access"
class Reply:
    status_code=200
    def __init__(self,body):self.body=body
    def json(self):return self.body
class FakeRemote:
    def __init__(self,path):
        self.path=str(path);self.lock=threading.Lock()
        self.fail_after_commit=False;self.history=[]
    def post(self,url,headers,json,timeout,allow_redirects):
        assert url=="https://kyoto-ai-test-fixture.turso.io/v2/pipeline"
        assert headers["Authorization"]=="Bearer "+TOKEN
        assert allow_redirects is False and timeout==12
        with self.lock:
            self.history.append(json)
            results=[]
            with sqlite3.connect(self.path) as db:
                for req in json["requests"]:
                    if req["type"]=="close":
                        results.append({"type":"ok","response":{"type":"close"}});continue
                    item=req["stmt"]
                    values=[v["value"] for v in item["args"]]
                    c=db.execute(item["sql"],values)
                    fields=(c.fetchall() if c.description else [])
                    rows=[[{"type":"text","value":str(v) if v is not None else None} for v in row] for row in fields]
                    results.append({"type":"ok","response":{"type":"execute","result":{"rows":rows}}})
                db.commit()
            if self.fail_after_commit:
                self.fail_after_commit=False
                raise TimeoutError("unknown mutation result; do not replay!")
            return Reply({"results":results})
class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        remote=FakeRemote(Path(t.name)/"remote.sqlite")
        self.remote=remote
        self.a=TursoCaptureClaims(url=URL,token=TOKEN,transport=remote)
        self.b=TursoCaptureClaims(url=URL,token=TOKEN,transport=remote)
        self.a.prepare_schema()
        self.k=key(day="20261121",slot=0,race=11,channel="PC",market="quinella")
    def test_shared_external_clients_one_owner(self):
        x=self.a.claim(claim_key=self.k,owner="github_actions_1",now_epoch=10000)
        y=self.b.claim(claim_key=self.k,owner="streamlit_node_1",now_epoch=10000)
        self.assertTrue(x["must_fetch"]);self.assertFalse(y["must_fetch"])
        self.assertEqual(y["state"],"ACTIVE_LEASE")
        self.assertTrue(self.a.complete(claim_key=self.k,owner="github_actions_1",
                        generation=x["generation"],sha256="a"*64)["committed"])
        self.assertEqual(self.b.claim(claim_key=self.k,owner="streamlit_node_1",
                         now_epoch=10001)["state"],"DONE_REUSE_EXISTING")
    def test_two_parallel_threads_one_atomic_insert(self):
        barrier=threading.Barrier(2)
        out=[]
        lock=threading.Lock()
        def request(client,owner):
            barrier.wait()
            result=client.claim(claim_key=self.k,owner=owner,now_epoch=10000)
            with lock:out.append(result)
        t1=threading.Thread(target=request,args=(self.a,"github_actions_1"))
        t2=threading.Thread(target=request,args=(self.b,"streamlit_node_1"))
        t1.start();t2.start();t1.join();t2.join()
        self.assertEqual(len(out),2)
        self.assertEqual(sum(x["must_fetch"] for x in out),1)
    def test_failed_attempt_does_not_block_next_slot(self):
        x=self.a.claim(claim_key=self.k,owner="github_actions_1",now_epoch=10000)
        self.assertTrue(self.a.abandon(claim_key=self.k,owner="github_actions_1",
                    generation=x["generation"],now_epoch=10000)["released"])
        y=self.b.claim(claim_key=self.k,owner="streamlit_node_1",now_epoch=10000)
        self.assertTrue(y["must_fetch"])
        for slot in (1,2,3):
            other=key(day="20261121",slot=slot,race=11,channel="PC",market="quinella")
            self.assertTrue(self.a.claim(claim_key=other,owner="github_actions_1",
                            now_epoch=10000)["must_fetch"])
        tomorrow=key(day="20261122",slot=0,race=11,channel="PC",market="quinella")
        self.assertTrue(self.a.claim(claim_key=tomorrow,owner="github_actions_1",
                        now_epoch=10000)["must_fetch"])
    def test_generation_fence_rejects_old_worker(self):
        x=self.a.claim(claim_key=self.k,owner="github_actions_1",now_epoch=10000,lease_seconds=30)
        y=self.b.claim(claim_key=self.k,owner="streamlit_node_1",now_epoch=10031)
        self.assertTrue(y["must_fetch"])
        self.assertEqual(y["generation"],x["generation"]+1)
        self.assertFalse(self.a.complete(claim_key=self.k,owner="github_actions_1",
                         generation=x["generation"],sha256="a"*64)["committed"])
        self.assertTrue(self.b.complete(claim_key=self.k,owner="streamlit_node_1",
                        generation=y["generation"],sha256="b"*64)["committed"])
    def test_ambiguous_mutation_no_blind_retry(self):
        self.remote.fail_after_commit=True
        with self.assertRaisesRegex(TursoClaimUnconfirmed,"no_blind_retry"):
            self.a.claim(claim_key=self.k,owner="github_actions_1",now_epoch=10000)
        self.assertEqual(self.b.observe(self.k)["owner"],"github_actions_1")
        self.assertEqual(len([q for q in self.remote.history if
                              q["requests"][0]["stmt"]["sql"].startswith("INSERT")]),1)
    def test_wrong_remote_target_rejected(self):
        for url in ("https://example.com","file:///tmp/test.sqlite",
                    "libsql://evil.turso.io@other.org","https://production.turso.io/?role=admin"):
            with self.subTest(url=url),self.assertRaises(ReservationError):
                TursoCaptureClaims(url=url,token=TOKEN,transport=self.remote)
    def test_lab_namespace_is_disjoint_from_real_collector_table(self):
        lab=TursoCaptureClaims(url=URL,token=TOKEN,
             transport=self.remote,namespace="ISOLATED_LAB")
        lab.prepare_schema()
        x=lab.claim(claim_key=self.k,owner="lab_runner_001",now_epoch=10000)
        self.assertTrue(x["must_fetch"])
        self.assertIsNone(self.a.observe(self.k))
        self.assertTrue(self.a.claim(claim_key=self.k,owner="github_actions_1",
            now_epoch=10000)["must_fetch"])
        self.assertEqual(lab.observe(self.k)["owner"],"lab_runner_001")
        with sqlite3.connect(self.remote.path) as db:
            names={r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(names,{
            "__kyoto_ai_weekend_claims_v1",
            "__kyoto_ai_weekend_claims_isolated_lab_v1"})
    def test_lab_run_id_claim_never_allowed_in_operational_scope(self):
        lab=TursoCaptureClaims(url=URL,token=TOKEN,
            transport=self.remote,namespace="ISOLATED_LAB")
        lab.prepare_schema()
        lab_key="lab:44252070334:"+self.k
        self.assertTrue(lab.claim(claim_key=lab_key,
            owner="lab_runner_001",now_epoch=10000)["must_fetch"])
        with self.assertRaisesRegex(ReservationError,"claim_key"):
            self.a.claim(claim_key=lab_key,
                owner="github_actions_1",now_epoch=10000)
    def test_unrecognized_namespace_cannot_be_injected(self):
        with self.assertRaisesRegex(ReservationError,"namespace"):
            TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote,
                namespace="OPERATIONAL; DROP TABLE")
    def test_no_plain_sql_interpolated_user_input(self):
        self.a.claim(claim_key=self.k,owner="github_actions_1",now_epoch=10000)
        queries=[r["stmt"] for p in self.remote.history for r in p["requests"]
                 if r["type"]=="execute"]
        self.assertTrue(any(self.k in str(x["args"]) for x in queries))
        self.assertFalse(any(self.k in x["sql"] for x in queries))
if __name__=="__main__":unittest.main()
