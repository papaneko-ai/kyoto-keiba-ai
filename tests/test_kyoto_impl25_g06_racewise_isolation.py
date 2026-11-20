"""Per-race G03 integrity failure must not cancel valid G06 market inputs."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
from diagnostics.jra_one_shot_market_capture import SourceChainError

DAY="20261121"

class FakeSpec:
    def __init__(self,day,race_number,*a):
        self.race_day=day
        self.race_number=race_number
    def validate(self,*,require_channels):
        assert require_channels==("PC",)

def sample(race,root):
    raw=(f"JRA_OFFICIAL_OFFLINE_FIXTURE_{race}").encode()
    (root/f"g03_official_racecard_{race:02d}.html").write_bytes(raw)
    return {"state":"ROSTER_AND_START_VERIFIED_OFFLINE",
        "original_file":f"official_racecard_{race:02d}.html",
        "original_sha256":hashlib.sha256(raw).hexdigest(),
        "captured_at_utc":"2026-11-21T00:20:00+00:00",
        "start_time_jst":"10:00",
        "source_url":f"https://jra.jp/offline-fixture/{race}",
        "runners":[{"number":1,"frame":1,"name":"TEST_A"},
                   {"number":2,"frame":2,"name":"TEST_B"}]}

class RacewiseG06InputIsolation(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        entries={str(i):{"state":"OFFICIAL_LINK_NOT_OBSERVED"} for i in range(1,13)}
        entries["1"]=sample(1,self.root)
        entries["2"]=sample(2,self.root)
        self.report={"schema":"kyoto_g03_all_races.v1","day":DAY,"races":entries}
        self.flush()

    def flush(self):
        (self.root/"g03_receipt.json").write_text(json.dumps(self.report))

    def run_adapter(self,**kwargs):
        with patch("diagnostics.kyoto_g03_to_g06_input_adapter.normal_sales_open",
                   return_value=datetime(2026,11,21,tzinfo=timezone.utc)),patch(
                   "diagnostics.kyoto_g03_to_g06_input_adapter.ObservedRaceSpec",FakeSpec):
            return records_from_g03(self.root,day=DAY,**kwargs)

    def test_one_tampered_race_does_not_block_other_eleven_slots(self):
        (self.root/"g03_official_racecard_01.html").write_bytes(b"TAMPERED")
        rejected={}
        records=self.run_adapter(skip_invalid_races=True,rejections=rejected)
        self.assertIsNone(records[1])
        self.assertIsNotNone(records[2])
        self.assertEqual(set(records),set(range(1,13)))
        self.assertEqual(set(rejected),{"1"})
        self.assertEqual(rejected["1"]["reason_code"],"g03_original_sha_mismatch")

    def test_default_strict_contract_still_rejects_tampering(self):
        (self.root/"g03_official_racecard_01.html").write_bytes(b"TAMPERED")
        with self.assertRaisesRegex(SourceChainError,"g03_original_sha_mismatch"):
            self.run_adapter()

    def test_source_after_start_quarantined_not_promoted(self):
        self.report["races"]["1"]["captured_at_utc"]="2026-11-21T01:01:00Z"
        self.flush()
        result=self.run_adapter(skip_invalid_races=True,rejections={})
        self.assertIsNone(result[1])
        self.assertIsNotNone(result[2])

    def test_corrupt_identity_does_not_break_other_races(self):
        self.report["races"]["1"]["runners"][1]["frame"]=9
        self.flush()
        rejected={}
        r=self.run_adapter(skip_invalid_races=True,rejections=rejected)
        self.assertIsNone(r[1])
        self.assertIsNotNone(r[2])
        self.assertEqual(rejected["1"]["reason_code"],"g03_roster_not_named")

    def test_global_day_mismatch_still_fails_closed(self):
        self.report["day"]="20261122"
        self.flush()
        with self.assertRaisesRegex(SourceChainError,"g03_receipt_day_mismatch"):
            self.run_adapter(skip_invalid_races=True)

    def test_global_schema_mismatch_still_fails_closed(self):
        self.report["schema"]="invented"
        self.flush()
        with self.assertRaisesRegex(SourceChainError,"g03_receipt_day_mismatch"):
            self.run_adapter(skip_invalid_races=True)

    def test_unsafe_symlink_race_rejected_and_peer_available(self):
        (self.root/"g03_official_racecard_01.html").unlink()
        (self.root/"g03_official_racecard_01.html").symlink_to(
            self.root/"g03_official_racecard_02.html")
        rejected={}
        result=self.run_adapter(skip_invalid_races=True,rejections=rejected)
        self.assertIsNone(result[1])
        self.assertIsNotNone(result[2])
        self.assertIn("1",rejected)

    def test_invalid_isolation_type_fail_closed(self):
        with self.assertRaisesRegex(SourceChainError,"race_isolation_flag_invalid"):
            self.run_adapter(skip_invalid_races="true")

if __name__=="__main__":
    unittest.main()
