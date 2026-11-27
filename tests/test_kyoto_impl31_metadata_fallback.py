import json,unittest
from unittest.mock import patch
from diagnostics.kyoto_impl30_nextday_adaptation import recover, recover_from_metadata, OBSERVER, OBSERVER_NAME, TARGET_DAY
from tests.test_kyoto_impl30_nextday_adaptation import REPO,SHA,KEY

def run():
    return dict(id=42,name=OBSERVER_NAME,created_at='2026-11-28T02:15:00Z',event='schedule',status='completed',head_repository={'full_name':REPO},path='.github/workflows/'+OBSERVER)
def job():
    return dict(run_id=42,name='pc-originals-independent',status='completed',conclusion='failure',steps=[{'name':'Race date, immutable commit, secret, first attempt and non-replay guard','conclusion':'failure'}])
def api_for(r,j):
    def api(endpoint):
        if '/workflows/' in endpoint:return {'total_count':1,'workflow_runs':[r]}
        return {'total_count':1,'jobs':[j]}
    return api
class Fallback(unittest.TestCase):
    def test_positive_failure(self):
        self.assertEqual(recover_from_metadata(api_for(run(),job()),REPO),('MARKET_OR_ROSTER_RECOVERY','OBSERVER_FAILURE_METADATA_ONLY_42_PC'))
    def test_wrong_context(self):
        for key,val in [('event','workflow_dispatch'),('created_at','2026-11-29'),('head_repository',{'full_name':'other/repo'}),('path','wrong'),('status','in_progress')]:
            r=run();r[key]=val
            self.assertEqual(recover_from_metadata(api_for(r,job()),REPO)[0],'BASELINE')
    def test_unconfirmed_job(self):
        for key,val in [('run_id',43),('conclusion','success'),('status','in_progress'),('steps',[])]:
            j=job();j[key]=val
            self.assertEqual(recover_from_metadata(api_for(run(),j),REPO)[0],'BASELINE')
    def test_primary_missing_secondary_applied(self):
        def cli(args,**kwargs):
            self.assertLessEqual(kwargs['timeout'],5)
            endpoint=args[-1]
            if OBSERVER not in endpoint and '/jobs?' not in endpoint:return json.dumps({'total_count':0,'workflow_runs':[]})
            return json.dumps(api_for(run(),job())(endpoint))
        with patch('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output',side_effect=cli):
            mode,reason=recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY)
        self.assertEqual(mode,'MARKET_OR_ROSTER_RECOVERY');self.assertIn('METADATA_ONLY',reason)
    def test_bounded_total_and_invalid_key(self):
        clock=iter([0,19,19])
        with patch('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output') as cli:
            self.assertEqual(recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY,monotonic=lambda:next(clock))[0],'BASELINE')
            self.assertEqual(recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key='bad')[0],'BASELINE')
            cli.assert_not_called()
    def test_duplicate_runs(self):
        with self.assertRaises(ValueError):recover_from_metadata(lambda _: {'total_count':2,'workflow_runs':[run(),run()]},REPO)
if __name__=='__main__':unittest.main()

class RuntimeFallback(unittest.TestCase):
    def test_real_sp_entrypoint_without_signed_handoff(self):
        import os,tempfile,time
        from pathlib import Path
        from diagnostics.kyoto_weekend_capture import capture
        from diagnostics.kyoto_impl30_nextday_adaptation import WORKFLOW
        def cli(args,**kwargs):
            if WORKFLOW in args[-1]:return json.dumps({'total_count':0,'workflow_runs':[]})
            return json.dumps(api_for(run(),job())(args[-1]))
        def discover(root,**kwargs):
            root.mkdir();(root/'sp_discovery_receipt.json').write_text('{}')
            return {'network_requests_started':0,'racecard_url':'observed-fixture'}
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'KYOTO_TARGET_DAY':TARGET_DAY,'KYOTO_WEEKEND_HTTP_APPROVED':'YES','GITHUB_EVENT_NAME':'schedule','ARCHIVE_KEY':KEY,'GITHUB_REPOSITORY':REPO,'COLLECTOR_SHA':SHA}),patch('diagnostics.kyoto_weekend_capture.validate_day'),patch('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output',side_effect=cli),patch('diagnostics.kyoto_weekend_sp_discovery.discover',side_effect=discover),patch('diagnostics.kyoto_sp_all12_observed_capture.capture_all',return_value={'races':{}}) as live_capture:
            before=time.monotonic()
            out=capture(TARGET_DAY,'SP',str(Path(tmp)/'source'),live=True,opener=object())
            after=time.monotonic()
            deadline=live_capture.call_args.kwargs['deadline_monotonic']
            self.assertLessEqual(before+360,deadline);self.assertLessEqual(deadline,after+360)
            self.assertEqual(out['observed_http_requests_started'],0)
    def test_handoff_status_distinguished(self):
        from diagnostics.kyoto_impl30_nextday_adaptation import WORKFLOW,NAME
        for status,conclusion,label in [('in_progress',None,'HANDOFF_INCOMPLETE'),('completed','timed_out','HANDOFF_TIMED_OUT'),('completed','failure','HANDOFF_FAILED')]:
            r=dict(run(),name=NAME,path='.github/workflows/'+WORKFLOW,status=status,conclusion=conclusion)
            def cli(args,**kwargs):
                if WORKFLOW in args[-1]:return json.dumps({'total_count':1,'workflow_runs':[r]})
                return json.dumps(api_for(run(),job())(args[-1]))
            with patch('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output',side_effect=cli):
                mode,reason=recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY)
            self.assertEqual(mode,'MARKET_OR_ROSTER_RECOVERY');self.assertIn(label,reason)
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_impl30_nextday_adaptation import derive,make,accept,recover,recover_from_metadata,WORKFLOW,NAME,TARGET_DAY
from diagnostics.kyoto_impl31_handoff_budget import gather_bounded
from tests.test_kyoto_impl30_nextday_adaptation import saturday,REPO,SHA,KEY
from tests.test_kyoto_impl31_handoff_budget import fixture,DAY

