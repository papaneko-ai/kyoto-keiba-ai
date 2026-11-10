"""RG-01B one continuous LAB computation with persisted freeze and correction."""
import copy
import tempfile
import unittest
from pathlib import Path
from diagnostics.rg01_prediction_freeze_settlement_lab import (
    freeze_research_prediction, settle_research_result,
    verify_research_restart, IntegratedLabRejected
)
from diagnostics.p6_virtual_settlement_fixture_lab import LabRejected

def args(ticket_type="QUINELLA"):
    strengths={1:4.0,2:3.0,3:2.0}
    frames={1:1,2:1,3:2}
    qs={(1,2):"20.0",(1,3):"20.0",(2,3):"20.0"}
    bs={(1,1):"20.0",(1,2):"20.0"}
    return {
        "scenario_id":"LAB-20261110-01",
        "ticket_type":ticket_type,
        "strengths":strengths, "frames":frames,
        "market":qs if ticket_type=="QUINELLA" else bs,
        "observed_utc":"2026-11-10T01:00:00Z",
        "frozen_utc":"2026-11-10T01:30:00Z",
        "cutoff_utc":"2026-11-10T02:00:00Z"
    }
class IntegratedSequence(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/"research-journal.jsonl"
    def freeze(self, **changes):
        a=args();a.update(changes)
        return freeze_research_prediction(self.path,**a)
    def settle(self, head, **changes):
        data={"expected_head":head,"version":1,"payout_per_100":{},
              "refunded_pairs":[],"event_utc":"2026-11-10T03:00:00Z"}
        data.update(changes)
        return settle_research_result(self.path,**data)
    def test_one_end_to_end_prediction_freeze_restart_final_settlement(self):
        f=self.freeze()
        self.assertEqual(f["state"],"LAB_FROZEN_UNSETTLED")
        before=verify_research_restart(self.path,expected_head=f["journal_head_sha256"])
        self.assertEqual(before["entries"],1)
        self.assertEqual(before["outcome"]["status"],"UNSETTLED")
        key="-".join(map(str,f["chosen_pair"]))
        final=self.settle(f["journal_head_sha256"],payout_per_100={key:750})
        self.assertEqual(final["state"],"FINAL_FIXTURE_ONLY")
        self.assertEqual(final["result"]["stake_yen"],100)
        self.assertEqual(final["result"]["payout_yen"],750)
        self.assertEqual(final["result"]["profit_yen"],650)
        after=verify_research_restart(self.path,expected_head=final["journal_head_sha256"])
        self.assertEqual(after["entries"],2)
        self.assertEqual(after["outcome"],final["result"])
        self.assertFalse(final["official_results_verified"])
        self.assertFalse(final["real_bet_authorized"])
    def test_bracket_same_frame_result(self):
        a=args("BRACKET")
        f=freeze_research_prediction(self.path,**a)
        self.assertEqual(f["ticket_type"],"BRACKET")
        key="-".join(map(str,f["chosen_pair"]))
        final=self.settle(f["journal_head_sha256"],payout_per_100={key:500})
        self.assertEqual(final["result"]["payout_yen"],500)
    def test_preliminary_never_counts_profit(self):
        f=self.freeze()
        provisional=self.settle(f["journal_head_sha256"],state="RESULT_PRELIMINARY")
        self.assertEqual(provisional["state"],"PRELIMINARY_UNSETTLED")
        self.assertIsNone(provisional["result"]["profit_yen"])
        final=self.settle(provisional["journal_head_sha256"],version=2)
        self.assertEqual(final["result"]["profit_yen"],-100)
    def test_final_correction_replaces_prior_not_add(self):
        f=self.freeze()
        key="-".join(map(str,f["chosen_pair"]))
        first=self.settle(f["journal_head_sha256"],payout_per_100={key:800})
        second=self.settle(first["journal_head_sha256"],version=2,
                            payout_per_100={key:400})
        self.assertEqual(first["result"]["payout_yen"],800)
        self.assertEqual(second["result"]["payout_yen"],400)
        self.assertEqual(second["result"]["profit_yen"],300)
    def test_same_scenario_repeated_freeze_rejected(self):
        self.freeze()
        with self.assertRaises(LabRejected):self.freeze()
    def test_stale_result_anchor_refused(self):
        f=self.freeze()
        with self.assertRaises(LabRejected):self.settle("0"*64)
    def test_result_cannot_arrive_before_cutoff(self):
        f=self.freeze()
        with self.assertRaisesRegex(IntegratedLabRejected,"result_before_race_cutoff"):
            self.settle(f["journal_head_sha256"],event_utc="2026-11-10T01:59:00Z")
    def test_market_cannot_be_observed_after_freeze(self):
        with self.assertRaisesRegex(IntegratedLabRejected,"post_cutoff_or_future_market"):
            self.freeze(observed_utc="2026-11-10T01:50:00Z")
    def test_missing_market_pair_refused(self):
        a=args();a["market"].pop((1,2))
        with self.assertRaisesRegex(Exception,"market_coverage_mismatch"):
            freeze_research_prediction(self.path,**a)
        self.assertFalse(self.path.exists())
    def test_synthetic_never_accepts_real_scenario(self):
        with self.assertRaisesRegex(IntegratedLabRejected,"lab_identity_required"):
            self.freeze(scenario_id="KYOTO-LIVE")
    def test_no_ev_skips_without_fake_freeze(self):
        a=args();a["market"]={k:"1.01" for k in a["market"]}
        out=freeze_research_prediction(self.path,**a)
        self.assertEqual(out["state"],"LAB_NO_BET")
        self.assertFalse(self.path.exists())
    def test_tampered_journal_fails_replay(self):
        f=self.freeze()
        original=self.path.read_bytes()
        self.path.write_bytes(original.replace(b"LAB-PL-NOT-CALIBRATED",b"LAB-PL-NOT-CALIBRATEX"))
        with self.assertRaises(LabRejected):
            verify_research_restart(self.path,expected_head=f["journal_head_sha256"])
    def test_duplicate_result_cannot_be_appended(self):
        f=self.freeze()
        first=self.settle(f["journal_head_sha256"])
        with self.assertRaises(LabRejected):
            self.settle(first["journal_head_sha256"])
    def test_final_to_preliminary_blocked(self):
        f=self.freeze()
        final=self.settle(f["journal_head_sha256"])
        with self.assertRaises(LabRejected):
            self.settle(final["journal_head_sha256"],version=2,state="RESULT_PRELIMINARY")
if __name__=="__main__":unittest.main()
