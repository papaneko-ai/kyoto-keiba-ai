"""R07 SP actual race-loop shared claim negative cases. Zero JRA/Turso HTTP."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from diagnostics.kyoto_sp_all12_observed_capture import capture_all
from diagnostics.kyoto_shared_capture_reservation import SharedLedger, key
from diagnostics.kyoto_weekend_sp_discovery import SEED
from tests.test_kyoto_sp_all12_observed_capture import link

DAY="20261121"


class CrossLaneSPTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"source"
        self.root.mkdir()
        self.ledger=SharedLedger(Path(tmp.name)/"coordinator.sqlite")
        self.addCleanup(self.ledger.close)
        raw=("<html><a href=\""+link(1)+"\">京都 1R</a></html>").encode("cp932")
        (self.root/"official_sp_discovery_1.html").write_bytes(raw)
        (self.root/"sp_discovery_receipt.json").write_text(json.dumps({
            "day":DAY,"attempts":[{"url":SEED,"file":"official_sp_discovery_1.html",
                                  "sha256":hashlib.sha256(raw).hexdigest()}]}))
        self.k=key(day=DAY,slot=0,race=1,channel="SHARED",market="racecard")
        self.calls=[]

    def fake(self, staging, *, race_number, source_url, **kwargs):
        self.calls.append((race_number,source_url))
        (Path(staging)/"official_sp_racecard.html").write_bytes(b"synthetic_official_sp_bytes")
        return {"state":"SP_ORIGINAL_CAPTURED_NOT_ROSTER_VERIFIED",
                "racecard_fetched":True,"network_requests_started":1}

    def capture(self, owner="github_sp_worker", client=None, suffix=None):
        with patch("diagnostics.kyoto_sp_all12_observed_capture.capture_verified_sp_seed",
                   side_effect=self.fake):
            return capture_all(self.root,day=DAY,opener=object(),pacer=Mock(),
                claim_client=client or self.ledger,claim_slot=0,claim_owner=owner,
                claim_now_epoch=10000)

    def test_pc_active_lease_blocks_sp_without_network(self):
        self.ledger.claim(claim_key=self.k,owner="github_pc_worker",now_epoch=10000)
        r=self.capture()
        self.assertEqual(self.calls,[])
        self.assertEqual(r["races"]["1"]["state"],"SP_SHARED_CLAIM_ALREADY_OWNED_OR_DONE")
        self.assertEqual(r["races"]["1"]["network_requests_started"],0)

    def test_pc_failure_release_allows_sp_to_complete_source_digest(self):
        pc=self.ledger.claim(claim_key=self.k,owner="github_pc_worker",now_epoch=10000)
        self.ledger.abandon(claim_key=self.k,owner="github_pc_worker",
                            generation=pc["generation"],now_epoch=10000)
        r=self.capture()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(r["races"]["1"]["claim_state"],"COMMITTED")
        saved=self.ledger.claim(claim_key=self.k,owner="github_other_worker",now_epoch=10001)
        self.assertEqual(saved["state"],"DONE_REUSE_EXISTING")
        self.assertEqual(saved["receipt_sha256"],hashlib.sha256(b"synthetic_official_sp_bytes").hexdigest())

    def test_remote_claim_failure_causes_zero_sp_race_http(self):
        class Broken:
            def claim(self,**kwargs):
                raise ConnectionError("synthetic coordinator outage")
        r=self.capture(client=Broken())
        self.assertEqual(self.calls,[])
        self.assertEqual(r["races"]["1"]["state"],"SP_SHARED_COORDINATOR_UNCONFIRMED_NO_HTTP")

    def test_missing_racecard_abandons_claim_for_recovery(self):
        def failed(staging,**kwargs):
            self.calls.append(("failed",kwargs["race_number"]))
            return {"state":"SOURCE_MISSING","racecard_fetched":False,
                    "network_requests_started":1}
        with patch("diagnostics.kyoto_sp_all12_observed_capture.capture_verified_sp_seed",side_effect=failed):
            r=capture_all(self.root,day=DAY,opener=object(),pacer=Mock(),
                          claim_client=self.ledger,claim_slot=0,claim_owner="github_sp_worker",
                          claim_now_epoch=10000)
        self.assertEqual(r["races"]["1"]["claim_state"],"ABANDONED_NO_VERIFIED_RACECARD")
        result=self.ledger.claim(claim_key=self.k,owner="github_next_worker",now_epoch=10000)
        self.assertTrue(result["must_fetch"])

if __name__=="__main__":
    unittest.main()
