"""RG03B destructive integration: sealed P6 journals -> genuinely earlier LAB folds."""
import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from diagnostics.rg01_prediction_freeze_settlement_lab import (
    freeze_research_prediction,settle_research_result)
from diagnostics.rg03_temporal_journal_walkforward_lab import (
    audit_frozen_walkforward,TemporalIntegrationRejected)
from diagnostics.p6_virtual_settlement_fixture_lab import LabRejected

def make_lab_records(base):
    out=[]
    for i in range(5):
        day=datetime(2026,11,11,tzinfo=timezone.utc)+timedelta(days=i)
        at=lambda h:(day+timedelta(hours=h)).isoformat()
        race_id=f"LAB-CHRONO-{i+1:02d}"
        # Changing strengths changes the held-out probability vector.
        strength={1:float(5-i%3),2:3.0,3:float(1+i%3)}
        frames={1:1,2:1,3:2}
        market={(1,2):"20.0",(1,3):"20.0",(2,3):"20.0"}
        path=Path(base)/f"journal-{i}.jsonl"
        frozen=freeze_research_prediction(
            path,scenario_id=race_id,ticket_type="QUINELLA",
            strengths=strength,frames=frames,market=market,
            observed_utc=at(1),frozen_utc=at(2),cutoff_utc=at(3))
        winner=(1,2) if i%2==0 else (2,3)
        result=settle_research_result(
            path,expected_head=frozen["journal_head_sha256"],version=1,
            payout_per_100={f"{winner[0]}-{winner[1]}":600},
            refunded_pairs=[],event_utc=at(4))
        out.append({
            "path":str(path),"expected_head":result["journal_head_sha256"],
            "race_id":race_id,"strengths":strength,"frames":frames,"market":market,
            "observed_utc":at(1),"result_recorded_utc":at(4)})
    return out

class WalkforwardIntegrated(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.rows=make_lab_records(self.dir.name)
    def audit(self,rows=None):
        return audit_frozen_walkforward(self.rows if rows is None else rows)
    def test_full_walk_forward_on_frozen_journals(self):
        x=self.audit()
        self.assertEqual(x["holdout_races"],2)
        self.assertEqual(len(x["scored"]["folds"]),2)
        self.assertEqual(x["freeze_order"],[r["race_id"] for r in self.rows])
        self.assertTrue(x["sequential_result_availability_enforced"])
        self.assertFalse(x["operational_prediction_ready"])
        self.assertFalse(x["official_result_authenticated"])
        self.assertEqual(x,self.audit())
    def test_changed_precommit_training_features_rejected(self):
        rows=copy.deepcopy(self.rows)
        rows[0]["strengths"][1]=999
        with self.assertRaisesRegex(TemporalIntegrationRejected,"precommitted_input_mismatch"):
            self.audit(rows)
    def test_changed_market_is_not_allowed(self):
        rows=copy.deepcopy(self.rows)
        rows[2]["market"][(1,2)]="15.0"
        with self.assertRaisesRegex(TemporalIntegrationRejected,"precommitted_input_mismatch"):
            self.audit(rows)
    def test_future_training_result_rejected(self):
        rows=copy.deepcopy(self.rows)
        rows[0]["result_recorded_utc"]="2026-11-12T06:00:00+00:00"
        with self.assertRaisesRegex(TemporalIntegrationRejected,"previous_outcome_not_available"):
            self.audit(rows)
    def test_result_before_cutoff_rejected(self):
        rows=copy.deepcopy(self.rows)
        rows[2]["result_recorded_utc"]="2026-11-13T02:59:00+00:00"
        with self.assertRaisesRegex(TemporalIntegrationRejected,"future_information_or_cutoff"):
            self.audit(rows)
    def test_reordered_races_rejected(self):
        rows=copy.deepcopy(self.rows)
        rows[0],rows[1]=rows[1],rows[0]
        with self.assertRaisesRegex(TemporalIntegrationRejected,"races_out_of_order"):
            self.audit(rows)
    def test_truncated_journal_rejected_by_external_anchor(self):
        p=Path(self.rows[0]["path"])
        p.write_bytes(p.read_bytes().splitlines(keepends=True)[0])
        with self.assertRaises(LabRejected):
            self.audit()
    def test_tampered_journal_rejected(self):
        p=Path(self.rows[1]["path"])
        p.write_bytes(p.read_bytes().replace(b"LAB-CHRONO-02",b"LAB-CHRONO-XX"))
        with self.assertRaises(LabRejected):
            self.audit()
    def test_wrong_external_anchor_rejected(self):
        rows=copy.deepcopy(self.rows)
        rows[0]["expected_head"]="0"*64
        with self.assertRaises(LabRejected):
            self.audit(rows)
    def test_duplicate_journal_refused(self):
        rows=copy.deepcopy(self.rows)
        rows[1]["path"]=rows[0]["path"]
        with self.assertRaisesRegex(TemporalIntegrationRejected,"journal_missing_or_duplicate"):
            self.audit(rows)
    def test_labels_cannot_enter_frozen_input_schema(self):
        rows=copy.deepcopy(self.rows)
        rows[2]["winning_pair"]=[1,2]
        with self.assertRaisesRegex(TemporalIntegrationRejected,"input_schema_invalid"):
            self.audit(rows)
    def test_missing_holdout_prevented(self):
        with self.assertRaisesRegex(TemporalIntegrationRejected,"at_least_five"):
            self.audit(self.rows[:4])
    def test_final_without_only_one_winner_rejected(self):
        # Event is immutable: different payout payload cannot be swapped into
        # a valid journal without breaking its chain.
        p=Path(self.rows[0]["path"])
        p.write_bytes(p.read_bytes().replace(b"1-2",b"2-3"))
        with self.assertRaises(LabRejected):
            self.audit()
    def test_no_active_actual_betting(self):
        x=self.audit()
        self.assertFalse(x["actual_bet_authorized"])
        self.assertFalse(x["calibrated_live_model"])
        self.assertFalse(x["external_timestamp_proven"])

if __name__=="__main__": unittest.main()
