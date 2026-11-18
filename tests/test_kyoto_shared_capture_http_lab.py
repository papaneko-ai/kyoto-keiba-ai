"""Two independent OS workers contend via TCP for one backend reservation."""
import multiprocessing as mp
import tempfile,threading,unittest
from pathlib import Path
from urllib.error import HTTPError
from diagnostics.kyoto_shared_capture_http_lab import create_server,request_claim
from diagnostics.kyoto_shared_capture_reservation import key
TOKEN="offline-shared-test-secret-20261118"
def worker(url,barrier,queue,index,claim_key):
    barrier.wait()
    response=request_claim(url,TOKEN,"claim",claim_key=claim_key,
                           owner="remote_agent_"+str(index),now_epoch=10000)
    queue.put((index,response))
class TestHttpCoordination(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.server=create_server("127.0.0.1",0,str(Path(t.name)/"remote_state.db"),TOKEN)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url=f"http://127.0.0.1:{self.server.server_address[1]}/capture-claim/v1"
        self.claim_key=key(day="20261121",slot=0,race=11,channel="PC",market="quinella")
    def test_two_process_remote_atomic_claim_one_http_request_owner(self):
        ctx=mp.get_context("spawn")
        barrier=ctx.Event();results=ctx.Queue()
        procs=[ctx.Process(target=worker,args=(self.url,barrier,results,i,self.claim_key)) for i in (11,22)]
        for p in procs:p.start()
        barrier.set()
        for p in procs:
            p.join(timeout=12)
            self.assertEqual(p.exitcode,0)
        claims=[results.get(timeout=3)[1] for _ in procs]
        self.assertEqual(sum(r["must_fetch"] for r in claims),1)
        self.assertEqual({r["state"] for r in claims},{"ACQUIRED","ACTIVE_LEASE"})
    def test_expired_owner_cannot_commit_remote_after_takeover(self):
        a=request_claim(self.url,TOKEN,"claim",claim_key=self.claim_key,
                        owner="remote_agent_1",now_epoch=10000,lease_seconds=30)
        b=request_claim(self.url,TOKEN,"claim",claim_key=self.claim_key,
                        owner="remote_agent_2",now_epoch=10031)
        self.assertTrue(b["must_fetch"])
        stale=request_claim(self.url,TOKEN,"complete",claim_key=self.claim_key,
            owner="remote_agent_1",generation=a["generation"],sha256="b"*64)
        self.assertFalse(stale["committed"])
        good=request_claim(self.url,TOKEN,"complete",claim_key=self.claim_key,
            owner="remote_agent_2",generation=b["generation"],sha256="c"*64)
        self.assertTrue(good["committed"])
    def test_each_schedule_slot_new_opportunity_not_blocked(self):
        for slot in range(4):
            entry=key(day="20261121",slot=slot,race=11,channel="PC",market="quinella")
            x=request_claim(self.url,TOKEN,"claim",claim_key=entry,
                            owner="remote_agent_3",now_epoch=10000)
            self.assertTrue(x["must_fetch"])
            self.assertTrue(request_claim(self.url,TOKEN,"complete",
                claim_key=entry,owner="remote_agent_3",
                generation=x["generation"],sha256="a"*64)["committed"])
        next_day=key(day="20261122",slot=0,race=11,channel="PC",market="quinella")
        self.assertTrue(request_claim(self.url,TOKEN,"claim",claim_key=next_day,
            owner="remote_agent_3",now_epoch=10000)["must_fetch"])
    def test_failed_slot_can_be_recovered_immediately(self):
        a=request_claim(self.url,TOKEN,"claim",claim_key=self.claim_key,
                        owner="remote_agent_1",now_epoch=10000)
        self.assertTrue(request_claim(self.url,TOKEN,"abandon",claim_key=self.claim_key,
                        owner="remote_agent_1",generation=a["generation"],
                        now_epoch=10000)["released"])
        self.assertTrue(request_claim(self.url,TOKEN,"claim",claim_key=self.claim_key,
            owner="remote_agent_2",now_epoch=10000)["must_fetch"])
    def test_invalid_authentication_cannot_claim(self):
        with self.assertRaises(HTTPError) as ctx:
            request_claim(self.url,"incorrect-secret","claim",claim_key=self.claim_key,
                          owner="remote_agent_4",now_epoch=10000)
        self.assertEqual(ctx.exception.code,401)
if __name__=="__main__":unittest.main()
