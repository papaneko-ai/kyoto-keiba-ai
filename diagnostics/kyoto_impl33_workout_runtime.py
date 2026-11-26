"""Independent bounded workout capture and roster bridge. No official-source HTTP.
Use existing authenticated PC originals; retain third-party originals separately.
"""
import json, os, re, secrets, subprocess, tempfile, time
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_impl33_whitegreen_probe import HOST, AGENT, JST, get, text
from diagnostics.kyoto_impl33_workout_generic import discover, bridge, candidate_links, parse_observed
from diagnostics.kyoto_impl33_hybrid_workout import parse_table_v3,parse_labeled_turf,recover,preserve_partial
from diagnostics.kyoto_g03_independent_partial import verify_partial
from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.kyoto_impl31_workout_intake import inspect_workouts

DAYS=('20261128','20261129')
REPO='papaneko-ai/kyoto-keiba-ai'
OBSERVER='kyoto-20261128-29-two-source-production-observer.yml'
WORKFLOW='kyoto-20261128-29-workout-source.yml'
PRIMARY_INDEX=HOST+'/keiba/'
SECONDARY={'umasiru.com':'https://umasiru.com/','talmudic.net':'https://talmudic.net/'}
# Observed current published link; not a hardcoded horse or fabricated URL.
SEEDS={('20261128',11):['https://umasiru.com/archives/22515']}
PREVIEW_RUN=45755377155
def digest(raw):return sha256(raw).hexdigest()
def utc(s):
    t=datetime.fromisoformat(s.replace('Z','+00:00'))
    if t.utcoffset()!=timedelta(0):raise ValueError('utc')
    return t
def day_iso(day):return day[:4]+'-'+day[4:6]+'-'+day[6:]
def now():return datetime.now(timezone.utc)
def official(root,day,rid):
    verified=verify_partial(root,expected_day=day)['verified_race_numbers']
    records=records_from_g03(root,day=day,skip_invalid_races=True)
    proof=json.loads((Path(root)/'g03_receipt.json').read_text())
    found={}
    for r in verified:
        rec=records[r]
        if not rec:continue
        row=proof['races'][str(r)]
        roster={n:name for n,_,name in rec['expected_named_runners']}
        found[r]={'roster':roster,'start':rec['verified_start_utc'],'source_sha256':row['original_sha256'],'captured_utc':row['captured_at_utc'],'run_id':rid}
    return found

def roster_union(found,other,conflicts):
    for race,v in other.items():
        if race in conflicts:continue
        if race in found and (found[race]['roster'],found[race]['start'])!=(v['roster'],v['start']):
            conflicts.add(race);found.pop(race,None)
        elif race not in found:found[race]=v
    return found

