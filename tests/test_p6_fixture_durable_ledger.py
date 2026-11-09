"""Local filesystem P6 fixture persistence regression; not a JRA result feed."""
import tempfile
import unittest
from pathlib import Path
from diagnostics.p6_fixture_durable_ledger import read_journal, append_record, LabRejected
from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture

def frozen():
    return freeze_fixture(scenario_id='LAB-JOURNAL-1', ticket_type='QUINELLA',
        frozen_utc='2026-11-13T04:00:00Z', cutoff_utc='2026-11-14T04:50:00Z',
        model_version='lab-not-calibrated', source_sha256='a'*64,
        tickets=[{'pair':[1,2], 'stake_yen':200,'probability':.3,'odds':4.2}])

def event(version=1,state='PAYOUT_FINAL',paid=500):
    return {'scenario_id':'LAB-JOURNAL-1','source_kind':'FIXTURE','version':version,
            'state':state,'payout_per_100':{'1-2':paid},'refunded_pairs':[]}

class DurableFixtureJournal(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
        self.path=Path(self.dir.name)/'ledger.jsonl'
    def start(self):
        return append_record(self.path,'FROZEN',frozen(),expected_head='0'*64)
    def test_empty_is_explicit(self):
        self.assertEqual(read_journal(self.path)['state'],'EMPTY')
    def test_freeze_survives_restart_and_hash_stable(self):
        one=self.start();two=read_journal(self.path)
        self.assertEqual(one['head'],two['head']);self.assertEqual(len(two['entries']),1)
        self.assertEqual(two['result']['status'],'UNSETTLED')
    def test_preliminary_stays_unsettled_after_restart(self):
        s=self.start();s=append_record(self.path,'RESULT_EVENT',event(state='RESULT_PRELIMINARY'),expected_head=s['head'])
        self.assertEqual(read_journal(self.path)['result']['profit_yen'],None)
    def test_final_and_correction_replace_not_accumulate(self):
        s=self.start();s=append_record(self.path,'RESULT_EVENT',event(1),expected_head=s['head'])
        self.assertEqual(s['result']['payout_yen'],1000)
        s=append_record(self.path,'RESULT_EVENT',event(2,paid=400),expected_head=s['head'])
        self.assertEqual(s['result']['payout_yen'],800)
        self.assertEqual(s['result']['profit_yen'],600)
        self.assertEqual(read_journal(self.path)['result'],s['result'])
    def test_stale_head_rejected(self):
        s=self.start()
        with self.assertRaisesRegex(LabRejected,'journal_head_changed'):
            append_record(self.path,'RESULT_EVENT',event(),expected_head='0'*64)
        self.assertEqual(len(read_journal(self.path)['entries']),1)
    def test_duplicate_freeze_rejected(self):
        s=self.start()
        with self.assertRaisesRegex(LabRejected,'journal_already_frozen'):
            append_record(self.path,'FROZEN',frozen(),expected_head=s['head'])
    def test_duplicate_event_rejected(self):
        s=self.start();s=append_record(self.path,'RESULT_EVENT',event(),expected_head=s['head'])
        with self.assertRaisesRegex(LabRejected,'journal_duplicate_event_append'):
            append_record(self.path,'RESULT_EVENT',event(),expected_head=s['head'])
        self.assertEqual(len(read_journal(self.path)['entries']),2)
    def test_conflicting_version_rejected(self):
        s=self.start();s=append_record(self.path,'RESULT_EVENT',event(),expected_head=s['head'])
        with self.assertRaises(LabRejected):
            append_record(self.path,'RESULT_EVENT',event(paid=600),expected_head=s['head'])
    def test_changed_older_bytes_detected(self):
        self.start()
        data=self.path.read_bytes().replace(b'lab-not-calibrated',b'lab-bad-calibrated')
        self.path.write_bytes(data)
        with self.assertRaisesRegex(LabRejected,'journal_entry_tampered'):
            read_journal(self.path)
    def test_torn_record_refused(self):
        self.start();self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaisesRegex(LabRejected,'torn_journal_record'):
            read_journal(self.path)
    def test_truncated_complete_line_detected_with_anchor(self):
        s=self.start();s=append_record(self.path,'RESULT_EVENT',event(),expected_head=s['head'])
        self.path.write_bytes(self.path.read_bytes().splitlines(keepends=True)[0])
        # Complete-line truncation is detected only if the last head is anchored externally.
        self.assertNotEqual(read_journal(self.path)['head'],s['head'])
    def test_symlink_rejected(self):
        external=Path(self.dir.name)/'real.txt';external.write_text('x')
        self.path.symlink_to(external)
        with self.assertRaisesRegex(LabRejected,'journal_symlink_forbidden'):
            read_journal(self.path)
    def test_event_without_freeze_rejected(self):
        with self.assertRaisesRegex(LabRejected,'journal_freeze_required'):
            append_record(self.path,'RESULT_EVENT',event(),expected_head='0'*64)
    def test_nonfixture_input_rejected(self):
        s=self.start();e=event();e['source_kind']='OFFICIAL'
        with self.assertRaisesRegex(LabRejected,'event_invalid'):
            append_record(self.path,'RESULT_EVENT',e,expected_head=s['head'])
    def test_final_back_to_preliminary_rejected(self):
        s=self.start();s=append_record(self.path,'RESULT_EVENT',event(),expected_head=s['head'])
        with self.assertRaisesRegex(LabRejected,'event_invalid'):
            append_record(self.path,'RESULT_EVENT',event(2,state='RESULT_PRELIMINARY'),expected_head=s['head'])

if __name__=='__main__':unittest.main()
