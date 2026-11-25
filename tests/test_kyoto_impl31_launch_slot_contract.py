import unittest,tempfile
from datetime import datetime,timezone
from pathlib import Path
from diagnostics.kyoto_impl31_launch_slot_contract import resolve,market_key
from diagnostics.kyoto_impl31_launch_monitor import SLOTS
from diagnostics.kyoto_shared_capture_reservation import SharedLedger
D='20261128';T=datetime(2026,11,28,0,20,tzinfo=timezone.utc)
class Contract(unittest.TestCase):
    def test_same_slot_key_and_transactional_exclusion(self):
        a=resolve(D,'schedule',SLOTS[D][0],None,T)
        b=resolve(D,'workflow_dispatch','',0,T,external_verified=True)
        self.assertEqual(a,b)
        k=market_key(a,1,'PC','quinella');self.assertEqual(k,market_key(b,1,'PC','quinella'))
        with tempfile.TemporaryDirectory() as td:
            l=SharedLedger(Path(td)/'claims.db');self.addCleanup(l.close)
            x=l.claim(claim_key=k,owner='scheduled',now_epoch=1000)
            y=l.claim(claim_key=k,owner='external',now_epoch=1001)
            self.assertTrue(x['must_fetch']);self.assertFalse(y['must_fetch']);self.assertEqual(y['state'],'ACTIVE_LEASE')
            l.complete(claim_key=k,owner='scheduled',generation=x['generation'],sha256='a'*64)
            self.assertEqual(l.claim(claim_key=k,owner='external',now_epoch=1002)['state'],'DONE_REUSE_EXISTING')
            n=resolve(D,'schedule',SLOTS[D][1],None,datetime(2026,11,28,1,20,tzinfo=timezone.utc))
            self.assertTrue(l.claim(claim_key=market_key(n,1,'PC','quinella'),owner='scheduled',now_epoch=1003)['must_fetch'])
    def test_unverified_manual_rejected(self):
        with self.assertRaises(ValueError):resolve(D,'workflow_dispatch','',0,T)
    def test_wrong_slot_or_time_rejected(self):
        for x in (-1,True,4,1):
            with self.subTest(x=x),self.assertRaises(ValueError):resolve(D,'workflow_dispatch','',x,T,external_verified=True)
    def test_delayed_slot_not_silently_reassigned(self):
        with self.assertRaises(ValueError):resolve(D,'schedule',SLOTS[D][0],None,datetime(2026,11,28,1,16,tzinfo=timezone.utc))
    def test_no_authorization_from_contract(self):
        self.assertFalse(resolve(D,'workflow_dispatch','',0,T,external_verified=True)['production_dispatch_authorized'])
if __name__=='__main__':unittest.main()
