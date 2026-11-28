"""Recompute postrace observations from original bytes, never from summary flags.
Separate evidence recheck for exact-day correction histories; no JRA HTTP.
"""
from pathlib import Path
from urllib.parse import urlsplit
from hashlib import sha256
import json,re,tempfile
from diagnostics.kyoto_impl30_postrace_day import MENU,observed_actions,select_navigation
from diagnostics.kyoto_impl30_final_reconcile import reconcile,append_revision,FinalEvidenceRejected
from diagnostics.kyoto_impl25_c12_all_runs_handoff import _gh,_download,_date,run_name_matches
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.p6_virtual_settlement_fixture_lab import _utc

WORKFLOW='kyoto-20261128-29-postrace-evidence.yml'
NAME='Kyoto Nov28-29 postrace result and payout evidence'

def reopen_navigation(root,day):
    """Reconstruct exact saved navigation. Absence is distinct from tampering."""
    root=Path(root)
    def read(name):
        p=root/name
        if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=1_500_000:raise FinalEvidenceRejected('missing_original:'+name)
        return p.read_bytes()
    receipt=json.loads(read('receipt.json'))
    if receipt.get('day')!=day or receipt.get('schema')!='kyoto_impl30_postrace_day.v1':raise FinalEvidenceRejected('wrong_postrace_receipt')
    seed=read('postrace_seed.html')
    if sha256(seed).hexdigest()!=receipt.get('seed_sha256'):raise FinalEvidenceRejected('seed_sha_mismatch')
    requests=receipt['requests'];by={m['file']:m for m in requests}
    if len(requests)!=len(by):raise FinalEvidenceRejected('duplicate_receipt_file')
    expected={'results_menu.html','results_meeting.html','payout_menu.html','payout_meeting.html'}|{f'r{n:02d}_result.html' for n in range(1,13)}
    if set(by)-expected:raise FinalEvidenceRejected('unexpected_navigation_receipt')
    for name in expected:
        p=root/name
        if (p.exists() or p.is_symlink())!=(name in by):raise FinalEvidenceRejected('receipt_original_inventory_mismatch')
    def bound(name,action,parent_stamp=None):
        if name not in by:return None
        m=by[name];raw=read(name)
        if (m['bytes']!=len(raw) or m['sha256']!=sha256(raw).hexdigest()):raise FinalEvidenceRejected('original_sha_mismatch')
        stamp=_utc(m['captured_at_utc'])
        if stamp.strftime('%Y%m%d')!=day or stamp.hour<10 or stamp.hour>=15 or (parent_stamp and stamp<_utc(parent_stamp)):raise FinalEvidenceRejected('wrong_capture_day_or_order')
        if (m['action_token'],m['method'],m['source_url'])!=action[1:]:raise FinalEvidenceRejected('observed_action_not_bound')
        return raw,m
    pages={};proofs=[];missing=[];results_key=None
    for market,(path,label) in MENU.items():
        menu_name=market+'_menu.html';meeting_name=market+'_meeting.html'
        if menu_name not in by:
            if meeting_name in by:raise FinalEvidenceRejected('orphan_meeting')
            missing.extend([menu_name,meeting_name]);continue
        candidates=[z for z in observed_actions(seed,path,origin=receipt.get('seed_origin','https://jra.jp')) if z[0]==label]
        if len(candidates)!=1:raise FinalEvidenceRejected('saved_menu_action_ambiguous')
        menu,mm=bound(menu_name,candidates[0]);pages[menu_name]=(menu,mm)
        try:action,proof=select_navigation(menu,day,market+'_meeting',origin='https://'+urlsplit(mm['source_url']).netloc)
        except ValueError:
            if meeting_name in by:raise
            missing.append(meeting_name);continue
        if meeting_name not in by:
            missing.append(meeting_name)
            if (proof['rule']=='OBSERVED_MODE_01_RECOVERY' and receipt.get(market+'_meeting_state')=='PostraceRejected:missing_or_ambiguous_observed_navigation'):
                proofs.append({**proof,'state':'PRIOR_FAILURE_REPRODUCED_RECOVERY_CANDIDATE'})
            continue
        meeting,meta=bound(meeting_name,action,mm['captured_at_utc']);pages[meeting_name]=(meeting,meta)
        if market=='results':results_key=proof['meeting']
    for race in range(1,13):
        name=f'r{race:02d}_result.html'
        if 'results_meeting.html' not in pages:
            if name in by:raise FinalEvidenceRejected('orphan_result_original')
            missing.append(name);continue
        parent,pm=pages['results_meeting.html']
        try:action,proof=select_navigation(parent,day,'result_race',origin='https://'+urlsplit(pm['source_url']).netloc,race=race,meeting=results_key)
        except ValueError:
            if name in by:raise
            missing.append(name);continue
        if name not in by:
            missing.append(name)
            reason=receipt.get('races',{}).get(str(race),{}).get('reason')
            if proof['rule']=='OBSERVED_MODE_01_RECOVERY' and reason=='PostraceRejected:missing_or_ambiguous_observed_navigation':
                proofs.append({**proof,'state':'PRIOR_FAILURE_REPRODUCED_RECOVERY_CANDIDATE'})
            continue
        # An invalid saved race must not erase the other 11. Record the exact
        # rejection and never use it as a positive observation.
        try:pages[name]=bound(name,action,pm['captured_at_utc'])
        except (ValueError,KeyError,TypeError,OSError) as exc:pages[name]={'rejected':type(exc).__name__+':'+str(exc)[:100]}
    return pages,proofs,missing

