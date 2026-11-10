import tempfile
import unittest
from pathlib import Path
from diagnostics.p6_fixture_durable_ledger import append_record,LabRejected
from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture
from diagnostics.p6_fixture_temporal_aggregate import aggregate_fixture_journals


class TemporalFixtureTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
 def record(self,i,*,payout=None,preliminary=False):
  path=self.root/f"race{i}.jsonl"
  freeze=freeze_fixture(scenario_id=f"LAB-AGG-{i}",ticket_type="QUINELLA",
      frozen_utc=f"2026-11-{i+1:02d}T04:00:00Z",
      cutoff_utc=f"2026-11-{i+1:02d}T05:00:00Z",
      model_version="lab-v1",source_sha256="a"*64,
      tickets=[{"pair":[1,2],"stake_yen":200,"probability":0.3,"odds":4.2}])
  state=append_record(path,"FROZEN",freeze,expected_head="0"*64)
  if payout is not None or preliminary:
   event={"scenario_id":f"LAB-AGG-{i}","source_kind":"FIXTURE","version":1,
          "state":"RESULT_PRELIMINARY" if preliminary else "PAYOUT_FINAL",
          "payout_per_100":{"1-2":payout} if payout is not None else {},
          "refunded_pairs":[]}
   state=append_record(path,"RESULT_EVENT",event,expected_head=state["head"])
  return {"path":str(path),"expected_head":state["head"]}
 def test_aggregate_corrections_and_chronological_cohorts(self):
  a=self.record(1,payout=500)
  b=self.record(2,payout=0)
  c=self.record(3,preliminary=True)
  result=aggregate_fixture_journals([c,b,a])
  self.assertEqual(result["total_scenarios"],3)
  self.assertEqual(result["settled_scenarios"],2)
  self.assertEqual(result["unsettled_scenarios"],1)
  self.assertEqual(result["stake_yen"],400)
  self.assertEqual(result["payout_yen"],1000)
  self.assertEqual(result["profit_yen"],600)
  self.assertEqual(result["roi_percent"],250)
  self.assertEqual(result["race_hit_rate_percent"],50)
  self.assertEqual(result["max_drawdown_yen"],200)
  self.assertEqual(result["first_half"]["profit_yen"],800)
  self.assertEqual(result["second_half"]["profit_yen"],-200)
  self.assertEqual(result,aggregate_fixture_journals([a,c,b]))
  self.assertFalse(result["actual_purchase"])
  self.assertFalse(result["prediction_ready"])
 def test_all_unsettled_no_fabricated_roi(self):
  result=aggregate_fixture_journals([self.record(1,preliminary=True)])
  self.assertIsNone(result["roi_percent"])
  self.assertIsNone(result["race_hit_rate_percent"])
  self.assertEqual(result["profit_yen"],0)
 def test_duplicate_journal_rejected(self):
  a=self.record(1,payout=500)
  with self.assertRaisesRegex(LabRejected,"aggregate_duplicate_journal"):
   aggregate_fixture_journals([a,a])
 def test_tampered_anchor_rejected(self):
  a=self.record(1,payout=500)
  a["expected_head"]="0"*64
  with self.assertRaisesRegex(LabRejected,"journal_head_anchor_mismatch"):
   aggregate_fixture_journals([a])
 def test_tampered_bytes_rejected(self):
  a=self.record(1,payout=500)
  path=Path(a["path"])
  path.write_bytes(path.read_bytes().replace(b"lab-v1",b"lab-v2"))
  with self.assertRaisesRegex(LabRejected,"journal_entry_tampered"):
   aggregate_fixture_journals([a])
 def test_no_anchor_rejected(self):
  a=self.record(1,payout=500)
  del a["expected_head"]
  with self.assertRaisesRegex(LabRejected,"aggregate_journal_spec_invalid"):
   aggregate_fixture_journals([a])
 def test_symlink_rejected(self):
  a=self.record(1,payout=500)
  symlink=self.root/"link.jsonl";symlink.symlink_to(Path(a["path"]))
  with self.assertRaisesRegex(LabRejected,"aggregate_journal_file_invalid"):
   aggregate_fixture_journals([{"path":str(symlink),"expected_head":a["expected_head"]}])
 def test_empty_rejected(self):
  with self.assertRaisesRegex(LabRejected,"aggregate_nonempty_journal_list_required"):
   aggregate_fixture_journals([])

if __name__=="__main__":
 unittest.main()
