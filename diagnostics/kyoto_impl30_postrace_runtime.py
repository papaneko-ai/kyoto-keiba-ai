"""Scheduled source-only postrace entrypoint. Reuse authenticated PC evidence,
independent G03 reparsing, observed menu navigation and existing AES archive.
No synthetic URL, pre-race data promotion, settlement, or production DB write.
"""
import argparse,json,os,re,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from urllib.parse import urlsplit,parse_qs,urlencode
from urllib.request import Request,build_opener,HTTPCookieProcessor
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from diagnostics.kyoto_impl25_c12_all_runs_handoff import _gh,_download,WEEKENDS,_date
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence,encrypt_evidence
from diagnostics.kyoto_g03_independent_partial import verify_partial
from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
from diagnostics.kyoto_impl30_postrace_day import collect_day,observed_actions,MENU
from diagnostics.jra_one_shot_market_capture import RequestPacer,NoRedirect

DAYS=('20261128','20261129')
def recover_inputs(day,repo,key,*,include_coverage=False):
    if day not in DAYS or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('bad_day_or_repository')
    workflow,file,_=WEEKENDS[day]
    index=_gh(f'repos/{repo}/actions/workflows/{file}/runs?created={_date(day)}&per_page=100')
    runs=index['workflow_runs']
    if index['total_count']!=len(runs) or len(runs)>100 or len({r['id'] for r in runs})!=len(runs):raise ValueError('run_listing_incomplete')
    roster={r:None for r in range(1,13)};starts={};seed=None;sources={};rejected=[];conflicts=set()
    coverage_slots=[];coverage_errors=[]
    for run in sorted(runs,key=lambda r:r['id'],reverse=True):
        rid=run['id']
        if run['name']!=workflow or run['created_at'][:10]!=_date(day):raise ValueError('wrong_run_identity')
        if run['status']!='completed' or run['event'] not in ('schedule','workflow_dispatch'):continue
        try:
            arts=_gh(f'repos/{repo}/actions/runs/{rid}/artifacts?per_page=100')
            if arts['total_count']!=len(arts['artifacts']):raise ValueError('artifact_listing_incomplete')
            name=f'kyoto-pc-{rid}-{day}'
            found=[a for a in arts['artifacts'] if a['name']==name and a['expired'] is False]
            if len(found)!=1:continue
            with tempfile.TemporaryDirectory(prefix='kyoto_postrace_') as tmp:
                base=Path(tmp);cipher=base/'cipher';cipher.mkdir();raw=base/'raw'
                _download(rid,name,cipher,repo)
                decrypt_evidence(cipher,raw,key_hex=key,repo=repo,run_id=str(rid))
                if include_coverage:
                    try:
                        from diagnostics.kyoto_impl30_day_coverage import extract_slot
                        coverage_slots.append(extract_slot(raw,day,rid))
                    except Exception as exc:
                        coverage_errors.append({"run_id":rid,"error_class":type(exc).__name__})
                verified=verify_partial(raw,expected_day=day)['verified_race_numbers']
                records=records_from_g03(raw,day=day,skip_invalid_races=True)
                for race in verified:
                    item=records[race]
                    if item is None:continue
                    named=item['expected_named_runners'];start=item['verified_start_utc']
                    if race in conflicts:continue
                    if roster[race] is not None and (roster[race]!=named or starts[race]!=start):
                        conflicts.add(race);roster[race]=None;starts.pop(race,None);sources.pop(str(race),None);continue
                    path=raw/f'g03_official_racecard_{race:02d}.html'
                    original=path.read_bytes()
                    if roster[race] is None:
                        roster[race]=named;starts[race]=start;sources[str(race)]={'run_id':rid,'sha256':sha256(original).hexdigest()}
                    if seed is None and all(any(a[0]==label for a in observed_actions(original,p)) for p,label in MENU.values()):
                        seed=original
        except Exception as exc:rejected.append({'run_id':rid,'error_class':type(exc).__name__})
    if seed is None:raise ValueError('no_verified_observed_postrace_menu_seed')
    proof={'sources':sources,'rejected_runs':rejected,'conflicting_races':sorted(conflicts)}
    if include_coverage:
        # Day aggregation is not a hard prerequisite for official result GETs.
        # Preserve the already verified roster even when this diagnostic fails.
        try:
            from diagnostics.kyoto_impl30_day_coverage import combine
            proof["day_source_coverage"]=combine(day,coverage_slots)
            proof["day_source_coverage"]["slot_errors"]=coverage_errors
        except Exception as exc:
            proof["day_source_coverage_error"]=type(exc).__name__
    return roster,starts,seed,proof