class DispatchFailureRecovery(unittest.TestCase):
    def dispatch(self):return dict(run(),event='workflow_dispatch',head_branch='main')
    def test_only_exact_main_dispatch_positive_failure(self):
        r=self.dispatch();self.assertEqual(recover_from_metadata(api_for(r,job()),REPO),('MARKET_OR_ROSTER_RECOVERY','OBSERVER_DISPATCH_FAILURE_METADATA_ONLY_42_PC'))
        for field,val in [('head_branch','other'),('created_at','2026-11-29'),('head_repository',{'full_name':'other/repo'}),('path','wrong'),('event','pull_request'),('status','in_progress')]:
            self.assertEqual(recover_from_metadata(api_for(dict(r,**{field:val}),job()),REPO)[0],'BASELINE')
        for field,val in [('run_id',43),('conclusion','success'),('status','in_progress'),('steps',[])]:
            self.assertEqual(recover_from_metadata(api_for(r,dict(job(),**{field:val})),REPO)[0],'BASELINE')
    def test_handoff_signed_dispatch_failure_when_no_native_or_original(self):
        def invoke(task,end):
            kind,day,repo,rid,lane=task
            if kind=='index':return {'total_count':1,'workflow_runs':[self.dispatch()]} if lane=='main' else {'total_count':0,'workflow_runs':[]}
            if kind=='metadata':return {'jobs':[job()],'artifacts':[]}
            raise AssertionError('no artifact read')
        report=gather_bounded(DAY,REPO,invoke=invoke)
        self.assertEqual(report['observed_schedule_count'],0);self.assertEqual(report['day_source_coverage']['authenticated_pc_slots'],0)
        self.assertEqual(len(report['manual_failure_assessment']),1)
        self.assertEqual(derive(report)['mode'],'MARKET_OR_ROSTER_RECOVERY')
        d=make(report,repo=REPO,run_id=101,collector_sha=SHA,key=KEY)
        self.assertEqual(accept(d,report,repo=REPO,run_id=101,collector_sha=SHA,key=KEY),'MARKET_OR_ROSTER_RECOVERY')
        q=copy.deepcopy(report);q['manual_failure_assessment'][0]['head_branch']='other'
        self.assertEqual(derive(q)['mode'],'BASELINE')
        with self.assertRaises(ValueError):accept(d,q,repo=REPO,run_id=101,collector_sha=SHA,key=KEY)
    def test_incomplete_signed_baseline_does_not_hide_late_positive_failure(self):
        for complete,want in ((False,'MARKET_OR_ROSTER_RECOVERY'),(True,'BASELINE')):
            r=saturday();r['all_run_metadata_screened']=complete
            doc=make(r,repo=REPO,run_id=101,collector_sha=SHA,key=KEY)
            h=dict(id=101,name=NAME,created_at='2026-11-28T12:00:00Z',event='schedule',status='completed',conclusion='success',head_repository={'full_name':REPO},path='.github/workflows/'+WORKFLOW)
            def cli(args,**kw):
                ep=args[-1]
                if WORKFLOW in ep:return json.dumps({'total_count':1,'workflow_runs':[h]})
                if '/artifacts?' in ep:return json.dumps({'total_count':1,'artifacts':[{'name':'kyoto-handoff-101-20261128','expired':False}]})
                return json.dumps(api_for(self.dispatch(),job())(ep))
            def dl(args,**kw):
                p=Path(args[-1]);(p/'report.json').write_text(json.dumps(r));(p/'nextday_policy.json').write_text(json.dumps(doc))
            with patch('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output',side_effect=cli),patch('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.run',side_effect=dl):
                self.assertEqual(recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY)[0],want)
if __name__=='__main__':unittest.main()
