"""R11: certified-scope LAB freeze, exact source/model/ticket identity, tamper gates."""
import copy, tempfile, unittest
from pathlib import Path
from diagnostics.p6_virtual_settlement_fixture_lab import (
    freeze_fixture,settle_fixture,LabRejected)
from diagnostics.p6_fixture_durable_ledger import append_record,read_journal

BASE={"scenario_id":"LAB-R11-ACCEPT",
      "ticket_type":"QUINELLA","cutoff_utc":"2026-11-14T05:00:00Z",
      "frozen_utc":"2026-11-14T04:58:00Z",
      "model_version":"lab-model-registered-v1","source_sha256":"b"*64,
      "tickets":[{"pair":[1,2],"stake_yen":200,"probability":.34,"odds":4.2}]}
def result(version=1,amount=400,state="PAYOUT_FINAL"):
    return {"scenario_id":"LAB-R11-ACCEPT","source_kind":"FIXTURE",
            "version":version,"state":state,"payout_per_100":{"1-2":amount},
            "refunded_pairs":[]}

class R11Acceptance(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory()
    self.addCleanup(self.tmp.cleanup)
    self.path=Path(self.tmp.name)/"immutable.jsonl"
    self.frozen=freeze_fixture(**copy.deepcopy(BASE))
 def start(self):
    return append_record(self.path,"FROZEN",self.frozen,expected_head="0"*64)
 def test_frozen_contract_carries_source_model_time_market_stake(self):
    f=self.frozen["frozen"]
    for k in ("scenario_id","ticket_type","model_version","source_sha256",
              "frozen_utc","cutoff_utc","tickets"):
        self.assertIn(k,f)
    self.assertFalse(f["not_actual_purchase"] is False)
    self.assertEqual(f["tickets"][0]["stake_yen"],200)
 def test_freeze_sha_and_restart_equal(self):
    h=self.start()["head"]
    s=read_journal(self.path,expected_head=h)
    self.assertEqual(s["result"]["status"],"UNSETTLED")
    self.assertEqual(s["entries"][0]["payload"]["record"],self.frozen)
 def test_late_freeze_rejected(self):
    bad=copy.deepcopy(BASE)
    bad["frozen_utc"]=bad["cutoff_utc"]
    with self.assertRaisesRegex(LabRejected,"freeze_after_cutoff"):
        freeze_fixture(**bad)
 def test_model_mutation_detected(self):
    bad=copy.deepcopy(self.frozen)
    bad["frozen"]["model_version"]="future-optimized"
    with self.assertRaisesRegex(LabRejected,"freeze_tampered"):
        settle_fixture(bad,[])
 def test_source_hash_mutation_detected(self):
    bad=copy.deepcopy(self.frozen)
    bad["frozen"]["source_sha256"]="c"*64
    with self.assertRaisesRegex(LabRejected,"freeze_tampered"):
        settle_fixture(bad,[])
 def test_stake_mutation_detected(self):
    bad=copy.deepcopy(self.frozen)
    bad["frozen"]["tickets"][0]["stake_yen"]=9000
    with self.assertRaisesRegex(LabRejected,"freeze_tampered"):
        settle_fixture(bad,[])
 def test_duplicate_freeze_fails_without_writing(self):
    h=self.start()["head"]
    with self.assertRaisesRegex(LabRejected,"journal_already_frozen"):
        append_record(self.path,"FROZEN",self.frozen,expected_head=h)
    self.assertEqual(read_journal(self.path)["head"],h)
 def test_stale_head_blocks_double_event(self):
    h=self.start()["head"]
    append_record(self.path,"RESULT_EVENT",result(),expected_head=h)
    with self.assertRaisesRegex(LabRejected,"journal_head_changed"):
        append_record(self.path,"RESULT_EVENT",result(2),expected_head=h)
 def test_conflicting_final_same_version_rejected(self):
    h=self.start()["head"]
    new=append_record(self.path,"RESULT_EVENT",result(),expected_head=h)
    with self.assertRaises(LabRejected):
        append_record(self.path,"RESULT_EVENT",result(amount=500),expected_head=new["head"])
 def test_final_to_preliminary_refused(self):
    h=self.start()["head"]
    new=append_record(self.path,"RESULT_EVENT",result(),expected_head=h)
    with self.assertRaises(LabRejected):
        append_record(self.path,"RESULT_EVENT",result(2,state="RESULT_PRELIMINARY"),expected_head=new["head"])
 def test_tampered_journal_bytes_refused(self):
    self.start()
    self.path.write_bytes(self.path.read_bytes().replace(b"lab-model-registered-v1",b"lab-model-registered-v2"))
    with self.assertRaisesRegex(LabRejected,"journal_entry_tampered"):
        read_journal(self.path)
 def test_truncated_journal_with_original_anchor_refused(self):
    h=self.start()["head"]
    self.path.write_bytes(b"")
    with self.assertRaisesRegex(LabRejected,"journal_head_anchor_mismatch"):
        read_journal(self.path,expected_head=h)
 def test_nonfixture_source_cannot_be_frozen(self):
    bad=copy.deepcopy(BASE);bad["scenario_id"]="KYOTO-REAL"
    with self.assertRaisesRegex(LabRejected,"lab_marker_required"):
        freeze_fixture(**bad)
 def test_altered_ticket_odds_refused(self):
    bad=copy.deepcopy(self.frozen)
    bad["frozen"]["tickets"][0]["odds"]=77
    with self.assertRaisesRegex(LabRejected,"freeze_tampered"):
        settle_fixture(bad,[])
if __name__=="__main__":unittest.main()