def saved_navigation_recovery(root,day):
    _,proofs,missing=reopen_navigation(root,day)
    return {'schema':'kyoto_postrace_navigation_recovery.v1','day':day,'recovery_candidates':proofs,'missing_originals':missing,'new_source_http_requests':0,'automatic_code_promotion':False}

def saved_observations(root,day,roster,starts):
    pages,_,missing=reopen_navigation(root,day)
    outcomes={}
    for race in range(1,13):
        name=f'r{race:02d}_result.html'
        try:
            if name in missing or 'payout_meeting.html' in missing:raise FinalEvidenceRejected('authenticated_original_not_observed')
            item=pages[name]
            if isinstance(item,dict):raise FinalEvidenceRejected('race_original_rejected:'+item['rejected'])
            raw,meta=item;payout,pm=pages['payout_meeting.html']
            if not roster[race] or not starts.get(race):raise FinalEvidenceRejected('no_independent_prerace_roster')
            outcomes[race]=reconcile(result_raw=raw,payout_raw=payout,day=day,race=race,registered=roster[race],
                result_url=meta['source_url'],result_utc=meta['captured_at_utc'],payout_utc=pm['captured_at_utc'],start_utc=starts[race])
        except (ValueError,KeyError,TypeError,OSError) as exc:outcomes[race]={'state':'PENDING','reason':type(exc).__name__+':'+str(exc)[:100]}
    return outcomes

def prior_archives(day,repo,key,current_run,*,cached=None):
    """Yield exact completed earlier captures; do not infer success from metadata."""
    response=_gh(f'repos/{repo}/actions/workflows/{WORKFLOW}/runs?created={_date(day)}&per_page=100')
    runs=response['workflow_runs']
    if response['total_count']!=len(runs) or len(runs)>100 or len({r['id'] for r in runs})!=len(runs):raise FinalEvidenceRejected('incomplete_prior_run_index')
    for run in sorted(runs,key=lambda x:(x['created_at'],x['id'])):
        if not run_name_matches(run,NAME,WORKFLOW,day) or run['created_at'][:10]!=_date(day):raise FinalEvidenceRejected('wrong_prior_workflow_or_day')
        rid=run['id']
        if str(rid)==str(current_run) or run['status']!='completed' or run['event'] not in ('schedule','workflow_dispatch'):continue
        if cached and str(rid) in cached:
            yield rid,cached[str(rid)],None;continue
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

def replay_history(current,*,day,repo,key,current_run,roster,starts,cached_prior=None):
    """Reconstruct version sequence from authenticated bytes per race, never overwrite previous source."""
    reports=[];complete=True;observations={i:[] for i in range(1,13)};published={i:[] for i in range(1,13)}
    def add(rid,raw):
        nonlocal complete
        try:
            verified=saved_observations(raw,day,roster,starts)
            for race,obs in verified.items():
                if obs.get('state')=='DUAL_PAGE_EXPLICIT_FINAL':observations[race].append((rid,obs))
                if obs.get('official_payout_publication_verified') is True:published[race].append({'run_id':rid,'observation':obs})
            reports.append({'run_id':rid,'recomputed_races':len(verified),'explicit_final_matches':sum(o.get('state')=='DUAL_PAGE_EXPLICIT_FINAL' for o in verified.values()),'pending_races':{str(n):o.get('reason') for n,o in verified.items() if o.get('state')=='PENDING'}})
        except Exception as exc:
            complete=False;reports.append({'run_id':rid,'error_class':type(exc).__name__})
    try:
        for rid,raw,error in prior_archives(day,repo,key,current_run,**({'cached':cached_prior} if cached_prior else {})):
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
