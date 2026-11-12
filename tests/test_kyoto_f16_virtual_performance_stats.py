"""F16 contract: multi-race profit/ROI, max drawdown, version/refund and integrity."""
import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_virtual_sqlite_journal import (
    freeze_virtual, record_lab_final, dashboard, VirtualLedgerRejected
)
from diagnostics.kyoto_f16_virtual_performance_stats import (
    summarize_lab_journal,StatsRejected
)
def freeze(race,market="QUINELLA",model="MODEL-A"):
    pairs=[[1,2],[3,4]] if market=="QUINELLA" else [[1,1],[2,3]]
    return dict(race_id=f"20261114-KYOTO-R{race:02d}",
      race_start_utc="2026-11-14T05:00:00Z",
      frozen_utc="2026-11-14T04:20:00Z",
      source_observed_utc="2026-11-14T04:15:00Z",
      source_sha256="a"*64,model_sha256="b"*64,model_version=model,
      ticket_type=market,daily_budget_yen=1000,
      provenance_scope="UNAUTHENTICATED_LAB_INPUT",
      tickets=[dict(pair=p,stake_yen=100,observed_odds=9.0) for p in pairs])
def final(race,version=1,payout=0,market="QUINELLA",refund=False):
    pair=[1,2] if market=="QUINELLA" else [1,1]
    return dict(race_id=f"20261114-KYOTO-R{race:02d}",
      result_version=version,result_captured_utc="2026-11-14T07:00:00Z",
      result_sha256=(hex((race+version)%16)[2:]*64),
      result_scope="UNAUTHENTICATED_LAB_FINAL",
      payouts=([dict(pair=pair,yen_per_100=payout)] if payout else []),
      refund_pairs=([pair] if refund else []))
def make(db):
    freeze_virtual(db,freeze(1))
    freeze_virtual(db,freeze(2,model="MODEL-B"))
    freeze_virtual(db,freeze(3,market="BRACKET"))
    freeze_virtual(db,freeze(4,model="MODEL-A"))
    record_lab_final(db,final(1,payout=600))
    record_lab_final(db,final(2,payout=0))
    record_lab_final(db,final(3,payout=0,market="BRACKET",refund=True))
    record_lab_final(db,final(3,version=2,payout=900,market="BRACKET"))
    return summarize_lab_journal(db)
