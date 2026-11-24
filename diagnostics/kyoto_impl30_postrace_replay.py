"""Recompute postrace observations from original bytes, never from summary flags.
Separate evidence recheck for exact-day correction histories; no JRA HTTP.
"""
from pathlib import Path
from hashlib import sha256
import json,re,tempfile
from diagnostics.kyoto_impl30_postrace_day import MENU,observed_actions
from diagnostics.kyoto_impl30_final_reconcile import reconcile,append_revision,FinalEvidenceRejected
from diagnostics.kyoto_impl25_c12_all_runs_handoff import _gh,_download,_date
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.p6_virtual_settlement_fixture_lab import _utc

WORKFLOW='kyoto-20261128-29-postrace-evidence.yml'
NAME='Kyoto Nov28-29 postrace result and payout evidence'

def saved_observations(root,day,roster,starts):
    root=Path(root)
    def read(name):
        path=root/name
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=1_500_000:raise FinalEvidenceRejected('missing_original:'+name)
        return path.read_bytes()
    receipt=json.loads(read('receipt.json'))
    if receipt.get('day')!=day or receipt.get('schema')!='kyoto_impl30_postrace_day.v1':raise FinalEvidenceRejected('wrong_postrace_receipt')
    seed=read('postrace_seed.html')
    if sha256(seed).hexdigest()!=receipt.get('seed_sha256'):raise FinalEvidenceRejected('seed_sha_mismatch')
    requests=receipt['requests'];by_name={x['file']:x for x in requests}
    if len(requests)!=len(by_name):raise FinalEvidenceRejected('duplicate_receipt_file')
    def bound(name,parent,path):
        meta=by_name[name];raw=read(name)
        if len(raw)!=meta['bytes'] or sha256(raw).hexdigest()!=meta['sha256']:raise FinalEvidenceRejected('original_sha_mismatch')
        if _utc(meta['captured_at_utc']).strftime('%Y%m%d')!=day:raise FinalEvidenceRejected('wrong_capture_day')
        matches=[x for x in observed_actions(parent,path) if (x[1],x[2],x[3])==(meta['action_token'],meta['method'],meta['source_url'])]
        if len(matches)!=1:raise FinalEvidenceRejected('observed_action_not_bound')
        return raw,meta
    menus={}
    for market,(path,label) in MENU.items():
        menu,_=bound(market+'_menu.html',seed,path)
        menus[market]=bound(market+'_meeting.html',menu,path)
    payout,pm=menus['payout'];result_meeting,_=menus['results']
    outcomes={}
    for race in range(1,13):
        try:
            raw,meta=bound(f'r{race:02d}_result.html',result_meeting,MENU['results'][0])
            if not roster[race] or not starts.get(race):raise FinalEvidenceRejected('no_independent_prerace_roster')
            outcomes[race]=reconcile(result_raw=raw,payout_raw=payout,day=day,race=race,registered=roster[race],
                result_url=meta['source_url'],result_utc=meta['captured_at_utc'],payout_utc=pm['captured_at_utc'],start_utc=starts[race])
        except (ValueError,KeyError,TypeError,OSError) as exc:outcomes[race]={'state':'PENDING','reason':type(exc).__name__+':'+str(exc)[:100]}
    return outcomes

def prior_archives(day,repo,key,current_run):
    """Yield exact completed earlier captures; do not infer success from metadata."""
    response=_gh(f'repos/{repo}/actions/workflows/{WORKFLOW}/runs?created={_date(day)}&per_page=100')
    runs=response['workflow_runs']
    if response['total_count']!=len(runs) or len(runs)>100 or len({r['id'] for r in runs})!=len(runs):raise FinalEvidenceRejected('incomplete_prior_run_index')
    for run in sorted(runs,key=lambda x:(x['created_at'],x['id'])):
        if run['name']!=NAME or run['created_at'][:10]!=_date(day):raise FinalEvidenceRejected('wrong_prior_workflow_or_day')
        rid=run['id']
        if str(rid)==str(current_run) or run['status']!='completed' or run['event'] not in ('schedule','workflow_dispatch'):continue
        with tempfile.TemporaryDirectory(prefix='kyoto_postrace_prior_') as tmp:
            target=Path(tmp)/'cipher';target.mkdir();raw=Path(tmp)/'raw'
            try:
                index=_gh(f'repos/{repo}/actions/runs/{rid}/artifacts?per_page=100')
                if index['total_count']!=len(index['artifacts']):raise FinalEvidenceRejected('prior_artifact_listing_incomplete')
                name=f'kyoto-postrace-{rid}-{day}'
                found=[a for a in index['artifacts'] if a['name']==name and a['expired'] is False]
                if len(found)!=1:raise FinalEvidenceRejected('prior_artifact_missing_or_ambiguous')
                _download(rid,name,target,repo);decrypt_evidence(target,raw,key_hex=key,repo=repo,run_id=str(rid))
            except Exception as exc:
                yield rid,None,type(exc).__name__;continue
            yield rid,raw,None

def replay_history(current,*,day,repo,key,current_run,roster,starts):
    """Reconstruct version sequence from authenticated bytes per race, never overwrite previous source."""
    reports=[];complete=True;observations={i:[] for i in range(1,13)}
    def add(rid,raw):
        nonlocal complete
        try:
            verified=saved_observations(raw,day,roster,starts)
            for race,obs in verified.items():
                if obs.get('state')=='DUAL_PAGE_EXPLICIT_FINAL':observations[race].append((rid,obs))
            reports.append({'run_id':rid,'recomputed_races':len(verified),'explicit_final_matches':sum(o.get('state')=='DUAL_PAGE_EXPLICIT_FINAL' for o in verified.values())})
        except Exception as exc:
            complete=False;reports.append({'run_id':rid,'error_class':type(exc).__name__})
    try:
        for rid,raw,error in prior_archives(day,repo,key,current_run):
            if raw is None:complete=False;reports.append({'run_id':rid,'error_class':error})
            else:add(rid,raw)
    except Exception as exc:complete=False;reports.append({'state':'PRIOR_INDEX_UNAVAILABLE','error_class':type(exc).__name__})
    add(current_run,current)
    races={}
    with tempfile.TemporaryDirectory(prefix='kyoto_postrace_revisions_') as tmp:
        for race,entries in observations.items():
            changes=[];conflict=False
            for rid,obs in sorted(entries,key=lambda item:(max(_utc(item[1][k]) for k in ('result_utc','payout_utc')),str(item[0]))):
                try:
                    result=append_revision(Path(tmp)/str(race),obs)
                    changes.append({'run_id':rid,**result,'observation':obs})
                except (ValueError,KeyError,OSError) as exc:
                    conflict=True;changes.append({'run_id':rid,'state':'REVISION_CONFLICT','reason':type(exc).__name__})
            races[str(race)]={'revisions':changes,'state':'CONFLICT' if conflict else 'SOURCE_REVISION_CHAIN' if changes else 'NO_EXPLICIT_FINAL_OBSERVATION'}
    return {'schema':'kyoto_impl30_postrace_replay.v1','day':day,'prior_artifact_index_complete':complete,'run_evidence':reports,'races':races,'settlement_authorized':False}
