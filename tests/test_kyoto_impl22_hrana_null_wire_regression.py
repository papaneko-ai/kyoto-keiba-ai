"""Regression for the exact Hrana NULL wire format that blocked run 44442325455."""
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_turso_capture_claims import (
    TursoCaptureClaims, TursoClaimUnconfirmed, _rows, _cell
)
from diagnostics.kyoto_shared_capture_reservation import key
from tests.test_kyoto_turso_capture_claims import FakeRemote, URL, TOKEN

class HranaNullWireTests(unittest.TestCase):
    def test_null_has_no_value_field(self):
        self.assertEqual(_rows({"rows":[[
            {"type":"text","value":"runner_a"},
            {"type":"integer","value":"1"},
            {"type":"integer","value":"1800"},
            {"type":"text","value":"LEASED"},
            {"type":"null"}
        ]]}),[["runner_a","1","1800","LEASED",None]])
    def test_invalid_cell_remains_closed(self):
        for cell in ({"type":"null","value":"should-not-exist"},
                     {"type":"text"},{"type":"integer","value":42},
                     {"type":"blob","base64":"AA=="},{}):
            with self.subTest(cell=cell),self.assertRaises(TursoClaimUnconfirmed):
                _rows({"rows":[[cell]]})
    def test_two_independent_clients_complete_and_reuse(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        db=FakeRemote(Path(tmp.name)/"remote.sqlite")
        a=TursoCaptureClaims(url=URL,token=TOKEN,transport=db,namespace="ISOLATED_LAB")
        b=TursoCaptureClaims(url=URL,token=TOKEN,transport=db,namespace="ISOLATED_LAB")
        a.prepare_schema()
        claim_key="lab:44442325455:"+key(day="20261121",slot=0,race=1,channel="PC",market="racecard")
        first=a.claim(claim_key=claim_key,owner="lab_first",now_epoch=15000)
        second=b.claim(claim_key=claim_key,owner="lab_second",now_epoch=15000)
        self.assertEqual(first["state"],"ACQUIRED")
        self.assertEqual(second["state"],"ACTIVE_LEASE")
        self.assertFalse(second["must_fetch"])
        observation=b.observe(claim_key)
        self.assertIsNone(observation["receipt_sha256"])
        self.assertTrue(a.complete(claim_key=claim_key,owner="lab_first",
            generation=first["generation"],sha256="b"*64)["committed"])
        third=b.claim(claim_key=claim_key,owner="lab_third",now_epoch=15001)
        self.assertEqual(third["state"],"DONE_REUSE_EXISTING")
        self.assertFalse(third["must_fetch"])
        self.assertEqual(third["receipt_sha256"],"b"*64)

if __name__=="__main__":
    unittest.main()