class Budget:
    def __init__(self,seconds):self.end=time.monotonic()+seconds
    def remaining(self,cap=15):
        n=self.end-time.monotonic()
        if n<=0:raise TimeoutError('budget')
        return min(cap,n)
    def api(self,path):
        return json.loads(subprocess.check_output(['gh','api',path],stderr=subprocess.DEVNULL,text=True,timeout=self.remaining(12)))
    def download(self,rid,name,dest):
        subprocess.run(['gh','run','download',str(rid),'--repo',REPO,'--name',name,'--dir',str(dest)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=self.remaining(30))

def eligible_runs(budget,day,workflow):
    index=budget.api(f'repos/{REPO}/actions/workflows/{workflow}/runs?per_page=100')
    rows=index['workflow_runs']
    if index['total_count']!=len(rows) or len(rows)>100:raise ValueError('run_index_incomplete')
    out=[]
    for r in rows:
        if r.get('status')!='completed' or r.get('head_branch')!='main' or r.get('head_repository',{}).get('full_name')!=REPO:continue
        if r.get('path','').split('@',1)[0]!='.github/workflows/'+workflow:continue
        if not isinstance(r.get('id'),int) or r['id']<=0:continue
        if workflow==OBSERVER and (r.get('event') not in ('schedule','workflow_dispatch') or r['created_at'][:10]!=day_iso(day)):continue
        if workflow==WORKFLOW and r.get('event') not in ('schedule','workflow_dispatch','workflow_run'):continue
        out.append(r)
    return sorted(out,key=lambda r:r['id'],reverse=True)

def gather_official(day,key,budget):
    found={};conflicts=set();issues=[]
    try:
        rows=eligible_runs(budget,day,OBSERVER)
        for r in rows[:8]:
            rid=r['id']
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    cipher=Path(tmp)/'cipher';cipher.mkdir();root=Path(tmp)/'raw'
                    budget.download(rid,f'kyoto-pc-{rid}-{day}',cipher)
                    decrypt_evidence(cipher,root,key_hex=key.hex(),repo=REPO,run_id=str(rid))
                    roster_union(found,official(root,day,rid),conflicts)
            except Exception as e:issues.append(type(e).__name__)
    except Exception as e:issues.append(type(e).__name__)
    return found,sorted(conflicts),issues

def seal(out,name,raw,key,aad):
    nonce=secrets.token_bytes(12);blob=nonce+AESGCM(key).encrypt(nonce,raw,aad)
    if AESGCM(key).decrypt(blob[:12],blob[12:],aad)!=raw:raise ValueError('seal_readback')
    p=out/name;tmp=out/(name+'.tmp');tmp.write_bytes(blob);tmp.replace(p)
    return digest(blob)

def source_record(raw,stamp,url,kind,race):
    if utc(stamp)>now()+timedelta(seconds=30):raise ValueError('future_capture')
    return {'raw':raw,'stamp':utc(stamp).isoformat(),'url':url,'kind':kind,'race':race}

def read_snapshot(blob,meta,key,expected_aad):
    if meta['archive_aad'].encode()!=expected_aad or digest(blob)!=meta['ciphertext_sha256']:raise ValueError('cipher_identity')
    raw=AESGCM(key).decrypt(blob[:12],blob[12:],expected_aad)
    if digest(raw)!=meta['source_sha256']:raise ValueError('raw_identity')
    return raw

def previews(day,key,budget):
    out=[]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);budget.download(PREVIEW_RUN,f'kyoto-impl33-upcoming-workout-{PREVIEW_RUN}',p)
            doc=json.loads((p/'receipt.json').read_text())
            for item in doc['days'][day]['races']:
                if item['status']!='PRE_DAY_SOURCE_FROZEN':continue
                n=item['race'];aad=f'kyoto-workout-upcoming-v1|{REPO}|{PREVIEW_RUN}|{day}|{n}'.encode()
                meta={**item,'ciphertext_sha256':item['source_ciphertext_sha256']}
                raw=read_snapshot((p/f'{day}_r{n:02d}.aesgcm').read_bytes(),meta,key,aad)
                out.append(source_record(raw,item['captured_utc'],item['url'],'PRIMARY',n))
    except Exception:pass
    return out

def previous(day,key,budget):
    out=[]
    try:
        for r in eligible_runs(budget,day,WORKFLOW)[:4]:
            rid=r['id']
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    p=Path(tmp);budget.download(rid,f'kyoto-workout-{rid}-{day}',p)
                    d=json.loads((p/'receipt.json').read_text())
                    if d['day']!=day or d['run_id']!=rid:raise ValueError('previous_identity')
                    for i,m in enumerate(d['snapshots']):
                        if m['kind'] not in ('PRIMARY','SECONDARY') or type(m['race']) is not int or not 1<=m['race']<=12:continue
                        name=f'source_{i:03d}.aesgcm';aad=f'kyoto-workout-runtime-v1|{REPO}|{rid}|{day}|{i}'.encode()
                        raw=read_snapshot((p/name).read_bytes(),m,key,aad)
                        out.append(source_record(raw,m['captured_utc'],m['url'],m['kind'],m['race']))
            except Exception:continue
    except Exception:pass
    return out

