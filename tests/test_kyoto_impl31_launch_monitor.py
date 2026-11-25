import unittest
from datetime import datetime, timezone
from diagnostics.kyoto_impl31_launch_monitor import report, slot_key, expected, REHEARSAL, PRODUCTION
DAY='20261125'; CRON='0 3 25 11 *'
NOW=datetime(2026,11,25,3,20,tzinfo=timezone.utc)
def run(**kw):
    return dict({'id':1,'path':REHEARSAL,'head_branch':'main','event':'schedule','created_at':'2026-11-25T03:08:00Z','status':'queued'},**kw)
class Monitor(unittest.TestCase):
    def check(self,runs=(),identities=None,complete=True):
        return report(DAY,NOW,runs,identities or {},complete=complete)
    def test_missing_vs_future(self):
        r=self.check();self.assertEqual([x['state'] for x in r['slots']],['NO_RUN_OBSERVED_AFTER_GRACE','NOT_DUE']);self.assertTrue(r['slots'][0]['external_no_jra_probe_candidate'])
    def test_incomplete_listing(self):self.assertEqual(self.check(complete=False)['slots'][0]['state'],'HISTORY_UNVERIFIED')
    def test_unknown_slot_not_guessed(self):self.assertEqual(self.check([run()])['slots'][0]['state'],'UNASSIGNED_RUN_EVIDENCE')
    def test_queued(self):
        r=self.check([run()],{'1':CRON})['slots'][0];self.assertEqual(r['state'],'RUN_QUEUED');self.assertEqual(r['creation_delay_seconds'],480)
    def test_in_progress(self):
        r=self.check([run(status='in_progress',run_started_at='2026-11-25T03:10:00Z')],{'1':CRON})['slots'][0];self.assertEqual(r['state'],'RUN_IN_PROGRESS');self.assertEqual(r['start_delay_seconds'],600)
    def test_success_not_source_success(self):
        r=self.check([run(status='completed',conclusion='success')],{'1':CRON})['slots'][0];self.assertFalse(r['source_success_proved']);self.assertEqual(r['state'],'RUN_COMPLETED_SUCCESS_NOT_SOURCE_PROOF')
    def test_failed(self):self.assertEqual(self.check([run(status='completed',conclusion='failure')],{'1':CRON})['slots'][0]['state'],'RUN_COMPLETED_NOT_SUCCESS')
    def test_multiple(self):self.assertEqual(self.check([run(),run(id=2)],{'1':CRON,'2':CRON})['slots'][0]['state'],'MULTIPLE_RUNS_SAME_SLOT')
    def test_manual_and_wrong_workflow_not_schedule_proof(self):self.assertEqual(self.check([run(event='workflow_dispatch'),run(id=2,path=PRODUCTION)])['slots'][0]['state'],'NO_RUN_OBSERVED_AFTER_GRACE')
    def test_duplicate_input_rejected(self):
        with self.assertRaises(ValueError):self.check([run(),run()])
    def test_eight_preserved_production_slot_keys(self):
        from diagnostics.kyoto_impl31_launch_monitor import SLOTS
        for d in ('20261128','20261129'):
            self.assertEqual([slot_key(d,c) for c in SLOTS[d]],[f'{d}:{i}' for i in range(4)])
            r=report(d,datetime(2026,11,int(d[-2:]),3,59,tzinfo=timezone.utc),[],{},complete=True)
            self.assertTrue(all(not x['external_no_jra_probe_candidate'] and not x['production_dispatch_authorized'] for x in r['slots']))
    def test_deterministic(self):self.assertEqual(self.check(),self.check())
if __name__=='__main__':unittest.main()
