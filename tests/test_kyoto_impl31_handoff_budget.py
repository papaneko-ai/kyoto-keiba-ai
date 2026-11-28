import unittest,time,sys
from unittest.mock import patch
from diagnostics.kyoto_impl31_handoff_budget import gather_bounded,_invoke
from diagnostics.kyoto_impl25_c12_all_runs_handoff import WEEKENDS
from diagnostics.kyoto_impl30_auxiliary_refresh import NAME,WORKFLOW
DAY='20261128'; REPO='papaneko-ai/kyoto-keiba-ai'

def run(rid,aux=False,event='schedule'):
    name,file=(NAME,WORKFLOW) if aux else WEEKENDS[DAY][:2]
    return dict(id=rid,name=name,path='.github/workflows/'+file,created_at='2026-11-28T02:00:00Z',event=event,status='completed',conclusion='success',head_repository={'full_name':REPO})

def fixture(task,end):
    kind,day,repo,rid,lane=task
    if kind=='index':
        rs=[run(1),run(2),run(3),run(4),run(5,event='workflow_dispatch')] if lane=='main' else [run(6,True),run(7,True),run(8,True),run(9,True)]
        return {'total_count':len(rs),'workflow_runs':rs}
    if kind=='metadata':
        return {'jobs':[{'name':f'{c.lower()}-originals-independent','conclusion':'success','steps':[]} for c in ('PC','SP')], 'artifacts':[{'name':f'kyoto-{c.lower()}-{rid}-{day}','expired':False} for c in ('PC','SP')]}
    if kind=='aux':
        if rid==9:return {'error_class':'HANDOFF_WORKER_TIMEOUT'}
        return {'day':day,'run_id':str(rid),'races':{}}
    if rid==3 and lane=='SP': return {'error_class':'HANDOFF_WORKER_TIMEOUT'}
    return {'state':'VALID_ORIGINALS_WITH_INCOMPLETE_MARKETS','ciphertext_authenticated':True,'source_original_sha_utc_checked':True,'day_coverage_slot':{'day':day,'run_id':str(rid),'races':{}}}

class HandoffBudget(unittest.TestCase):
    def test_all_lanes_and_manual_sources_preserved_despite_two_timeouts(self):
        r=gather_bounded(DAY,REPO,invoke=fixture)
        self.assertEqual(r['observed_schedule_count'],4)
        self.assertEqual(r['day_source_coverage']['authenticated_pc_slots'],5)
        self.assertEqual(r['day_source_coverage']['authenticated_auxiliary_slots'],3)
        self.assertEqual(r['manual_source_assessment'],[{'run_id':5,'authenticated_pc_slot':True,'state':'VALID_ORIGINALS_WITH_INCOMPLETE_MARKETS'}])
        self.assertEqual(r['scheduled_runs'][2]['lanes']['SP']['artifact_evidence_state'],'ARTIFACT_DOWNLOAD_FAILED')
        self.assertFalse(r['full_live_jra_coverage_proved'])
        self.assertEqual(r['handoff_budget']['source_tasks'],14)
    def test_wrong_repository_or_incomplete_listing_not_promoted(self):
        def bad(task,end):
            r=fixture(task,end)
            if task[0]=='index' and task[-1]=='main':r['workflow_runs'][0]['head_repository']['full_name']='other/repo'
            return r
        r=gather_bounded(DAY,REPO,invoke=bad)
        self.assertEqual(r['observed_schedule_count'],3)
        self.assertFalse(r['github_run_listing_complete'])
        self.assertFalse(r['all_run_metadata_screened'])
    def test_deadline_exhausted_before_worker_no_spawn(self):
        with patch('diagnostics.kyoto_impl31_handoff_budget.subprocess.Popen') as p:
            self.assertEqual(_invoke(('index',DAY,REPO,0,'main'),0),{'error_class':'HANDOFF_DEADLINE_EXHAUSTED'})
            p.assert_not_called()
    def test_actual_child_timeout_terminates_worker(self):
        # The worker command is replaced with a harmless local sleeper only.
        import subprocess
        original=subprocess.Popen
        def sleep(cmd,**kwargs):return original([sys.executable,'-c','import time; time.sleep(10)'],**kwargs)
        with patch('diagnostics.kyoto_impl31_handoff_budget.subprocess.Popen',side_effect=sleep):
            t=time.monotonic(); result=_invoke(('index',DAY,REPO,0,'main'),t+0.1)
            self.assertEqual(result,{'error_class':'HANDOFF_WORKER_TIMEOUT'})
            self.assertLess(time.monotonic()-t,2)
    def test_runtime_worker_uses_recovery_for_index_and_jobs(self):
        from diagnostics.kyoto_impl31_handoff_budget import _worker
        from diagnostics.kyoto_repair_control import recover_collection
        def recovering(path,field,trace):
            def fetch(endpoint):
                if 'per_page=100' in endpoint:return {'total_count':1,field:[]}
                return {'total_count':1,field:[{'id':7}]}
            return recover_collection(path,field,fetch=fetch,sleep=lambda _:None,trace=trace)
        with patch('diagnostics.kyoto_repair_control.recover_collection',side_effect=recovering):
            x=_worker('index',DAY,REPO,0,'main')
            self.assertEqual(x['workflow_runs'],[{'id':7}])
            self.assertEqual([r['state'] for r in x['metadata_recovery']],['REJECTED','COMPLETE'])
            x=_worker('metadata',DAY,REPO,7,'main')
            self.assertEqual(x['jobs'],[{'id':7}])
            self.assertEqual(x['artifacts'],[{'id':7}])
            self.assertEqual(x['metadata_recovery']['artifacts'][1]['state'],'COMPLETE')
    def test_empty_index_still_returns_partial_report(self):
        r=gather_bounded(DAY,REPO,invoke=lambda t,e:{'error_class':'HANDOFF_WORKER_TIMEOUT'})
        self.assertEqual(r['observed_schedule_count'],0)
        self.assertFalse(r['all_run_metadata_screened'])
        self.assertEqual(r['day_source_coverage']['authenticated_pc_slots'],0)
if __name__=='__main__':unittest.main()
