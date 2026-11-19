"""Prevent same-slot reacquisition while a 20-minute GitHub capture may still run."""
import tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_shared_capture_reservation import SharedLedger,key
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
from tests.test_kyoto_turso_capture_claims import FakeRemote,URL,TOKEN

class Tests(unittest.TestCase):
    def exercise(self,client_a,client_b):
        first=key(day="20261121",slot=0,race=11,channel="PC",market="racecard")
        next_slot=key(day="20261121",slot=1,race=11,channel="PC",market="racecard")
        a=client_a.claim(claim_key=first,owner="github_first",now_epoch=10000,lease_seconds=1800)
        self.assertTrue(a["must_fetch"])
        # Old 600s lease would let a second runner re-fetch at t+601.
        b=client_b.claim(claim_key=first,owner="github_second",now_epoch=10601,lease_seconds=1800)
        self.assertFalse(b["must_fetch"])
        self.assertEqual(b["state"],"ACTIVE_LEASE")
        # Each new scheduled window still gets an independent opportunity.
        c=client_b.claim(claim_key=next_slot,owner="github_second",now_epoch=10601,lease_seconds=1800)
        self.assertTrue(c["must_fetch"])
        # A previous completed fetch cannot be replayed in the same slot.
        self.assertTrue(client_a.complete(claim_key=first,owner="github_first",
                        generation=a["generation"],sha256="a"*64)["committed"])
        d=client_b.claim(claim_key=first,owner="github_second",now_epoch=11801,lease_seconds=1800)
        self.assertFalse(d["must_fetch"])
        self.assertEqual(d["state"],"DONE_REUSE_EXISTING")
    def test_sqlite_protocol(self):
        with tempfile.TemporaryDirectory() as root:
            a=SharedLedger(Path(root)/"ledger.sqlite")
            b=SharedLedger(Path(root)/"ledger.sqlite")
            try:self.exercise(a,b)
            finally:a.close();b.close()
    def test_turso_hrana_transport_protocol_offline(self):
        with tempfile.TemporaryDirectory() as root:
            remote=FakeRemote(Path(root)/"remote.sqlite")
            a=TursoCaptureClaims(url=URL,token=TOKEN,transport=remote)
            b=TursoCaptureClaims(url=URL,token=TOKEN,transport=remote)
            a.prepare_schema()
            self.exercise(a,b)
if __name__=="__main__":unittest.main()