class F16StatisticsTests(unittest.TestCase):
 def setUp(self):
    t=tempfile.TemporaryDirectory()
    self.addCleanup(t.cleanup)
    self.path=Path(t.name)/"virtual_lab.sqlite"
 def test_full_four_race_fixture(self):
    r=make(self.path)
    self.assertEqual(r["frozen_races"],4)
    self.assertEqual(r["settled_races"],3)
    self.assertEqual(r["unsettled_races_excluded_from_roi"],1)
    self.assertEqual(r["totals"]["stake_yen"],600)
    self.assertEqual(r["totals"]["return_yen"],1500)
    self.assertEqual(r["totals"]["profit_yen"],900)
    self.assertEqual(r["totals"]["hit_tickets"],2)
    self.assertEqual(r["totals"]["hit_races"],2)
    self.assertEqual(r["totals"]["settled_tickets"],6)
    self.assertEqual(r["max_realized_drawdown_yen"],200)
    self.assertEqual([x["profit_yen"] for x in r["chronological_settled_races"]],[400,-200,700])
 def test_model_breakdown(self):
    r=make(self.path)
    self.assertEqual(r["by_model_version"]["MODEL-A"]["settled_races"],2)
    self.assertEqual(r["by_model_version"]["MODEL-B"]["profit_yen"],-200)
 def test_market_breakdown(self):
    r=make(self.path)
    self.assertEqual(r["by_ticket_type"]["BRACKET"]["return_yen"],900)
    self.assertEqual(r["by_ticket_type"]["QUINELLA"]["stake_yen"],400)
 def test_roi_and_hit_rates(self):
    r=make(self.path)
    self.assertEqual(r["totals"]["roi_percent"],250.0)
    self.assertAlmostEqual(r["totals"]["race_hit_percent"],66.667,places=3)
    self.assertAlmostEqual(r["totals"]["ticket_hit_percent"],33.333,places=3)
 def test_latest_final_correction_not_double_counted(self):
    r=make(self.path)
    self.assertEqual(r["chronological_settled_races"][-1]["final_version"],2)
    self.assertEqual(r["chronological_settled_races"][-1]["return_yen"],900)
    self.assertTrue(r["corrected_versions_replace_earlier_results"])
 def test_unsettled_never_is_zero_payout(self):
    r=make(self.path)
    self.assertNotIn("20261114-KYOTO-R04",[x["race_id"] for x in r["chronological_settled_races"]])
    self.assertEqual(r["unsettled_races_excluded_from_roi"],1)
 def test_restart_idempotence(self):
    make(self.path)
    self.assertEqual(summarize_lab_journal(self.path),summarize_lab_journal(self.path))
 def test_duplicate_freeze_does_not_double_count(self):
    before=make(self.path)
    out=freeze_virtual(self.path,freeze(1))
    self.assertEqual(out["status"],"ALREADY_PRESENT")
    self.assertEqual(summarize_lab_journal(self.path),before)
 def test_duplicate_final_does_not_double_count(self):
    before=make(self.path)
    record_lab_final(self.path,final(3,version=2,payout=900,market="BRACKET"))
    self.assertEqual(summarize_lab_journal(self.path),before)
 def test_refund_not_hit(self):
    freeze_virtual(self.path,freeze(1))
    record_lab_final(self.path,final(1,refund=True))
    r=summarize_lab_journal(self.path)
    self.assertEqual(r["totals"]["return_yen"],100)
    self.assertEqual(r["totals"]["hit_races"],0)
    self.assertEqual(r["totals"]["hit_tickets"],0)
 def test_all_unsettled_rate_is_null(self):
    freeze_virtual(self.path,freeze(1))
    r=summarize_lab_journal(self.path)
    self.assertIsNone(r["totals"]["roi_percent"])
    self.assertIsNone(r["totals"]["ticket_hit_percent"])
    self.assertEqual(r["max_realized_drawdown_yen"],0)
 def test_empty_file_refused(self):
    with self.assertRaises(StatsRejected):summarize_lab_journal(self.path)
 def test_illegal_tamper_detected(self):
    make(self.path)
    with sqlite3.connect(self.path) as c:
        c.execute("DROP TRIGGER no_modify_events")
        c.execute("UPDATE events SET entry_sha256=? WHERE event_seq=1",("f"*64,))
    with self.assertRaises(VirtualLedgerRejected):
        summarize_lab_journal(self.path)
 def test_revised_result_updates_drawdown(self):
    make(self.path)
    record_lab_final(self.path,final(2,version=2,payout=300))
    r=summarize_lab_journal(self.path)
    self.assertEqual(r["max_realized_drawdown_yen"],0)
    self.assertEqual(r["totals"]["return_yen"],1800)
 def test_no_real_bet_claims(self):
    r=make(self.path)
    for k in ("live_jra_authenticity_verified","production_turso_persistence_verified",
              "real_paper_trade_stats_available","real_bet_authorized"):
        self.assertFalse(r[k])
 def test_sha_digest_stable(self):
    r=make(self.path)
    self.assertEqual(r["stats_sha256"],summarize_lab_journal(self.path)["stats_sha256"])
 def test_model_version_not_collapsed(self):
    r=make(self.path)
    self.assertEqual(set(r["by_model_version"]),{"MODEL-A","MODEL-B"})
 def test_cumulative_pnl_and_peak_drawdown(self):
    r=make(self.path)
    entries=r["chronological_settled_races"]
    self.assertEqual([x["cumulative_profit_yen"] for x in entries],[400,200,900])
    self.assertEqual([x["drawdown_from_peak_yen"] for x in entries],[0,200,0])
if __name__=="__main__":unittest.main()