class PublicFetch:
    def __init__(self,budget):
        self.budget=budget;self.robots={};self.last={};self.requests=0
    def __call__(self,url):
        u=urlsplit(url)
        if u.scheme!='https' or u.hostname not in {urlsplit(HOST).hostname,*SECONDARY} or u.username or u.password or u.fragment:raise ValueError('source_host')
        origin='https://'+u.netloc
        if origin not in self.robots:
            self.budget.remaining(15)
            try:self.requests+=1;robots=get(origin+'/robots.txt').decode('utf8')
            except HTTPError as e:
                if e.code!=404:raise
                robots='User-agent: *\nDisallow:'
            rp=RobotFileParser();rp.parse(robots.splitlines());self.robots[origin]=rp;self.last[origin]=time.monotonic()
        rp=self.robots[origin]
        if not rp.can_fetch(AGENT,url):raise ValueError('robots_disallow')
        delay=max(2,rp.crawl_delay(AGENT) or 0)
        if delay>15:raise ValueError('crawl_delay')
        wait=max(0,delay-(time.monotonic()-self.last[origin]))
        if self.budget.remaining(30)<wait+10:raise TimeoutError('source_budget')
        time.sleep(wait);self.requests+=1
        try:return get(url)
        finally:self.last[origin]=time.monotonic()

def identity(x):return x['kind'],x['race'],x['url'],digest(x['raw'])
def unique_snapshots(items):
    found={}
    for x in items:
        k=identity(x)
        if k not in found or utc(x['stamp'])<utc(found[k]['stamp']):found[k]=x
    return sorted(found.values(),key=lambda x:(x['race'],x['kind'],x['stamp'],x['url']))

def primary_final(x,day):
    try:
        rec,_,_,_=parse_observed(x['raw'],day,x['race'],x['url'],x['stamp'],((day,x['race'],x['url']),))
        return rec['summary_kind']=='FINAL_NUMBERED' and not rec['result_section_present']
    except Exception:return False

def race_labels(index,day):
    urls=discover(index,day);out={}
    soup=BeautifulSoup(index,'html.parser')
    for a in soup.find_all('a',href=True):
        u=urljoin(PRIMARY_INDEX,a['href'])
        for n,v in urls.items():
            if u!=v:continue
            m=re.search(r'京都\s*'+str(n)+r'R\s*(.+?)(?:\s*\d+頭|$)',text(a))
            if m:
                label=m[1].strip()
                if 2<=len(label)<=40 and '未勝利' not in label and '新馬' not in label and '勝クラス' not in label:out[n]=label
    return out

def collect_primary(day,items,rosters,fetch,clock=now,on_snapshot=lambda x:None):
    errors=[];labels={}
    try:index=fetch(PRIMARY_INDEX);urls=discover(index,day);labels=race_labels(index,day)
    except Exception as e:return items,labels,[type(e).__name__]
    for n,url in sorted(urls.items()):
        if n in rosters and clock()>=utc(rosters[n]['start']):continue
        cached=[x for x in items if x['race']==n and x['kind']=='PRIMARY' and primary_final(x,day)]
        # A complete previously fetched final source need not be fetched again.
        if cached:
            if n not in rosters:continue
            roster=rosters[n]
            for x in cached:
                try:
                    a,_,_,_=bridge(x['raw'],day,n,x['url'],x['stamp'],((day,n,x['url']),),roster['roster'],roster['start'])
                    if a['canonical_records_cover_roster']:break
                except Exception:continue
            else:cached=[]
            if cached:continue
        try:
            raw=fetch(url);stamp=clock().isoformat()
            x=source_record(raw,stamp,url,'PRIMARY',n);items.append(x);on_snapshot(x)
        except Exception as e:errors.append(f'R{n}:{type(e).__name__}')
    return items,labels,errors

def combine_primary(day,n,items,official):
    roster=official['roster'];start=official['start']
    values={k:[] for k in roster};proofs={k:[] for k in roster};issues=[]
    for x in sorted(items,key=lambda a:a['stamp'],reverse=True):
        if x['kind']!='PRIMARY' or x['race']!=n:continue
        try:a,canonical,records,issues2=bridge(x['raw'],day,n,x['url'],x['stamp'],((day,n,x['url']),),roster,start)
        except Exception as e:issues.append(type(e).__name__);continue
        for k,rows in records.items():
            if a['horses'][str(k)]['state']!='CANONICAL_RECORD_VALID':continue
            existing={tuple(sorted(r.items())) for r in values[k]}
            # Distinct timed sessions preserved; duplicate exact values removed.
            # Overlapping same day/course/distance with differing clock is
            # retained as a conflict instead of silently overriding a value.
            for r in rows:
                same=[v for v in values[k] if (v['training_date'],v['course'],v['distance_m'])==(r['training_date'],r['course'],r['distance_m'])]
                if same and r not in same:issues.append('overlap_clock_conflict');continue
                if tuple(sorted(r.items())) not in existing:
                    values[k].append(r);proofs[k].append({'source_sha256':digest(x['raw']),'captured_utc':x['stamp'],'url':x['url']});existing.add(tuple(sorted(r.items())))
        issues+=issues2
    return values,proofs,issues

