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
