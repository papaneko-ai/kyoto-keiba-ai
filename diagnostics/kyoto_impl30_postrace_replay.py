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

# JRA's official race-finality and payout rules establish that published
# payouts follow confirmed placings. This separate evidence chain is not
# an explicit finality marker, a permanently fixed sporting result, or
# permission to settle an investment.
PUBLISHED_RULES=(
    'https://www.jra.go.jp/keiba/rules/kakutei.html',
    'https://www.jra.go.jp/kouza/baken/index.html',
    'https://www.jra.go.jp/faq/pop03/1_6.html',
)

def published_history(entries,*,day,race):
    """Deterministic, no overwrite; conflicting amounts never certify a race."""
    from hashlib import sha256
    def canonical(x):
        return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if not entries:return {'state':'MISSING','revisions':[]}
    revisions=[];last=None;seen=set();head='0'*64
    try:
        for entry in sorted(entries,key=lambda e:(max(_utc(e['observation'][k]) for k in ('result_utc','payout_utc')),str(e['run_id']))):
            rid=str(entry['run_id']);obs=entry['observation']
            if (not rid.isdigit() or rid in seen or obs.get('day')!=day or obs.get('race')!=race
                or obs.get('official_payout_publication_verified') is not True
                or obs.get('settlement_authorized') is not False
                or set(obs['markets'])!={'quinella','bracket_quinella'}
                or any(not re.fullmatch(r'[a-f0-9]{64}',obs[k]) for k in ('result_sha256','payout_sha256'))
                or obs['result_sha256']==obs['payout_sha256']):
                raise FinalEvidenceRejected('published_identity')
            seen.add(rid)
            if last is not None and last['markets']!=obs['markets']:
                if obs.get('correction') is not True or min(_utc(obs[k]) for k in ('result_utc','payout_utc'))<=max(_utc(last[k]) for k in ('result_utc','payout_utc')):
                    raise FinalEvidenceRejected('published_amount_conflict')
            body={'version':len(revisions)+1,'run_id':rid,'previous_sha256':head,'observation':obs}
            head=sha256(canonical(body)).hexdigest()
            revisions.append({**body,'sha256':head})
            last=obs
    except (ValueError,KeyError,TypeError,AttributeError) as exc:
        return {'state':'CONFLICT','reason':str(exc)[:100],'revisions':revisions}
    return {'state':'OFFICIAL_PUBLISHED_PAYOUT_CHAIN','revisions':revisions,'rules':list(PUBLISHED_RULES),'settlement_authorized':False}

def replay_history(current,*,day,repo,key,current_run,roster,starts):
    """Reconstruct version sequence from authenticated bytes per race, never overwrite previous source."""
    reports=[];complete=True;observations={i:[] for i in range(1,13)};published={i:[] for i in range(1,13)}
    def add(rid,raw):
        nonlocal complete
        try:
            verified=saved_observations(raw,day,roster,starts)
            for race,obs in verified.items():
                if obs.get('state')=='DUAL_PAGE_EXPLICIT_FINAL':observations[race].append((rid,obs))
                if obs.get('official_payout_publication_verified') is True:published[race].append({'run_id':rid,'observation':obs})
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
    return {'schema':'kyoto_impl30_postrace_replay.v1','day':day,'prior_artifact_index_complete':complete,'run_evidence':reports,'races':races,'published_source_observations':{str(k):v for k,v in published.items()},'published_payout_chains':{str(k):published_history(v,day=day,race=k) for k,v in published.items()},'settlement_authorized':False}