def secondary_candidates(day,n,missing,roster,labels,fetch,cache):
    urls=set(SEEDS.get((day,n),[]))
    if n in labels:
        for host,index in SECONDARY.items():
            try:
                if host not in cache:cache[host]=fetch(index)
                urls.update(candidate_links(cache[host],index,allowed_hosts={host},horse_names=[roster[k] for k in missing],race_name=labels[n]))
            except Exception:continue
    return sorted(urls)[:4]

def secondary_record(x,name,day,start):
    if utc(x['stamp'])>=utc(start):return None
    host=urlsplit(x['url']).hostname
    parser={'umasiru.com':parse_table_v3,'talmudic.net':parse_labeled_turf}.get(host)
    if not parser:return None
    try:rec=parser(x['raw'],name,day_iso(day))
    except (ValueError,TypeError,KeyError,AttributeError):return None
    if rec and rec['training_date']<=utc(x['stamp']).astimezone(JST).date().isoformat():return rec
    return None

def partial_fields(day,n,items,official):
    result={}
    for x in items:
        if x['kind']!='PRIMARY' or x['race']!=n or utc(x['stamp'])>=utc(official['start']):continue
        try:
            receipt,_,_,_=parse_observed(x['raw'],day,n,x['url'],x['stamp'],((day,n,x['url']),))
            if receipt['result_section_present']:continue
            rows=preserve_partial(x['raw'],day_iso(day),official['roster'],x['stamp'])
            for row in rows:
                result[row['row_sha256']]={**row,'source_sha256':digest(x['raw']),'captured_utc':x['stamp']}
        except (ValueError,TypeError,KeyError,AttributeError):continue
    return list(result.values())

def checkpoint(out,report):
    tmp=out/'receipt.json.tmp'
    tmp.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2),encoding='utf8')
    tmp.replace(out/'receipt.json')

def append_snapshot(out,report,key,x):
    sha=digest(x['raw'])
    if any((m['kind'],m['race'],m['url'],m['source_sha256'])==(x['kind'],x['race'],x['url'],sha) for m in report['snapshots']):return
    i=len(report['snapshots']);day=report['day'];rid=report['run_id']
    aad=f'kyoto-workout-runtime-v1|{REPO}|{rid}|{day}|{i}'.encode()
    sh=seal(out,f'source_{i:03d}.aesgcm',x['raw'],key,aad)
    report['snapshots'].append({'race':x['race'],'kind':x['kind'],'url':x['url'],'captured_utc':x['stamp'],'source_sha256':sha,'ciphertext_sha256':sh,'archive_aad':aad.decode()})
    checkpoint(out,report)

