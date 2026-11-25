"""No-JRA schedule rehearsal: real trigger evidence kept separate from mock days."""
import argparse, hashlib, json, os, re, shutil, socket, subprocess, tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from contextlib import ExitStack
from diagnostics.kyoto_impl30_nextday_adaptation import make, WORKFLOW, NAME, TARGET_DAY
from diagnostics.kyoto_weekend_capture import capture,seal
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics import kyoto_nov15_encrypted_evidence as crypto
KEY='ab'*32 # public test key, never production key

def write(p,v):
    p.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n',encoding='utf8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def context():
    event=os.getenv('GITHUB_EVENT_NAME','local')
    cron=os.getenv('GITHUB_EVENT_SCHEDULE','')
    run=os.getenv('GITHUB_RUN_ID','0')
    collector=os.getenv('REHEARSAL_COLLECTOR_SHA','0'*40)
    repo=os.getenv('GITHUB_REPOSITORY','local/test')
    if not re.fullmatch('[0-9a-f]{40}',collector) or not run.isdigit():raise ValueError('identity')
    allowed_cron={'0 3 25 11 *':'20261125','30 3 25 11 *':'20261125','15 0 26 11 *':'20261126','45 0 26 11 *':'20261126'}
    actual=event=='schedule' and cron in allowed_cron and os.getenv('GITHUB_REF')=='refs/heads/main' and run!='0' and datetime.now(timezone.utc).strftime('%Y%m%d')==allowed_cron[cron]
    if event=='schedule' and not actual:raise ValueError('not_exact_rehearsal_date_or_ref')
    return dict(event=event,cron=cron,run_id=run,collector_sha=collector,repo=repo,actual_schedule_event=actual)
def prepare(out):
    c=context();out.mkdir(parents=True)
    report={'day':'20261128','next_day':'20261129','all_run_metadata_screened':False,'github_run_listing_complete':False,'scheduled_runs':[{'run':{'id':44854931835,'event':'schedule','created_at':'2026-11-28T01:00:00Z','status':'completed'},'state':'ALL_LANES_CLASSIFIED','lanes':{'PC':{'job_conclusion':'failure','job_state':'FAILED_WITH_ARTIFACT','failure_stage':'OFFLINE_REGRESSION','artifact_evidence_state':'PRE_HTTP_SAFE_STOP_NO_SOURCE'}}}], 'rehearsal_only':True}
    doc=make(report,repo=c['repo'],run_id=c['run_id'],collector_sha=c['collector_sha'],key=KEY)
    assert doc['body']['decision']['mode']=='MARKET_OR_ROSTER_RECOVERY'
    write(out/'report.json',report);write(out/'nextday_policy.json',doc)
    write(out/'trigger.json',dict(c,mock_source_day='20261128',mock_target_day='20261129',report_sha256=sha(out/'report.json'),policy_sha256=sha(out/'nextday_policy.json')))

def consume(inp,out):
    c=context(); original=json.loads((inp/'trigger.json').read_text())
    assert all(original[k]==v for k,v in c.items())
    assert original['report_sha256']==sha(inp/'report.json') and original['policy_sha256']==sha(inp/'nextday_policy.json')
    out.mkdir(parents=True);results=[]
    def forbidden(*a,**kw): raise AssertionError('NETWORK_FORBIDDEN_IN_DUMMY')
    def discover(root,**kw):
        root.mkdir();(root/'sp_discovery_receipt.json').write_text('{}')
        return {'network_requests_started':0,'racecard_url':'fixture'}
    for case,expect,seconds in [('signed','MARKET_OR_ROSTER_RECOVERY',360),('missing','BASELINE',240),('tampered','BASELINE',240)]:
        def api(args,**kw):
            ep=args[-1]
            if WORKFLOW in ep:
                rows=[] if case=='missing' else [dict(id=int(c['run_id']),name=NAME,created_at='2026-11-28T12:00:00Z',event='schedule',status='completed',conclusion='success',head_repository={'full_name':c['repo']},path='.github/workflows/'+WORKFLOW)]
                return json.dumps(dict(total_count=len(rows),workflow_runs=rows))
            if '/artifacts?' in ep:return json.dumps({'total_count':1,'artifacts':[{'name':f"kyoto-handoff-{c['run_id']}-20261128",'expired':False}]})
            return json.dumps({'total_count':0,'workflow_runs':[]})
        def download(args,**kw):
            assert args[:3]==['gh','run','download']; dest=Path(args[args.index('--dir')+1]);shutil.copyfile(inp/'report.json',dest/'report.json');shutil.copyfile(inp/'nextday_policy.json',dest/'nextday_policy.json')
            if case=='tampered':
                d=json.loads((dest/'nextday_policy.json').read_text());d['hmac_sha256']='0'*64;write(dest/'nextday_policy.json',d)
        env={'KYOTO_TARGET_DAY':TARGET_DAY,'KYOTO_WEEKEND_HTTP_APPROVED':'YES','GITHUB_EVENT_NAME':'schedule','ARCHIVE_KEY':KEY,'GITHUB_REPOSITORY':c['repo'],'COLLECTOR_SHA':c['collector_sha']}
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root=Path(tmp)/'raw';sealed=Path(tmp)/'sealed';decoded=Path(tmp)/'decoded'
            for target,kwargs in [('socket.socket.connect',{'side_effect':forbidden}),('socket.create_connection',{'side_effect':forbidden}),('diagnostics.kyoto_weekend_capture.validate_day',{}),('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output',{'side_effect':api}),('diagnostics.kyoto_impl30_nextday_adaptation.subprocess.run',{'side_effect':download}),('diagnostics.kyoto_weekend_sp_discovery.discover',{'side_effect':discover})]:stack.enter_context(patch(target,**kwargs))
            stack.enter_context(patch.dict(os.environ,env));stack.enter_context(patch.object(crypto,'DAY',TARGET_DAY))
            if __import__('importlib').util.find_spec('diagnostics.kyoto_impl31_sp_gap_plan') is not None:stack.enter_context(patch('diagnostics.kyoto_impl31_sp_gap_plan.get_plan',return_value=None))
            acq=stack.enter_context(patch('diagnostics.kyoto_sp_all12_observed_capture.capture_all',return_value={'races':{}}))
            r=capture(TARGET_DAY,'SP',str(root),live=True,opener=object());acq.assert_called_once()
            receipt=json.loads((root/'nextday_applied_policy.json').read_text());assert receipt['selected_policy']==expect and receipt['sp_seconds']==seconds
            assert r['observed_http_requests_started']==0 and r['prediction_ready'] is False
            seal(TARGET_DAY,str(root),str(sealed),key=KEY,repo=c['repo'],run_id=c['run_id']);decrypt_evidence(sealed,decoded,key_hex=KEY,repo=c['repo'],run_id=c['run_id'])
            assert json.loads((decoded/'nextday_applied_policy.json').read_text())==receipt
            results.append(dict(case=case,policy=expect,seconds=seconds,encrypted_receipt_verified=True,mocked_capture=True))
    write(out/'receipt.json',dict(c,cases=results,jra_http_attempts=0,live_acquisition_proved=False,artifact_sha256_verified=True,simulated_race_days=True))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','consume']);p.add_argument('--input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.out) if a.phase=='prepare' else consume(a.input,a.out)
