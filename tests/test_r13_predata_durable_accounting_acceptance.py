"""R13: durable multi-race P6 restart, reconciliation, cumulative and drift-safe accounting."""
import tempfile,unittest
from pathlib import Path
from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture,LabRejected
from diagnostics.p6_fixture_durable_ledger import read_journal,append_record
from diagnostics.p6_fixture_temporal_aggregate import (
    aggregate_fixture_journals,aggregate_model_version_cohorts)

class R13Acceptance(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory()
    self.addCleanup(self.tmp.cleanup)
    self.root=Path(self.tmp.name)
 def add(self,i,amount=None,preliminary=False,version="lab-A"):
    path=self.root/f"race{i}.jsonl"
    f=freeze_fixture(scenario_id=f"LAB-R13-{i}",
      ticket_type="QUINELLA",
      frozen_utc=f"2026-11-{i+1:02d}T04:00:00Z",
      cutoff_utc=f"2026-11-{i+1:02d}T05:00:00Z",
      model_version=version,source_sha256="c"*64,
      tickets=[{"pair":[1,2],"stake_yen":200,"probability":0.3,"odds":3.0}])
    s=append_record(path,"FROZEN",f,expected_head="0"*64)
    if amount is not None or preliminary:
      event={"scenario_id":f"LAB-R13-{i}","source_kind":"FIXTURE",
        "version":1,"state":"RESULT_PRELIMINARY" if preliminary else "PAYOUT_FINAL",
        "payout_per_100":{"1-2":amount} if amount else {},
        "refunded_pairs":[]}
      s=append_record(path,"RESULT_EVENT",event,expected_head=s["head"])
    return {"path":str(path),"expected_head":s["head"]}
 def test_three_races_roi_and_max_drawdown(self):
    a=self.add(1,500);b=self.add(2,0);c=self.add(3,preliminary=True)
    r=aggregate_fixture_journals([a,b,c])
    self.assertEqual((r["settled_scenarios"],r["unsettled_scenarios"]),(2,1))
    self.assertEqual((r["stake_yen"],r["payout_yen"],r["profit_yen"]),(400,1000,600))
    self.assertEqual(r["max_drawdown_yen"],200)
    self.assertEqual(r["roi_percent"],250)
 def test_restart_and_reordered_files_same_report(self):
    a=self.add(1,500);b=self.add(2,0)
    self.assertEqual(aggregate_fixture_journals([a,b]),
                     aggregate_fixture_journals([b,a]))
    self.assertEqual(read_journal(a["path"],expected_head=a["expected_head"])["result"]["profit_yen"],800)
 def test_duplicate_journal_rejected(self):
    a=self.add(1,500)
    with self.assertRaisesRegex(LabRejected,"aggregate_duplicate_journal"):
      aggregate_fixture_journals([a,a])
 def test_full_line_truncation_blocked_by_anchor(self):
    a=self.add(1,500)
    path=Path(a["path"])
    path.write_bytes(path.read_bytes().splitlines(keepends=True)[0])
    with self.assertRaisesRegex(LabRejected,"journal_head_anchor_mismatch"):
      aggregate_fixture_journals([a])
 def test_no_anchor_fails_closed(self):
    a=self.add(1,500)
    with self.assertRaisesRegex(LabRejected,"aggregate_journal_spec_invalid"):
      aggregate_fixture_journals([{"path":a["path"]}])
 def test_preliminary_not_counted_as_loss(self):
    r=aggregate_fixture_journals([self.add(1,preliminary=True)])
    self.assertEqual(r["stake_yen"],0)
    self.assertEqual(r["unsettled_scenarios"],1)
    self.assertIsNone(r["roi_percent"])
 def test_correction_replaces_payout_once(self):
    a=self.add(1,500)
    e={"scenario_id":"LAB-R13-1","source_kind":"FIXTURE","version":2,
       "state":"PAYOUT_FINAL","payout_per_100":{"1-2":300},"refunded_pairs":[]}
    s=append_record(a["path"],"RESULT_EVENT",e,expected_head=a["expected_head"])
    corrected=aggregate_fixture_journals([{"path":a["path"],"expected_head":s["head"]}])
    self.assertEqual(corrected["payout_yen"],600)
    self.assertEqual(corrected["profit_yen"],400)
 def test_stale_head_after_correction_fails(self):
    a=self.add(1,500)
    e={"scenario_id":"LAB-R13-1","source_kind":"FIXTURE","version":2,
       "state":"PAYOUT_FINAL","payout_per_100":{},"refunded_pairs":[]}
    append_record(a["path"],"RESULT_EVENT",e,expected_head=a["expected_head"])
    with self.assertRaisesRegex(LabRejected,"journal_head_anchor_mismatch"):
      aggregate_fixture_journals([a])
 def test_model_cohorts_never_authorize_adoption(self):
    a=self.add(1,500,version="lab-A");b=self.add(2,0,version="lab-B")
    r=aggregate_model_version_cohorts([a,b])
    self.assertEqual(set(r["model_version_cohorts"]),{"lab-A","lab-B"})
    self.assertTrue(r["unpaired_comparison_may_be_biased"])
    self.assertFalse(r["model_adoption_authorized"])
 def test_symlink_refused(self):
    a=self.add(1,500)
    alias=self.root/"alias.jsonl";alias.symlink_to(Path(a["path"]))
    with self.assertRaisesRegex(LabRejected,"aggregate_journal_file_invalid"):
      aggregate_fixture_journals([{"path":str(alias),"expected_head":a["expected_head"]}])
 def test_tampered_bytes_refused(self):
    a=self.add(1,500)
    path=Path(a["path"])
    path.write_bytes(path.read_bytes().replace(b"lab-A",b"lab-B"))
    with self.assertRaisesRegex(LabRejected,"journal_entry_tampered"):
      aggregate_fixture_journals([a])
 def test_duplicate_scenario_in_separate_journal_refused(self):
    a=self.add(1,500)
    path2=self.root/"separate.jsonl"
    frozen=read_journal(a["path"])["entries"][0]["payload"]["record"]
    t=append_record(path2,"FROZEN",frozen,expected_head="0"*64)
    with self.assertRaisesRegex(LabRejected,"aggregate_duplicate_scenario"):
      aggregate_fixture_journals([a,{"path":str(path2),"expected_head":t["head"]}])
if __name__=="__main__":unittest.main()
