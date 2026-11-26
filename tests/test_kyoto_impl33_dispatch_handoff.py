"""Native delay recovery; no live JRA requests or production credentials."""
import copy, json, unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_impl30_nextday_adaptation import derive,make,recover,NAME,WORKFLOW,TARGET_DAY
from tests.test_kyoto_impl30_nextday_adaptation import saturday,REPO,SHA,KEY


def run(rid=101,event='workflow_dispatch',**kw):
    row=dict(id=rid,name=NAME,created_at='2026-11-28T12:00:00Z',event=event,status='completed',conclusion='success',head_repository={'full_name':REPO},head_branch='main',path='.github/workflows/'+WORKFLOW)
    row.update(kw);return row


def evidence(report,rid):
    return report,make(report,repo=REPO,run_id=rid,collector_sha=SHA,key=KEY)


def exercise(rows,payloads):
    calls=[]
    def api(args,**kw):
        ep=args[-1]
        if WORKFLOW in ep:return json.dumps({'total_count':len(rows),'workflow_runs':rows})
        if '/artifacts?' in ep:
            rid=int(ep.split('/runs/')[1].split('/')[0]);return json.dumps({'total_count':1,'artifacts':[{'name':f'kyoto-handoff-{rid}-20261128','expired':False}]})
        return json.dumps({'total_count':0,'workflow_runs':[]})
    def download(args,**kw):
        rid=int(args[3]);calls.append(rid);r,d=payloads[rid];p=Path(args[-1]);(p/'report.json').write_text(json.dumps(r));(p/'nextday_policy.json').write_text(json.dumps(d))
    with patch('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output',side_effect=api),patch('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.run',side_effect=download):
        result=recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY)
    return result,calls

class DispatchRecovery(unittest.TestCase):
    def test_verified_manual_source_keeps_scheduled_count_separate(self):
        r=saturday(paired=2);r['all_run_metadata_screened']=False;r['manual_source_assessment']=[{'run_id':123,'authenticated_pc_slot':True}]
        self.assertEqual(derive(r)['mode'],'MARKET_OR_ROSTER_RECOVERY');self.assertFalse(r['all_run_metadata_screened'])
        for bad in ([],[{'run_id':123,'authenticated_pc_slot':False}],[{'run_id':True,'authenticated_pc_slot':True}]):
            q=copy.deepcopy(r);q['manual_source_assessment']=bad;self.assertEqual(derive(q)['mode'],'BASELINE')
        r['github_run_listing_complete']=False;self.assertEqual(derive(r)['mode'],'BASELINE')
    def test_dispatch_only_signed_same_workflow(self):
        r=saturday(paired=2);r['all_run_metadata_screened']=False;r['manual_source_assessment']=[{'run_id':123,'authenticated_pc_slot':True}]
        result,calls=exercise([run()],{101:evidence(r,101)})
        self.assertEqual(result,('MARKET_OR_ROSTER_RECOVERY','AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_101'));self.assertEqual(calls,[101])
    def test_native_has_priority(self):
        result,calls=exercise([run(),run(102,'schedule')],{101:evidence(saturday(paired=2),101),102:evidence(saturday(),102)})
        self.assertEqual(result,('BASELINE','AUTHENTICATED_SATURDAY_HANDOFF_102'));self.assertEqual(calls,[102])
    def test_native_incomplete_or_corrupt_rescue(self):
        r,d=evidence(saturday(),102);d['hmac_sha256']='0'*64
        for native in (run(102,'schedule',status='in_progress',conclusion=None),run(102,'schedule')):
            result,calls=exercise([run(),native],{101:evidence(saturday(paired=2),101),102:(r,d)})
            self.assertEqual(result,('MARKET_OR_ROSTER_RECOVERY','AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_101'))
    def test_multiple_dispatches_newest_invalid_older_valid(self):
        r,d=evidence(saturday(),102);d['hmac_sha256']='0'*64
        result,calls=exercise([run(),run(102,created_at='2026-11-28T13:00:00Z')],{101:evidence(saturday(paired=2),101),102:(r,d)})
        self.assertEqual(result,('MARKET_OR_ROSTER_RECOVERY','AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_101'));self.assertEqual(calls,[102,101])
    def test_wrong_identity_not_downloaded(self):
        for changed in ({'head_branch':'other'},{'head_repository':{'full_name':'other/repo'}},{'path':'other'},{'created_at':'2026-11-29T00:00:00Z'},{'event':'push'},{'conclusion':'failure'}):
            result,calls=exercise([run(**changed)],{})
            self.assertEqual(result[0],'BASELINE');self.assertEqual(calls,[])
    def test_wrong_run_or_corrupt_signature_baseline(self):
        r,d=evidence(saturday(paired=2),102)
        result,calls=exercise([run()],{101:(r,d)})
        self.assertEqual(result[0],'BASELINE');self.assertEqual(calls,[101])

if __name__=='__main__':unittest.main()
