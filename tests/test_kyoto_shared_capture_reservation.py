"""Adversarial multi-process transactional source acquisition lease tests."""
import multiprocessing as mp
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_shared_capture_reservation import SharedLedger,key,ReservationError

def worker(db,gate,answers,owner,claim_key):
    ledger=SharedLedger(db)
    gate.wait()
    result=ledger.claim(claim_key=claim_key,owner=owner,now_epoch=10000)
    answers.put((owner,result))
    ledger.close()

class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.db=str(Path(t.name)/"shared.sqlite")
        l=SharedLedger(self.db);l.close()
        self.k=key(day="20261121",slot=0,race=11,channel="PC",market="quinella")
    def test_two_process_race_only_one_owner(self):
        ctx=mp.get_context("spawn")
        gate=ctx.Event();results=ctx.Queue()
        processes=[ctx.Process(target=worker,args=(self.db,gate,results,"agent_"+str(i).zfill(3),self.k)) for i in range(2)]
        for p in processes:p.start()
        gate.set()
        for p in processes:
            p.join(timeout=15)
            self.assertEqual(p.exitcode,0)
        data=[results.get(timeout=3) for p in processes]
        self.assertEqual(sum(x["must_fetch"] for _,x in data),1)
        self.assertEqual(set(x["state"] for _,x in data),{"ACQUIRED","ACTIVE_LEASE"})
    def test_other_slot_not_blocked_after_completion(self):
        l=SharedLedger(self.db)
        a=l.claim(claim_key=self.k,owner="agent_001",now_epoch=10000)
        self.assertTrue(l.complete(claim_key=self.k,owner="agent_001",generation=a["generation"],sha256="b"*64)["committed"])
        same=l.claim(claim_key=self.k,owner="agent_002",now_epoch=10001)
        self.assertEqual(same["state"],"DONE_REUSE_EXISTING")
        for slot in (1,2,3):
            k=key(day="20261121",slot=slot,race=11,channel="PC",market="quinella")
            self.assertTrue(l.claim(claim_key=k,owner="agent_002",now_epoch=10001)["must_fetch"])
        sunday=key(day="20261122",slot=0,race=11,channel="PC",market="quinella")
        self.assertTrue(l.claim(claim_key=sunday,owner="agent_002",now_epoch=10001)["must_fetch"])
        l.close()
    def test_stale_owner_fenced_after_expiration(self):
        l=SharedLedger(self.db)
        first=l.claim(claim_key=self.k,owner="agent_001",now_epoch=10000,lease_seconds=30)
        second=l.claim(claim_key=self.k,owner="agent_002",now_epoch=10031)
        self.assertEqual(second["generation"],first["generation"]+1)
        self.assertFalse(l.complete(claim_key=self.k,owner="agent_001",generation=1,sha256="b"*64)["committed"])
        self.assertTrue(l.complete(claim_key=self.k,owner="agent_002",generation=2,sha256="c"*64)["committed"])
        l.close()
    def test_failed_fetch_released_for_same_slot(self):
        l=SharedLedger(self.db)
        first=l.claim(claim_key=self.k,owner="agent_001",now_epoch=10000)
        self.assertTrue(l.abandon(claim_key=self.k,owner="agent_001",generation=first["generation"],now_epoch=10000)["released"])
        retry=l.claim(claim_key=self.k,owner="agent_002",now_epoch=10000)
        self.assertTrue(retry["must_fetch"])
        self.assertFalse(l.complete(claim_key=self.k,owner="agent_001",generation=1,sha256="f"*64)["committed"])
        l.close()
    def test_separate_market_and_pc_sp_never_collapse(self):
        l=SharedLedger(self.db)
        self.assertTrue(l.claim(claim_key=self.k,owner="agent_001",now_epoch=10000)["must_fetch"])
        for market,channel in (("bracket_quinella","PC"),("quinella","SP")):
            k=key(day="20261121",slot=0,race=11,channel=channel,market=market)
            self.assertTrue(l.claim(claim_key=k,owner="agent_002",now_epoch=10000)["must_fetch"])
        l.close()
    def test_wrong_day_or_source_refused(self):
        for day,channel,market in (("20261123","PC","quinella"),("20261121","XX","quinella"),("20261121","PC","OTHER")):
            with self.assertRaises(ReservationError):
                key(day=day,slot=0,race=11,channel=channel,market=market)
    def test_wrong_owner_cannot_commit(self):
        l=SharedLedger(self.db)
        a=l.claim(claim_key=self.k,owner="agent_001",now_epoch=10000)
        self.assertFalse(l.complete(claim_key=self.k,owner="agent_002",generation=a["generation"],sha256="b"*64)["committed"])
        l.close()
if __name__=="__main__":unittest.main()
