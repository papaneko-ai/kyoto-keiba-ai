"""Weekend-only bounded evidence handoff. No JRA HTTP or source mutation.

Each metadata/artifact worker has a killable process group and a shared wall
clock deadline; a slow download or parser cannot block the Saturday policy.
Historical C12 behavior is kept for Nov21. Only verified decrypted evidence
is merged; authorized manual runs remain separate from scheduled counts.
"""
from __future__ import annotations
import json, os, signal, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BUDGET_SECONDS = 600
WORKERS = 6
METADATA_CAP = 65
ARTIFACT_CAP = 180

def _worker(kind, day, repo, rid, lane):
    from diagnostics.kyoto_impl25_c12_all_runs_handoff import _gh, _download, WEEKENDS, _date
    if kind == 'index':
        if lane == 'aux':
            from diagnostics.kyoto_impl30_auxiliary_refresh import WORKFLOW
            filename = WORKFLOW
        else:
            filename = WEEKENDS[day][1]
        return _gh(f'repos/{repo}/actions/workflows/{filename}/runs?created={_date(day)}&per_page=100')
    if kind == 'metadata':
        j = _gh(f'repos/{repo}/actions/runs/{rid}/jobs?per_page=100')
        a = _gh(f'repos/{repo}/actions/runs/{rid}/artifacts?per_page=100')
        for doc, field in ((j, 'jobs'), (a, 'artifacts')):
            if not isinstance(doc[field], list) or doc['total_count'] != len(doc[field]) or any(not isinstance(x,dict) for x in doc[field]):
                raise ValueError('incomplete_metadata')
        return {'jobs': j['jobs'], 'artifacts': a['artifacts']}
    with tempfile.TemporaryDirectory(prefix='kyoto_bounded_handoff_') as tmp:
        root = Path(tmp); cipher = root/'cipher'; cipher.mkdir()
        if kind == 'lane':
            from diagnostics.kyoto_weekend_day21_artifact_triage import assess_lane
            _download(rid, f'kyoto-{lane.lower()}-{rid}-{day}', cipher, repo)
            return assess_lane(cipher, day=day, channel=lane, key=os.environ.get('ARCHIVE_KEY',''), repo=repo, run_id=str(rid))
        if kind == 'aux':
            from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
            from diagnostics.kyoto_impl30_day_coverage import extract_slot
            _download(rid, f'kyoto-auxiliary-{rid}-{day}', cipher, repo)
            raw = root/'raw'
            decrypt_evidence(cipher, raw, key_hex=os.environ.get('ARCHIVE_KEY',''), repo=repo, run_id=str(rid))
            receipt = json.loads((raw/'receipt.json').read_text())
            if receipt.get('day') != day or receipt.get('schema') != 'kyoto_impl30_auxiliary_refresh.v1':
                raise ValueError('auxiliary_identity')
            return extract_slot(raw, day, rid)
    raise ValueError('unknown_worker_kind')

def _invoke(task, end, clock=time.monotonic):
    kind, day, repo, rid, lane = task
    cap = METADATA_CAP if kind in ('index','metadata') else ARTIFACT_CAP
    remaining = min(cap, end-clock())
    if remaining <= 0:
        return {'error_class':'HANDOFF_DEADLINE_EXHAUSTED'}
    # No secrets on command line. A killed worker and its gh children share an
    # isolated process group; no thread can wait indefinitely for a parser.
    try:
        with tempfile.TemporaryDirectory(prefix='kyoto_handoff_result_') as tmp:
            out = Path(tmp)/'result.json'
            cmd = [sys.executable,'-m','diagnostics.kyoto_impl31_handoff_budget',kind,day,repo,str(rid),lane,str(out)]
            # When imported normally __name__ is the stable module name.
            with subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, env={**os.environ,"TMPDIR":tmp}) as proc:
                try:
                    proc.wait(timeout=max(0.001,min(remaining,end-clock())))
                except subprocess.TimeoutExpired:
                    try: os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    proc.wait()
                    return {'error_class':'HANDOFF_WORKER_TIMEOUT'}
                if proc.returncode != 0 or not out.is_file():
                    return {'error_class':'HANDOFF_WORKER_FAILED'}
                return json.loads(out.read_text())
    except Exception as exc:
        return {'error_class':type(exc).__name__}

def _index(response, day, repo, name, filename):
    from diagnostics.kyoto_impl25_c12_all_runs_handoff import _date
    if not isinstance(response,dict): return [],False,None
    rows=response.get('workflow_runs',[])
    if not isinstance(rows,list): return [],False,None
    total=response.get('total_count')
    complete=type(total) is int and total==len(rows) and len(rows)<=100
    seen=set(); verified=[]
    for r in rows[:100]:
        if not isinstance(r,dict): complete=False; continue
        rid=r.get('id')
        if (type(rid) is not int or rid<=0 or rid in seen or r.get('name')!=name
            or str(r.get('created_at',''))[:10]!=_date(day)
            or not isinstance(r.get('head_repository'),dict) or r['head_repository'].get('full_name')!=repo
            or str(r.get('path','')).split('@',1)[0]!='.github/workflows/'+filename):
            complete=False; continue
        seen.add(rid); verified.append(r)
    return sorted(verified,key=lambda r:(r['created_at'],r['id'])),complete,total