def run(day,out,key,rid):
    if day not in DAYS or os.environ.get('GITHUB_REPOSITORY')!=REPO or not str(rid).isdigit():raise ValueError('runtime_identity')
    # Only the day before, or the designated race day, local Japan time.
    today=now().astimezone(JST).date();target=datetime.fromisoformat(day_iso(day)).date()
    if not target-timedelta(days=1)<=today<=target:raise ValueError('runtime_date')
    out=Path(out);out.mkdir(exist_ok=True)
    roster,conflicts,errors=gather_official(day,key,Budget(55)) if today==target else ({},[],[])
    items=unique_snapshots(previews(day,key,Budget(30))+previous(day,key,Budget(55)))
    fetch=PublicFetch(Budget(160))
    report={'day':day,'run_id':int(rid),'official_roster_conflicts':conflicts,'archive_errors':errors,'source_errors':[],'snapshots':[],'races':[],'jra_requests':0,'production_coverage_authorized':False,'status':'SOURCE_ONLY_IN_PROGRESS'}
    checkpoint(out,report)
    save=lambda x:append_snapshot(out,report,key,x)
    for x in items:save(x)
    items,labels,source_errors=collect_primary(day,items,roster,fetch,on_snapshot=save)
    report['source_errors']=source_errors;checkpoint(out,report)
    # Current observed supplemental pages can be frozen before the official roster.
    for (d,n),urls in SEEDS.items():
        if d!=day or (n in roster and now()>=utc(roster[n]['start'])):continue
        for url in urls:
            if any(x['kind']=='SECONDARY' and x['race']==n and x['url']==url for x in items):continue
            try:
                x=source_record(fetch(url),now().isoformat(),url,'SECONDARY',n);items.append(x);save(x)
            except Exception as e:report['source_errors'].append(f'S{n}:{type(e).__name__}')
    cache={}
    for n in range(1,13):
        if n not in roster:
            report['races'].append({'race':n,'status':'OFFICIAL_ROSTER_NOT_AVAILABLE','snapshot_count':sum(x['race']==n for x in items)});continue
        o=roster[n];values,proofs,issues=combine_primary(day,n,items,o)
        missing=[k for k in o['roster'] if not values[k]];obs={k:[] for k in missing}
        # Existing prestart secondary bytes remain usable even after start.
        for x in items:
            if x['kind']!='SECONDARY' or x['race']!=n:continue
            for k in missing:
                rec=secondary_record(x,o['roster'][k],day,o['start'])
                if rec:obs[k].append({'provider':urlsplit(x['url']).hostname,'record':rec})
        if missing and now()<utc(o['start']):
            for url in secondary_candidates(day,n,missing,o['roster'],labels,fetch,cache):
                old=[x for x in items if x['kind']=='SECONDARY' and x['race']==n and x['url']==url]
                if not old:
                    try:
                        x=source_record(fetch(url),now().isoformat(),url,'SECONDARY',n);items.append(x);save(x);old=[x]
                    except Exception:continue
                for x in old:
                    for k in missing:
                        rec=secondary_record(x,o['roster'][k],day,o['start'])
                        if rec:obs[k].append({'provider':urlsplit(url).hostname,'record':rec})
        merged,audit=recover(values,o['roster'],obs)
        # Include source-specific canonical evidence; secondary promotion
        # requires corroborated clocks and preserves separate source provenance.
        for k in missing:
            if merged[k]:
                for x in items:
                    if x['kind']=='SECONDARY' and x['race']==n and secondary_record(x,o['roster'][k],day,o['start'])==merged[k][0]:
                        proofs[k].append({'source_sha256':digest(x['raw']),'captured_utc':x['stamp'],'url':x['url']})
        a=f'kyoto-workout-normalized-v1|{REPO}|{rid}|{day}|{n}'.encode()
        partial=partial_fields(day,n,items,o)
        payload=json.dumps({'roster':o,'records':merged,'provenance':proofs,'recovery':audit,'partial_observations':partial},sort_keys=True,ensure_ascii=False,allow_nan=False).encode()
        sh=seal(out,f'r{n:02d}_normalized.aesgcm',payload,key,a)
        report['races'].append({'race':n,'status':'SOURCE_JOINED','official_horses':len(o['roster']),'covered_horses':sum(bool(v) for v in merged.values()),'records':sum(map(len,merged.values())),'issues':len(issues),'partial_observations':len(partial),'recovery':audit,'normalized_ciphertext_sha256':sh,'normalized_aad':a.decode()})
        checkpoint(out,report)
    report['source_requests']=fetch.requests
    report['status']='SOURCE_ONLY_FINISHED'
    checkpoint(out,report)
    print('WORKOUT_RUNTIME='+json.dumps({'day':day,'snapshots':len(report['snapshots']),'source_requests':fetch.requests,'races_joined':sum(r['status']=='SOURCE_JOINED' for r in report['races']),'covered_horses':sum(r.get('covered_horses',0) for r in report['races']),'official_horses':sum(r.get('official_horses',0) for r in report['races']),'production_coverage_authorized':False},sort_keys=True))
if __name__=='__main__':
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    run(os.environ['KYOTO_TARGET_DAY'],os.environ.get('WORKOUT_OUT','workout_sealed'),key,os.environ['GITHUB_RUN_ID'])
