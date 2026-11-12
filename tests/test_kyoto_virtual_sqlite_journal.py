"""Offline repeatable SQLite crash/restart paper-ledger integration tests.

No actual JRA records, trades, passwords, network or Turso production.
"""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_virtual_sqlite_journal import (
    VirtualLedgerRejected, dashboard, freeze_virtual, initialize,
    record_lab_final,
)

def frozen(race="20261114-KYOTO-R01"):
    return {
        "race_id":race,"race_start_utc":"2026-11-14T05:00:00Z",
        "frozen_utc":"2026-11-14T04:20:00Z",
        "source_observed_utc":"2026-11-14T04:15:00Z",
        "source_sha256":"a"*64,"model_sha256":"b"*64,
        "model_version":"fixed-offline-lab-test","ticket_type":"QUINELLA",
        "tickets":[{"pair":[1,2],"stake_yen":100,"observed_odds":5.1},
                   {"pair":[3,4],"stake_yen":200,"observed_odds":13.4}],
        "daily_budget_yen":500,
        "provenance_scope":"UNAUTHENTICATED_LAB_INPUT"
    }
def final(version=1,payout=400):
    return {
        "race_id":"20261114-KYOTO-R01","result_version":version,
        "result_captured_utc":"2026-11-14T07:00:00Z",
        "result_sha256":("c" if version==1 else "d")*64,
        "result_scope":"UNAUTHENTICATED_LAB_FINAL",
        "payouts":[{"pair":[1,2],"yen_per_100":payout}],
        "refund_pairs":[]
    }
class DurableVirtualLedgerTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.path=Path(t.name)/"independent_lab.sqlite"

    def test_restart_and_sha_chain(self):
        x=freeze_virtual(self.path,frozen())
        self.assertEqual(x["status"],"APPENDED")
        a=dashboard(self.path)
        b=dashboard(self.path)
        self.assertEqual(a,b)
        self.assertEqual(a["frozen_races"],1)
        self.assertEqual(a["unsettled_races"],1)
        self.assertIsNone(a["settled_roi_percent"])
        self.assertIsNone(a["races"][0]["profit_yen"])
        self.assertEqual(a["chain_head"],x["entry_sha256"])

    def test_immutable_duplicate_replay(self):
        x=freeze_virtual(self.path,frozen())
        y=freeze_virtual(self.path,frozen())
        self.assertEqual(y["status"],"ALREADY_PRESENT")
        self.assertEqual(dashboard(self.path)["event_count"],1)
        self.assertEqual(x["entry_sha256"],y["entry_sha256"])

    def test_conflicting_duplicate_denied(self):
        freeze_virtual(self.path,frozen())
        other=frozen()
        other["tickets"][0]["stake_yen"]=200
        with self.assertRaises(VirtualLedgerRejected):
            freeze_virtual(self.path,other)
        self.assertEqual(dashboard(self.path)["event_count"],1)

    def test_cutoff_and_future_source_denied(self):
        for key,value in (
            ("frozen_utc","2026-11-14T04:55:00Z"),
            ("frozen_utc","2026-11-14T05:01:00Z"),
            ("source_observed_utc","2026-11-14T04:30:00Z"),
        ):
            with self.subTest(key=key,value=value):
                p=frozen();p[key]=value
                with self.assertRaises(VirtualLedgerRejected):
                    freeze_virtual(self.path,p)
        self.assertFalse(self.path.exists())

    def test_no_real_source_certification_in_lab(self):
        p=frozen()
        p["provenance_scope"]="LIVE_JRA"
        with self.assertRaises(VirtualLedgerRejected):
            freeze_virtual(self.path,p)

    def test_no_real_ticket_purchase(self):
        p=frozen()
        p["ticket_type"]="REAL"
        with self.assertRaises(VirtualLedgerRejected):
            freeze_virtual(self.path,p)

    def test_100yen_budget_and_pair_bounds(self):
        for change in (
            lambda p:p.update(daily_budget_yen=200),
            lambda p:p["tickets"][0].update(stake_yen=125),
            lambda p:p["tickets"][0].update(pair=[2,1]),
            lambda p:p["tickets"][0].update(pair=[1,1]),
            lambda p:p["tickets"][0].update(observed_odds=float("nan")),
        ):
            p=frozen();change(p)
            with self.assertRaises(VirtualLedgerRejected):freeze_virtual(self.path,p)

    def test_lab_final_settlement_and_restart(self):
        freeze_virtual(self.path,frozen())
        record_lab_final(self.path,final())
        a=dashboard(self.path);b=dashboard(self.path)
        self.assertEqual(a,b)
        self.assertEqual(a["settled_races"],1)
        self.assertEqual(a["settled_stake_yen"],300)
        self.assertEqual(a["settled_return_yen"],400)
        self.assertEqual(a["settled_profit_yen"],100)
        self.assertAlmostEqual(a["settled_roi_percent"],133.333,places=3)
        self.assertEqual(a["hit_ticket_count"],1)

    def test_duplicate_final_does_not_double_count(self):
        freeze_virtual(self.path,frozen())
        record_lab_final(self.path,final())
        r=record_lab_final(self.path,final())
        self.assertEqual(r["status"],"ALREADY_PRESENT")
        self.assertEqual(dashboard(self.path)["event_count"],2)

    def test_correction_replaces_not_adds(self):
        freeze_virtual(self.path,frozen())
        record_lab_final(self.path,final(1,400))
        record_lab_final(self.path,final(2,700))
        r=dashboard(self.path)
        self.assertEqual(r["settled_return_yen"],700)
        self.assertEqual(r["settled_profit_yen"],400)
        self.assertEqual(r["event_count"],3)
        self.assertEqual(r["races"][0]["final_version"],2)

    def test_out_of_order_final_denied(self):
        freeze_virtual(self.path,frozen())
        with self.assertRaises(VirtualLedgerRejected):
            record_lab_final(self.path,final(2))
        self.assertEqual(dashboard(self.path)["event_count"],1)

    def test_result_before_freeze_denied(self):
        with self.assertRaises(VirtualLedgerRejected):
            record_lab_final(self.path,final())

    def test_result_before_start_denied(self):
        freeze_virtual(self.path,frozen())
        r=final()
        r["result_captured_utc"]="2026-11-14T04:59:00Z"
        with self.assertRaises(VirtualLedgerRejected):
            record_lab_final(self.path,r)

    def test_refund_is_return_not_hit(self):
        freeze_virtual(self.path,frozen())
        r=final()
        r["payouts"]=[]
        r["refund_pairs"]=[[1,2]]
        record_lab_final(self.path,r)
        result=dashboard(self.path)
        self.assertEqual(result["settled_return_yen"],100)
        self.assertEqual(result["hit_ticket_count"],0)

    def test_tamper_protected_by_sql_trigger(self):
        freeze_virtual(self.path,frozen())
        with sqlite3.connect(self.path) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE events SET payload='{}' WHERE event_seq=1")
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("DELETE FROM events")

    def test_hash_chain_detects_admin_tampering_even_if_trigger_removed(self):
        freeze_virtual(self.path,frozen())
        with sqlite3.connect(self.path) as c:
            c.execute("DROP TRIGGER no_modify_events")
            c.execute("UPDATE events SET payload='{}' WHERE event_seq=1")
        with self.assertRaises(VirtualLedgerRejected):
            dashboard(self.path)

    def test_unknown_schema_rejected(self):
        p=frozen();p["unknown"]="surprise"
        with self.assertRaises(VirtualLedgerRejected):
            freeze_virtual(self.path,p)

if __name__=="__main__":
    unittest.main()