def gather_bounded(day, repo, *, invoke=_invoke, clock=time.monotonic, budget=BUDGET_SECONDS):
    from diagnostics.kyoto_impl25_c12_all_runs_handoff import WEEKENDS,summarize
    from diagnostics.kyoto_impl30_auxiliary_refresh import NAME,WORKFLOW
    from diagnostics.kyoto_impl30_day_coverage import combine
    end=clock()+budget
    def batch(tasks):
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            pending=[pool.submit(invoke,t,end) for t in tasks]
            return [f.result() for f in pending]
    def task(kind,rid=0,lane='main'): return kind,day,repo,rid,lane
    main,aux=batch([task('index'),task('index',lane='aux')])
    name,filename,_=WEEKENDS[day]
    runs,complete,total=_index(main,day,repo,name,filename)
    auxiliaries,aux_complete,_=_index(aux,day,repo,NAME,WORKFLOW)
    entries=[{'run':r} for r in runs]
    active=[e for e in entries if e['run'].get('status')=='completed' and e['run'].get('event') in ('schedule','workflow_dispatch')]
    metadata=batch([task('metadata',e['run']['id']) for e in active])
    work=[]; destinations=[]; aux_errors=[]; aux_slots=[]
    if not aux_complete: aux_errors.append({'error_class':'AUXILIARY_RUN_INDEX_INCOMPLETE'})
    for e,m in zip(active,metadata):
        if 'jobs' not in m or 'artifacts' not in m:
            e['metadata_error']=m.get('error_class','METADATA_UNAVAILABLE'); continue
        e.update(m,source_assessment={})
        for lane in ('PC','SP'):
            rid=e['run']['id']; expected=f'kyoto-{lane.lower()}-{rid}-{day}'
            found=[a for a in m['artifacts'] if a.get('name')==expected and a.get('expired') is False]
            if len(found)!=1:
                e['source_assessment'][lane]={'state':'EXACT_ARTIFACT_NOT_FOUND_OR_AMBIGUOUS'};continue
            work.append(task('lane',rid,lane));destinations.append((e,lane))
    for r in auxiliaries:
        if r.get('event') not in ('schedule','workflow_dispatch'):continue
        if r.get('status')!='completed':
            aux_errors.append({'run_id':r['id'],'error_class':'AUXILIARY_RUN_UNFINISHED'});continue
        work.append(task('aux',r['id']));destinations.append((r,None))
    for (dest,lane),value in zip(destinations,batch(work)):
        if lane is not None:
            if 'state' not in value: value={'state':'ARTIFACT_DOWNLOAD_FAILED','error_class':value.get('error_class','INVALID_WORKER_RESULT')}
            dest['source_assessment'][lane]=value
        elif value.get('day')==day and value.get('run_id')==str(dest['id']) and isinstance(value.get('races'),dict):
            aux_slots.append(value)
        else: aux_errors.append({'run_id':dest['id'],'error_class':value.get('error_class','AUXILIARY_WORKER_INVALID')})
    report=summarize(day,entries,total_count=total,pagination_complete=complete)
    slots=[]; manual=[]
    for e in entries:
        source=e.get('source_assessment',{}).get('PC',{})
        slot=source.get('day_coverage_slot')
        verified=(source.get('ciphertext_authenticated') is True and source.get('source_original_sha_utc_checked') is True and isinstance(slot,dict) and slot.get('day')==day and slot.get('run_id')==str(e['run']['id']))
        if verified: slots.append(slot)
        if e['run'].get('event')=='workflow_dispatch':
            manual.append({'run_id':e['run']['id'],'authenticated_pc_slot':verified,'state':e.get('metadata_error',source.get('state','NO_SOURCE_ASSESSMENT'))})
    report['manual_source_assessment']=manual
    # Preserve the separate independently authenticated SP evidence; never
    # promote structural roster observations into the PC/model denominator.
    from diagnostics.kyoto_impl32_sp_handoff import aggregate
    try:
        report['independent_sp_source_coverage']=aggregate(day,entries)
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        report['independent_sp_source_coverage_error']=type(exc).__name__
    report['authenticated_applied_policies']=[{'run_id':e['run']['id'],'event':e['run']['event'],'channel':lane,'policy':v['applied_policy']} for e in entries for lane,v in e.get('source_assessment',{}).items() if v.get('ciphertext_authenticated') is True and v.get('source_original_sha_utc_checked') is True and isinstance(v.get('applied_policy'),dict)]
    report['handoff_budget']={'limit_seconds':budget,'worker_limit':WORKERS,'source_tasks':len(work),'main_index_complete':complete,'auxiliary_index_complete':aux_complete,'deadline_exhausted':clock()>=end}
    try:
        coverage=combine(day,slots+aux_slots)
        coverage.update(authenticated_pc_slots=len(slots),authenticated_auxiliary_slots=len(aux_slots),auxiliary_errors=aux_errors,all_scheduled_run_metadata_screened=report['all_run_metadata_screened'],expected_scheduled_slots=report['expected_schedule_count'],unassessed_pc_slots=max(0,report['observed_schedule_count']-sum(1 for e in entries if e['run'].get('event')=='schedule' and any(s['run_id']==str(e['run']['id']) for s in slots))))
        report['day_source_coverage']=coverage
    except Exception as exc: report['day_source_coverage_error']=type(exc).__name__
    return report

if __name__=='__main__':
    kind,day,repo,rid,lane,out=sys.argv[1:]
    try: result=_worker(kind,day,repo,int(rid),lane)
    except Exception as exc: result={'error_class':type(exc).__name__}
    Path(out).write_text(json.dumps(result,sort_keys=True,allow_nan=False),encoding='utf8')
