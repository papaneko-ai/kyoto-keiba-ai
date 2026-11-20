"""R07 focused negative tests: PC and SP must not own distinct logical G06 claims.

No Turso credentials, no JRA HTTP, no schema writes on production.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from diagnostics.kyoto_shared_capture_reservation import SharedLedger, key, ReservationError
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
from tests.test_kyoto_turso_capture_claims import FakeRemote, URL, TOKEN


class CrossLaneLeaseTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.path=Path(t.name)/"remote.sqlite"
        self.remote=FakeRemote(self.path)
        self.pc=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote)
        self.sp=TursoCaptureClaims(url=URL,token=TOKEN,transport=self.remote)
        self.pc.prepare_schema()

    def shared(self,slot=0,race=11,market="racecard"):
        return key(day="20261121",slot=slot,race=race,
                   channel="SHARED",market=market)

    def test_same_shared_key_cross_channel_remote_atomic_exclusion(self):
        k=self.shared()
        first=self.pc.claim(claim_key=k,owner="github_pc_worker",now_epoch=10000)
        second=self.sp.claim(claim_key=k,owner="github_sp_worker",now_epoch=10000)
        self.assertTrue(first["must_fetch"])
        self.assertEqual(second["state"],"ACTIVE_LEASE")
        self.assertFalse(second["must_fetch"])

    def test_failed_pc_release_allows_sp_takeover_in_same_slot(self):
        k=self.shared()
        first=self.pc.claim(claim_key=k,owner="github_pc_worker",now_epoch=10000)
        self.assertTrue(self.pc.abandon(claim_key=k,owner="github_pc_worker",
                        generation=first["generation"],now_epoch=10000)["released"])
        second=self.sp.claim(claim_key=k,owner="github_sp_worker",now_epoch=10000)
        self.assertTrue(second["must_fetch"])
        self.assertGreater(second["generation"],first["generation"])
        self.assertFalse(self.pc.complete(claim_key=k,owner="github_pc_worker",
                         generation=first["generation"],sha256="a"*64)["committed"])

    def test_successful_pc_lease_cannot_be_reused_as_new_sp_fetch(self):
        k=self.shared()
        first=self.pc.claim(claim_key=k,owner="github_pc_worker",now_epoch=10000)
        self.assertTrue(self.pc.complete(claim_key=k,owner="github_pc_worker",
                        generation=first["generation"],sha256="a"*64)["committed"])
        second=self.sp.claim(claim_key=k,owner="github_sp_worker",now_epoch=10001)
        self.assertEqual(second["state"],"DONE_REUSE_EXISTING")
        self.assertFalse(second["must_fetch"])

    def test_day_slot_race_and_market_isolation(self):
        base=self.shared()
        self.assertTrue(self.pc.claim(claim_key=base,owner="github_pc_worker",now_epoch=10000)["must_fetch"])
        for candidate in (self.shared(slot=1),self.shared(race=10),
                          self.shared(market="quinella"),
                          key(day="20261122",slot=0,race=11,channel="SHARED",market="racecard")):
            self.assertTrue(self.sp.claim(claim_key=candidate,
                            owner="github_sp_worker",now_epoch=10000)["must_fetch"])

    def test_legacy_channel_key_retained_for_compatibility(self):
        pc=key(day="20261121",slot=0,race=11,channel="PC",market="racecard")
        sp=key(day="20261121",slot=0,race=11,channel="SP",market="racecard")
        self.assertNotEqual(pc,sp)
        self.assertEqual(pc,"20261121:0:11:PC:racecard")
        self.assertEqual(sp,"20261121:0:11:SP:racecard")
        self.assertNotEqual(self.shared(),pc)

    def test_g06_claim_uses_shared_identity_only_when_coordinator_selected(self):
        from diagnostics.kyoto_g06_all12_capture import run_twelve
        from unittest.mock import patch
        from tests.test_kyoto_g06_claim_execution import records
        from tests.test_kyoto_g06_full_twelve_reparse_e2e import capture_mock
        with tempfile.TemporaryDirectory() as root:
            temp=Path(root)
            ledger=SharedLedger(temp/"leases.sqlite")
            self.addCleanup(ledger.close)
            observed=[]
            orig_claim=ledger.claim
            def watch(**kw):
                observed.append(kw["claim_key"])
                return orig_claim(**kw)
            with patch("diagnostics.kyoto_g06_all12_capture.capture_hybrid",
                       side_effect=capture_mock):
                with patch.object(ledger,"claim",side_effect=watch):
                    run_twelve(temp/"batch",records=records(),authorized_live_http=True,
                               claim_client=ledger,claim_slot=0,claim_owner="github_pc_worker",
                               claim_now_epoch=10000)
            self.assertEqual(observed,[self.shared()])

if __name__=="__main__":
    unittest.main()
