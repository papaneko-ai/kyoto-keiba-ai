import json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_weekend_capture import seal
from diagnostics.kyoto_safe_stop_artifact import record_pre_http_stop
from diagnostics.kyoto_weekend_day21_artifact_triage import assess_lane
from diagnostics.kyoto_impl31_incident_triage import diagnose
REPO='papaneko-ai/kyoto-keiba-ai'
DAY='20261128'
class SourceCertainty(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.dst=self.root/'sealed'
    def read(self,day=DAY):
        return assess_lane(self.dst,day=day,channel='PC',key='ab'*32,repo=REPO,run_id='123')
    def test_missing_directory_not_zero_for_both_future_days(self):
        for day in ('20261128','20261129'):
            self.dst=self.root/day
            d=seal(day,str(self.root/'missing'),str(self.dst),key='',repo=REPO,run_id='123')
            self.assertEqual(d['actual_jra_http_requests'],'UNKNOWN')
            self.assertFalse(d['JRA_success']);self.assertEqual(self.read(day)['state'],'NO_SOURCE_HTTP_UNVERIFIED')
    def test_legacy_zero_receipt_not_promoted_on_new_weekend(self):
        record_pre_http_stop(self.dst,race_day=DAY,reason='legacy')
        self.assertEqual(self.read()['actual_jra_http_requests'],'UNKNOWN')
    def test_wrong_day_and_invalid_credit_rejected(self):
        record_pre_http_stop(self.dst,race_day='20261129',reason='wrong')
        self.assertEqual(self.read()['state'],'MALFORMED_SAFE_STOP')
        p=self.dst/'safe_stop.json';d=json.loads(p.read_text());d['race_day']=DAY;d['operational_credit']=True;p.write_text(json.dumps(d))
        self.assertEqual(self.read()['state'],'MALFORMED_SAFE_STOP')
    def test_mixed_cipher_and_stop_rejected(self):
        record_pre_http_stop(self.dst,race_day=DAY,reason='mixed',http_count_known=False)
        (self.dst/'manifest.json').write_text('{}')
        self.assertEqual(self.read()['state'],'MALFORMED_SAFE_STOP')
    def test_legacy_historical_readback_preserved(self):
        record_pre_http_stop(self.dst,race_day='20261121',reason='old')
        self.assertEqual(self.read('20261121')['state'],'PRE_HTTP_SAFE_STOP_NO_SOURCE')
    def test_unknown_not_pre_http_incident(self):
        row={'job_conclusion':'success','failure_stage':'UNKNOWN','artifact_evidence_state':'NO_SOURCE_HTTP_UNVERIFIED'}
        report={'schema':'kyoto_impl25_c12_all_runs_day22_handoff.v1','day':DAY,'github_run_listing_complete':True,'scheduled_runs':[{'run':{'id':123,'event':'schedule','created_at':'2026-11-28T01:00:00Z'},'state':'ALL_LANES_CLASSIFIED','lanes':{'PC':row,'SP':row}}]}
        out=diagnose(report);self.assertEqual({x['kind'] for x in out['incidents']},{'EVIDENCE_REJECTED'})
        self.assertEqual(out['root_causes_certified'],0)
    def test_known_count_flag_type_rejected(self):
        with self.assertRaises(ValueError):record_pre_http_stop(self.dst,race_day=DAY,reason='bad',http_count_known='false')