def official_fetcher(day,*,clock=None,opener=None,pacer=None):
    """Separate evening window. Global access refusal stops further HTTP."""
    clock=clock or (lambda:datetime.now(timezone.utc))
    client=opener or build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
    pacer=pacer or RequestPacer();refused=False;count=0
    def fetch(method,url,token):
        nonlocal refused,count
        if refused:raise ValueError('prior_access_refusal')
        now=clock()
        if now.strftime('%Y%m%d')!=day or not 10<=now.hour<15:raise ValueError('outside_postrace_window')
        u=urlsplit(url)
        if u.scheme!='https' or u.netloc not in ('jra.jp','www.jra.go.jp') or u.path not in (x[0] for x in MENU.values()) or u.fragment or not re.fullmatch(r'pw[A-Za-z0-9]+/[A-Za-z0-9]+',token):raise ValueError('invalid_official_target')
        if method=='POST' and not u.query:body=urlencode({'cname':token}).encode('ascii')
        elif method=='GET' and parse_qs(u.query)=={'CNAME':[token]}:body=None
        else:raise ValueError('invalid_observed_action')
        if count>=16:raise ValueError('postrace_request_cap')
        pacer.before_request();count+=1
        req=Request(url,data=body,method=method,headers={'Accept':'text/html','User-Agent':'Mozilla/5.0','Content-Type':'application/x-www-form-urlencoded'})
        try:
            with client.open(req,timeout=20) as response:
                raw=response.read(1_500_001)
                if response.geturl()!=url:
                    refused=True
                    raise ValueError('response_url_mismatch')
                if response.status!=200 or 'html' not in response.headers.get('Content-Type','').lower() or not 0<len(raw)<=1_500_000:raise ValueError('response_rejected')
        except HTTPError as exc:
            if exc.code in (401,403,429):refused=True
            raise
        except ValueError as exc:
            if 'redirect_forbidden' in str(exc):refused=True
            raise
        return {'raw':raw,'captured_at_utc':clock().isoformat(),'requested_url':url,'method':method,'observed_action_token':token}
    return fetch

def main():
    p=argparse.ArgumentParser();p.add_argument('--day',choices=DAYS,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    day=a.day;repo=os.environ['GITHUB_REPOSITORY'];rid=os.environ['GITHUB_RUN_ID'];key=os.environ['ARCHIVE_KEY']
    if os.environ.get('KYOTO_TARGET_DAY')!=day or os.environ.get('KYOTO_POSTRACE_HTTP_APPROVED')!='YES' or os.environ.get('GITHUB_EVENT_NAME') not in ('schedule','workflow_dispatch'):raise ValueError('live_postrace_not_authorized')
    now=datetime.now(timezone.utc)
    if now.strftime('%Y%m%d')!=day or not 10<=now.hour<15 or not re.fullmatch(r'[a-fA-F0-9]{64}',key):raise ValueError('postrace_window_or_key_invalid')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kyoto_postrace_runtime_') as tmp:
        raw=Path(tmp)/'raw'
        try:
            roster,starts,seed,proof=recover_inputs(day,repo,key,include_coverage=True)
            cutoff=datetime.fromisoformat(_date(day)+'T10:00:00+00:00')
            report=collect_day(raw,day=day,seed_raw=seed,seed_sha256=sha256(seed).hexdigest(),
                registered=roster,verified_starts=starts,fetch=official_fetcher(day),
                clock=lambda:datetime.now(timezone.utc).isoformat(),not_before_utc=cutoff.isoformat())
            (raw/'postrace_input_proof.json').write_text(json.dumps(proof,sort_keys=True,ensure_ascii=False),encoding='utf8')
            (raw/'postrace_seed.html').write_bytes(seed)
            # Re-open current and previous authenticated pages; only the
            # independently reconstructed chain, not earlier PASS flags, is retained.
            from diagnostics.kyoto_impl30_postrace_replay import replay_history
            revisions=replay_history(raw,day=day,repo=repo,key=key,current_run=rid,roster=roster,starts=starts)
            (raw/'postrace_revision_history.json').write_text(json.dumps(revisions,sort_keys=True,ensure_ascii=False),encoding='utf8')
            if "day_source_coverage" in proof:
                from diagnostics.kyoto_impl30_day_coverage import include_postrace
                proof["day_source_coverage"]=include_postrace(proof["day_source_coverage"],revisions,roster=roster,starts=starts)
                (raw/'postrace_input_proof.json').write_text(json.dumps(proof,sort_keys=True,ensure_ascii=False),encoding='utf8')
        except Exception as exc:
            raw.mkdir(exist_ok=True)
            if not (raw/'receipt.json').exists():
                (raw/'receipt.json').write_text(json.dumps({'day':day,'state':'POSTRACE_INCOMPLETE','error_class':type(exc).__name__,'settlement_authorized':False}),encoding='utf8')
        finally:
            # The shared encrypted archive has an explicit postrace allowlist.
            encrypt_evidence(raw,a.out,key_hex=key,repo=repo,run_id=rid)
    print('POSTRACE_ENCRYPTED_SOURCE_ONLY=TRUE')
if __name__=='__main__':main()
