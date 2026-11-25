import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_impl31_incident_triage import diagnose
from diagnostics.kyoto_impl25_c12_all_runs_handoff import main

def report():
    clean={'job_conclusion':'success','failure_stage':'POSTFLIGHT_INSPECTION_REQUIRED','artifact_evidence_state':'VALID_ORIGINALS','ciphertext_authenticated':True,'source_original_sha_utc_checked':True,'both_raw_market_originals_sha_utc_verified':True}
    return {'schema':'kyoto_impl25_c12_all_runs_day22_handoff.v1','day':'20261128','github_run_listing_complete':True,'missing_run_count_lower_bound':0,'observed_schedule_count':4,'all_run_metadata_screened':True,'scheduled_runs':[{'run':{'id':n,'event':'schedule','created_at':'2026-11-28T00:15:00Z','head_sha':'a'*40},'state':'ALL_LANES_CLASSIFIED','lanes':{'PC':dict(clean),'SP':dict(clean)}} for n in range(1,5)]}

class IncidentTriage(unittest.TestCase):
    def test_no_incident_for_complete_clean_fixture(self):
        self.assertEqual(diagnose(report())['incident_count'],0)
    def test_actual_failure_and_evidence_gap_not_same_root(self):
        r=report();r['scheduled_runs'][0]['lanes']['PC'].update(job_conclusion='failure',failure_stage='OTHER_FAILURE',artifact_evidence_state='EXACT_ARTIFACT_NOT_FOUND_OR_AMBIGUOUS',ciphertext_authenticated=False)
        d=diagnose(r);self.assertEqual({x['kind'] for x in d['incidents']},{'OBSERVED_EXECUTION_FAILURE','EVIDENCE_UNAVAILABLE'})
        self.assertEqual(d['root_causes_certified'],0);self.assertFalse(d['code_promotion_authorized'])
        self.assertEqual(d,diagnose(copy.deepcopy(r)))
        self.assertEqual(len({x['incident_id'] for x in d['incidents']}),2)
    def test_missing_schedule_is_not_execution_failure(self):
        r=report();r.update(github_run_listing_complete=False,missing_run_count_lower_bound=1)
        self.assertEqual({x['kind'] for x in diagnose(r)['incidents']},{'EVIDENCE_UNAVAILABLE','EXPECTED_RECORD_NOT_OBSERVED'})
    def test_integrity_rejection_and_gap_separate(self):
        r=report();r['scheduled_runs'][0]['lanes']['PC']['artifact_evidence_state']='SOURCE_SHA_UTC_MISMATCH';r['scheduled_runs'][0]['lanes']['SP']['both_raw_market_originals_sha_utc_verified']=False
        self.assertEqual({x['kind'] for x in diagnose(r)['incidents']},{'EVIDENCE_REJECTED','OBSERVED_SOURCE_GAP'})
    def test_unknown_labels_do_not_leak(self):
        r=report();r['scheduled_runs'][0]['lanes']['PC'].update(job_conclusion='failure',failure_stage='https://private.example/key',artifact_evidence_state='https://private.example/secret')
        s=json.dumps(diagnose(r));self.assertNotIn('private.example',s);self.assertIn('ISOLATE_UNKNOWN_FAILURE_OFFLINE',s)
    def test_duplicate_or_wrong_day_rejected(self):
        r=report();r['scheduled_runs'][1]['run']['id']=1
        with self.assertRaises(ValueError):diagnose(r)
    def test_actual_handoff_entrypoint_persists_worklist(self):
        r=report();r['scheduled_runs'][0]['lanes']['PC'].update(job_conclusion='failure',failure_stage='OFFLINE_REGRESSION')
        with tempfile.TemporaryDirectory() as d,patch('diagnostics.kyoto_impl25_c12_all_runs_handoff.gather',return_value=r):
            p=Path(d)/'report.json';main(['--day','20261128','--repo','owner/repo','--out',str(p)])
            saved=json.loads(p.read_text());self.assertIn('REPLAY_FAILED_TEST_OUTSIDE_LIVE_SLOT',saved['incident_triage']['incidents'][0]['diagnostic_checks'])
            self.assertTrue(p.with_suffix('.sha256').is_file())
    def test_diagnostic_failure_cannot_stop_handoff(self):
        with tempfile.TemporaryDirectory() as d,patch('diagnostics.kyoto_impl25_c12_all_runs_handoff.gather',return_value=report()),patch('diagnostics.kyoto_impl31_incident_triage.diagnose',side_effect=RuntimeError('fixture')):
            p=Path(d)/'report.json';main(['--day','20261128','--repo','owner/repo','--out',str(p)])
            self.assertEqual(json.loads(p.read_text())['incident_triage_error_class'],'RuntimeError')
