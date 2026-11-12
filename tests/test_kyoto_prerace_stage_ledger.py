"""Offline stage sequencing, persistence, tampering and budget tests."""
import sqlite3, tempfile, unittest
from pathlib import Path
from diagnostics.kyoto_prerace_stage_ledger import StageLedger,StageError
RACE="20261114_KYOTO_R01"
START="2026-11-14T01:00:00Z"
DATES=("2026-11-12T08:00:00Z","2026-11-13T04:00:00Z","2026-11-13T23:00:00Z","2026-11-14T00:30:00Z")
STAGES=("ENTRIES","NUMBERED","MARKET","LAB_FREEZE")
def payload(stage):
    return {"race_id":RACE,"race_start_utc":START,"scope":"SYNTHETIC_LAB_ONLY","stage":stage}
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"proof.sqlite"
        self.s=StageLedger(self.path)
    def tearDown(self):
        self.s.close();self.tmp.cleanup()
    def add(self,i,p=None,raw=None):
        return self.s.append(race_id=RACE,stage=STAGES[i],captured_utc=DATES[i],
            start_utc=START,raw=(STAGES[i]+"-synthetic").encode() if raw is None else raw,
            payload=payload(STAGES[i]) if p is None else p)
    def first3(self):
        for i in range(3):self.add(i)
    def freeze(self,**kw):
        p={**payload("LAB_FREEZE"),"real_purchase":False,"source_verified_live":False,
            "market_record_sha256":self.s.read(RACE)[-1]["record_sha256"],
            "daily_budget_yen":500,"tickets":[{"stake_yen":200},{"stake_yen":100}]}
        p.update(kw)
        return self.add(3,p)
    def test_01_full_4stage(self):
        self.first3();self.assertEqual(self.freeze()["status"],"APPENDED")
        self.assertEqual([r["stage"] for r in self.s.read(RACE)],list(STAGES))
    def test_02_persistent_reopen(self):
        self.first3();self.freeze();self.s.close();self.s=StageLedger(self.path)
        self.assertEqual(len(self.s.read(RACE)),4)
    def test_03_out_of_order(self):
        with self.assertRaisesRegex(StageError,"OUT_OF_ORDER"):self.add(2)
    def test_04_immutable_source(self):
        self.add(0)
        with self.assertRaisesRegex(StageError,"IMMUTABLE_CONFLICT"):self.add(0,raw=b"changed")
    def test_05_identical_replay(self):
        self.add(0);self.assertEqual(self.add(0)["status"],"ALREADY_PRESENT")
    def test_06_after_start(self):
        with self.assertRaisesRegex(StageError,"POST_START"):
            self.s.append(race_id=RACE,stage="ENTRIES",captured_utc=START,start_utc=START,raw=b"a",payload=payload("ENTRIES"))
    def test_07_real_data_refused(self):
        p={**payload("ENTRIES"),"scope":"REAL_JRA"}
        with self.assertRaisesRegex(StageError,"REAL_SOURCE_NOT_APPROVED"):self.add(0,p)
    def test_08_budget_exceeded(self):
        self.first3()
        with self.assertRaisesRegex(StageError,"BUDGET_EXCEEDED"):self.freeze(daily_budget_yen=100)
    def test_09_wrong_market(self):
        self.first3()
        with self.assertRaisesRegex(StageError,"MARKET_BINDING_MISMATCH"):self.freeze(market_record_sha256="0"*64)
    def test_10_real_bet_refused(self):
        self.first3()
        with self.assertRaisesRegex(StageError,"LAB_ONLY"):self.freeze(real_purchase=True)
    def test_11_no_update(self):
        self.add(0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.conn.execute("UPDATE stages SET stage='MARKET'")
    def test_12_no_delete(self):
        self.add(0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.conn.execute("DELETE FROM stages")
if __name__=="__main__":unittest.main()
