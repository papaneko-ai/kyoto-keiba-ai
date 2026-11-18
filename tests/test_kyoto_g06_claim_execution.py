"""G06 actual batch claim execution against an injectable shared remote ledger.

The mock collector uses saved synthetic originals only. Two independent
G06 invocations must not each start a source fetch for the same scheduled
slot; the next slot must still be available even after a completed first.
"""
from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.kyoto_shared_capture_reservation import SharedLedger
from tests.test_kyoto_g06_live_recovery_batch import records
from tests.test_kyoto_g06_item_level_recovery import setup

class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.db=SharedLedger(self.root/"shared.sqlite")
        self.addCleanup(self.db.close)
        self.calls=[]
    def collector(self,out,**kw):
        self.calls.append(kw["race_spec"].race_number)
        setup(out,"PC",["quinella"])
        setup(out,"SP",["bracket_quinella"])
        return {"state":"SOURCE_ONLY","selected_channel":None,
                "attempts":[{"channel":"PC","state":"SOURCE_FROZEN","reason":None}]}
    def execute_batch(self,name,slot=0,owner="github_actions_1",collector=None,client=None):
        with patch("diagnostics.kyoto_g06_all12_capture.capture_hybrid",
                   side_effect=collector or self.collector):
            return run_twelve(self.root/name,records=records(),
                   authorized_live_http=True,
                   claim_client=client or self.db,claim_slot=slot,
                   claim_owner=owner,claim_now_epoch=10000)
    def test_single_owned_slot_executes_one_race_once(self):
        first=self.execute_batch("run_first")
        second=self.execute_batch("run_second",owner="streamlit_node_1")
        self.assertEqual(self.calls,[11])
        self.assertEqual(first["verified_dual_market_races"],1)
        self.assertEqual(second["verified_dual_market_races"],0)
        self.assertEqual(second["records"][10]["state"],
                         "SHARED_SLOT_OWNED_OR_DONE_REUSE_NEXT_SLOT")
        self.assertEqual(first["records"][10]["claim_commit_state"],"COMMITTED")
    def test_next_slot_must_not_be_blocked_by_previous_success(self):
        self.execute_batch("run_first")
        second=self.execute_batch("run_next_slot",slot=1,owner="streamlit_node_1")
        self.assertEqual(self.calls,[11,11])
        self.assertEqual(second["verified_dual_market_races"],1)
    def test_failed_fetch_releases_same_slot_for_next_worker(self):
        def failure(out,**kw):
            self.calls.append(kw["race_spec"].race_number)
            raise TimeoutError("synthetic connection interrupted")
        first=self.execute_batch("first_timeout",collector=failure)
        self.assertEqual(first["verified_dual_market_races"],0)
        self.assertEqual(first["records"][10]["claim_commit_state"],
                         "RELEASED_FOR_RETRY")
        second=self.execute_batch("second_success",owner="streamlit_node_1")
        self.assertEqual(second["verified_dual_market_races"],1)
        self.assertEqual(self.calls,[11,11])
    def test_coordinator_unconfirmed_no_unleased_http(self):
        class Broken:
            def claim(self,**kw):raise ConnectionError("simulated remote unconfirmed")
        a=self.execute_batch("unconfirmed",client=Broken())
        self.assertEqual(self.calls,[])
        self.assertEqual(a["records"][10]["claim_state"],"COORDINATOR_UNCONFIRMED")
        self.assertFalse(a["records"][10]["both_markets_verified"])
    def test_unconfigured_coordinator_keeps_existing_capture_route(self):
        with patch("diagnostics.kyoto_g06_all12_capture.capture_hybrid",
                   side_effect=self.collector):
            result=run_twelve(self.root/"without_coordinator",
                records=records(),authorized_live_http=True)
        self.assertEqual(result["verified_dual_market_races"],1)
        self.assertEqual(self.calls,[11])
        self.assertNotIn("claim_state",result["records"][10])
if __name__=="__main__":unittest.main()
