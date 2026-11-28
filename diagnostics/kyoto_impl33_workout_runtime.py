"""Independent bounded workout capture and roster bridge. No official-source HTTP.
Use existing authenticated PC originals; retain third-party originals separately.
"""
import json, os, re, secrets, subprocess, tempfile, time, sys
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
AUXILIARY='kyoto-20261128-29-auxiliary-refresh.yml'
PRIMARY_INDEX=HOST+'/keiba/'
SECONDARY={'umasiru.com':'https://umasiru.com/','talmudic.net':'https://talmudic.net/'}
# Observed current published link; not a hardcoded horse or fabricated URL.
SEEDS={('20261128',11):['https://umasiru.com/archives/22515']}
PREVIEW_RUN=45755377155
SP_READER_SHA='fed005c89fcfa940c479538ee983f211598a6640'
# Keep the established SP validator in its own immutable checkout; do not
# import a second, divergent copy of the official roster parser.
SP_READER_SCRIPT=r'''
import hashlib,json,os,sys,tempfile
from pathlib import Path
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.kyoto_weekend_postflight import check_originals
from diagnostics.kyoto_impl31_sp_saved_roster_audit import assess_checked,inspect_heading,utc
from diagnostics.kyoto_impl39_sp_market_union import standalone_roster
from diagnostics.kyoto_impl30_day_coverage import digest
cipher,day,rid=sys.argv[1:4]
repo="papaneko-ai/kyoto-keiba-ai"
if day!="20261129" or not rid.isascii() or not rid.isdigit():raise ValueError("sp_bridge_identity")
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/"raw"
    decrypt_evidence(cipher,root,key_hex=os.environ["ARCHIVE_KEY"],repo=repo,run_id=rid)
    post=check_originals(root,day=day,channel="SP")
    observed=assess_checked(root,day,post)
    found={}
    for n in range(1,13):
        try:
            row=observed["races"][str(n)]
            if row["state"]!="SP_STRUCTURAL_ROSTER_OBSERVED":continue
            if post["sp_race_integrity"][str(n)]["state"]!="DIGEST_UTC_CHECKED_ONLY":continue
            path=root/f"r{n:02d}_official_sp_racecard.html"
            if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=1500000:continue
            raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
            stamp=utc(row["captured_at_utc"])
            if sha!=row["source_sha256"]:continue
            v=standalone_roster(raw,day,n,stamp,sha)
            named=inspect_heading(raw,day,n)
            if digest(named)!=v["named_roster_digest"] or [i for i,_,_ in named]!=v["numbers"]:continue
            found[str(n)]={"roster":{i:name for i,_,name in named},"start":v["start_utc"],
                "source_sha256":sha,"captured_utc":stamp.isoformat(),"run_id":int(rid),"source_lane":"sp",
                "named_roster_digest":v["named_roster_digest"]}
        except (ValueError,KeyError,TypeError,OSError,AttributeError,IndexError):continue
    print(json.dumps({"day":day,"run_id":int(rid),"races":found},ensure_ascii=True,sort_keys=True))
'''
def read_sp_rosters(cipher,day,rid,key,budget,reader):
    if day!='20261129' or type(rid) is not int or rid<=0:raise ValueError('sp_bridge_identity')
    root=Path(reader).resolve()
    rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True,stderr=subprocess.DEVNULL,timeout=budget.remaining(5)).strip()
    if rev!=SP_READER_SHA:raise ValueError('sp_reader_revision')
    env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(root),'PYTHONUTF8':'1','KYOTO_TARGET_DAY':day,'ARCHIVE_KEY':key.hex(),'KYOTO_WEEKEND_HTTP_APPROVED':'NO','KYOTO_AUX_HTTP_APPROVED':'NO'}
    raw=subprocess.check_output([sys.executable,'-c',SP_READER_SCRIPT,str(Path(cipher).resolve()),day,str(rid)],cwd=root,env=env,stderr=subprocess.DEVNULL,timeout=budget.remaining(20))
    if len(raw)>100000:raise ValueError('sp_bridge_output_size')
    d=json.loads(raw)
    if d.get('day')!=day or d.get('run_id')!=rid or not isinstance(d.get('races'),dict) or len(d['races'])>12:raise ValueError('sp_bridge_output_identity')
    found={}
    for n,row in d['races'].items():
        race=int(n);names={int(k):v for k,v in row['roster'].items()}
        if (n!=str(race) or not 1<=race<=12 or row['run_id']!=rid or row['source_lane']!='sp'
            or not 2<=len(names)<=18 or sorted(names)!=list(range(1,len(names)+1))
            or any(not isinstance(v,str) or not v.strip() for v in names.values())
            or not re.fullmatch(r'[a-f0-9]{64}',row['source_sha256'])
            or not re.fullmatch(r'[a-f0-9]{64}',row['named_roster_digest'])
            or utc(row['captured_utc']).strftime('%Y%m%d')!=day or utc(row['start']).strftime('%Y%m%d')!=day
            or not utc(row['captured_utc'])<utc(row['start'])):raise ValueError('sp_bridge_output_roster')
        found[race]={**row,'roster':names}
    return found
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
    dates=day_iso(day) if workflow in (OBSERVER,AUXILIARY) else (datetime.fromisoformat(day_iso(day)).date()-timedelta(days=1)).isoformat()+'..'+day_iso(day)
    index=budget.api(f'repos/{REPO}/actions/workflows/{workflow}/runs?created={dates}&per_page=100')
    rows=index['workflow_runs']
    if index['total_count']!=len(rows) or len(rows)>100:raise ValueError('run_index_incomplete')
    out=[]
    for r in rows:
        if r.get('status')!='completed' or r.get('head_branch')!='main' or r.get('head_repository',{}).get('full_name')!=REPO:continue
        if r.get('path','').split('@',1)[0]!='.github/workflows/'+workflow:continue
        if not isinstance(r.get('id'),int) or r['id']<=0:continue
        if workflow in (OBSERVER,AUXILIARY) and (r.get('event') not in ('schedule','workflow_dispatch') or r['created_at'][:10]!=day_iso(day)):continue
        if workflow==WORKFLOW and r.get('event') not in ('schedule','workflow_dispatch','workflow_run'):continue
        out.append(r)
    return sorted(out,key=lambda r:r['id'],reverse=True)

def gather_official(day,key,budget,*,aux_budget_factory=lambda:Budget(35),sp_reader=None):
    found={};conflicts=set();issues=[];rows=[];b=None
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
    # The independently encrypted afternoon G03 originals can restore missing
    # prestart rosters even if all morning PC runs failed. Keep PC provenance,
    # do not overwrite or silently resolve a known roster conflict.
    if len(found)<12:
        auxiliary={};aux_conflicts=set()
        try:
            b=aux_budget_factory()
            for r in eligible_runs(b,day,AUXILIARY)[:4]:
                rid=r['id']
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        cipher=Path(tmp)/'cipher';cipher.mkdir();root=Path(tmp)/'raw'
                        b.download(rid,f'kyoto-auxiliary-{rid}-{day}',cipher)
                        decrypt_evidence(cipher,root,key_hex=key.hex(),repo=REPO,run_id=str(rid))
                        receipt=json.loads((root/'receipt.json').read_text())
                        if receipt.get('day')!=day or receipt.get('schema')!='kyoto_impl30_auxiliary_refresh.v1':raise ValueError('auxiliary_identity')
                        candidates={n:{**v,'source_lane':'auxiliary'} for n,v in official(root,day,rid).items() if n not in found and n not in conflicts}
                        roster_union(auxiliary,candidates,aux_conflicts)
                except Exception as e:issues.append('AUX:'+type(e).__name__)
        except Exception as e:issues.append('AUX:'+type(e).__name__)
        found.update(auxiliary);conflicts.update(aux_conflicts)
    # Use the existing auxiliary deadline, never an extra source HTTP request
    # or a new time allowance. Only fill missing races; known conflicts remain.
    if day=='20261129' and sp_reader and b is not None and len(found)<12:
        mobile={};mobile_conflicts=set()
        for r in rows[:8]:
            # Continue within the same deadline: a later authenticated roster
            # may conflict even if the apparent race coverage is already 12/12.
            rid=r['id']
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    cipher=Path(tmp)/'cipher';cipher.mkdir()
                    b.download(rid,f'kyoto-sp-{rid}-{day}',cipher)
                    candidates=read_sp_rosters(cipher,day,rid,key,b,sp_reader)
                    roster_union(mobile,{n:v for n,v in candidates.items() if n not in found and n not in conflicts},mobile_conflicts)
            except Exception as e:
                issues.append('SP:'+type(e).__name__)
                if isinstance(e,TimeoutError):break
        found.update(mobile);conflicts.update(mobile_conflicts)
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

# Exact existing isolated pre-day capture: reuse only its authenticated bytes.
PREDAY_RUN=45947723339
PREDAY_HEAD='57ac2dc665dacb94d73d542eaf60218a000209a3'
PREDAY_WORKFLOW='.github/workflows/kyoto-impl36-pre-day-workout-source.yml'
def preday_saved(day,key,budget):
    if day!='20261128':return []
    out=[]
    try:
        r=budget.api(f'repos/{REPO}/actions/runs/{PREDAY_RUN}')
        if (r.get('id')!=PREDAY_RUN or r.get('head_sha')!=PREDAY_HEAD or
            r.get('path','').split('@',1)[0]!=PREDAY_WORKFLOW or
            r.get('head_repository',{}).get('full_name')!=REPO or
            r.get('event')!='push' or r.get('status')!='completed' or r.get('conclusion')!='success'):
            raise ValueError('preday_run_identity')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            budget.download(PREDAY_RUN,f'impl36-preday-workout-{PREDAY_RUN}-{day}',p)
            d=json.loads((p/'receipt.json').read_text())
            if (d.get('day')!=day or d.get('run_id')!=PREDAY_RUN or
                d.get('jra_requests')!=0 or d.get('production_coverage_authorized') is not False or
                d.get('status')!='SOURCE_ONLY_FINISHED' or len(d['snapshots'])>50):
                raise ValueError('preday_receipt_identity')
            for i,m in enumerate(d['snapshots']):
                try:
                    n=m['race'];kind=m['kind'];u=urlsplit(m['url'])
                    if type(n) is not int or not 1<=n<=12 or kind not in ('PRIMARY','SECONDARY'):continue
                    if u.scheme!='https' or u.username or u.password or u.fragment:continue
                    if (kind=='PRIMARY' and u.hostname!=urlsplit(HOST).hostname) or (kind=='SECONDARY' and u.hostname not in SECONDARY):continue
                    if utc(m['captured_utc']).astimezone(JST).strftime('%Y%m%d') not in ('20261126','20261127'):continue
                    f=p/f'source_{i:03d}.aesgcm'
                    if f.is_symlink() or not f.is_file() or not 0<f.stat().st_size<=4_000_000:continue
                    aad=f'kyoto-workout-runtime-v1|{REPO}|{PREDAY_RUN}|{day}|{i}'.encode()
                    raw=read_snapshot(f.read_bytes(),m,key,aad)
                    out.append(source_record(raw,m['captured_utc'],m['url'],kind,n))
                except Exception:continue
    except Exception:return []
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

def collect_primary(day,items,rosters,fetch,clock=now,on_snapshot=lambda x:None,*,on_index=lambda raw,stamp:None,on_discovery=lambda races:None):
    errors=[];labels={}
    try:index=fetch(PRIMARY_INDEX)
    except Exception as e:return items,labels,[type(e).__name__]
    # Reuse the exact already fetched bytes. Preserve before parsing so even
    # an unfamiliar layout or a parser exception has a reproducible original.
    try:on_index(index,clock().isoformat())
    except Exception as e:errors.append('INDEX_ARCHIVE:'+type(e).__name__)
    try:urls=discover(index,day)
    except Exception as e:return items,labels,errors+['INDEX_DISCOVERY:'+type(e).__name__]
    try:on_discovery(sorted(urls))
    except Exception as e:errors.append('INDEX_RECEIPT:'+type(e).__name__)
    try:labels=race_labels(index,day)
    except Exception as e:errors.append('INDEX_LABELS:'+type(e).__name__)
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

def combine_primary(day,n,items,official,*,clock_observations=None):
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
                if clock_observations is not None:
                    g=(k,r['training_date'],r['course'],r['distance_m'])
                    variants=clock_observations.setdefault(g,{})
                    v=tuple(sorted(r.items()))
                    p={'source_sha256':digest(x['raw']),'captured_utc':x['stamp'],'url':x['url']}
                    ps=variants.setdefault(v,[])
                    if p not in ps:ps.append(p)
                same=[v for v in values[k] if (v['training_date'],v['course'],v['distance_m'])==(r['training_date'],r['course'],r['distance_m'])]
                if same and r not in same:issues.append('overlap_clock_conflict');continue
                if tuple(sorted(r.items())) not in existing:
                    values[k].append(r);proofs[k].append({'source_sha256':digest(x['raw']),'captured_utc':x['stamp'],'url':x['url']});existing.add(tuple(sorted(r.items())))
        issues+=issues2
    return values,proofs,issues

def clock_variant_receipt(observations):
    """Retain ambiguous same-key clock observations, separate from canonical records.
    Identical sets across captures do not imply distinct physical sessions.
    Neither ambiguous variants nor repeated observations increase canonical counts.
    """
    out=[]
    for (n,day,course,distance),variants in sorted(observations.items()):
        if len(variants)<2:continue
        snapshots={}
        rows=[]
        for val,proofs in sorted(variants.items()):
            ordered=sorted(proofs,key=lambda p:(p['captured_utc'],p['source_sha256'],p['url']))
            rows.append({'record':dict(val),'source_proofs':ordered})
            for p in ordered:
                sid=(p['source_sha256'],p['captured_utc'],p['url'])
                snapshots.setdefault(sid,set()).add(val)
        different=len({frozenset(v) for v in snapshots.values()})>1
        out.append({'horse_number':n,'training_date':day,'course':course,'distance_m':distance,
                    'state':'MULTIPLE_CLOCK_VALUES_REVIEW_REQUIRED',
                    'capture_sets_differ':different,'variants':rows})
    return out

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

def refresh_missing_secondary(day,n,missing,official,urls,items,fetch,save,attempted,*,clock=now):
    """Reuse complete cached records; refresh a known incomplete source once
    per invocation while the race is still upcoming. Never refetch just
    because a cached page exists or overwrite a retained observation.
    """
    observations={k:[] for k in missing}
    for url in sorted(set(urls)):
        def add(x):
            for k in missing:
                rec=secondary_record(x,official['roster'][k],day,official['start'])
                if rec:
                    item={'provider':urlsplit(url).hostname,'record':rec}
                    if item not in observations[k]:observations[k].append(item)
        old=[x for x in items if x['kind']=='SECONDARY' and x['race']==n and x['url']==url]
        for x in old:add(x)
        # One independent provider may not suffice for promotion; retain it,
        # and refresh only if it has no record for at least one missing horse.
        provider=urlsplit(url).hostname
        if not any(not any(v['provider']==provider for v in observations[k]) for k in missing):continue
        if (n,url) in attempted or clock()>=utc(official['start']):continue
        attempted.add((n,url))
        try:
            raw=fetch(url)
            stamp=clock().isoformat()
            x=source_record(raw,stamp,url,'SECONDARY',n)
            items.append(x);save(x);add(x)
        except Exception:continue
    return observations

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

def append_primary_index(out,report,key,raw,stamp):
    if type(raw) is not bytes or not 0<len(raw)<=4_000_000:raise ValueError('primary_index_size')
    captured=utc(stamp)
    if captured>now()+timedelta(seconds=30):raise ValueError('primary_index_future')
    aad=f"kyoto-workout-navigation-v1|{REPO}|{report['run_id']}|{report['day']}|PRIMARY_INDEX".encode()
    sha=digest(raw);filename='primary_index.aesgcm'
    meta={'state':'INDEX_SEALED','filename':filename,'captured_utc':captured.isoformat(),
          'source_sha256':sha,'archive_aad':aad.decode(),'bytes':len(raw),
          'ciphertext_sha256':seal(out,filename,raw,key,aad),'discovery_state':'NOT_EVALUATED'}
    report['primary_index']=meta
    checkpoint(out,report)

def record_primary_discovery(out,report,races):
    if any(type(n) is not int or not 1<=n<=12 for n in races) or list(races)!=sorted(set(races)):
        raise ValueError('primary_index_race_inventory')
    meta=report.setdefault('primary_index',{'state':'INDEX_NOT_SAVED'})
    meta.update(discovery_state='PARSER_RETURNED_RACES',discovered_races=list(races),
                not_discovered_races=sorted(set(range(1,13))-set(races)))
    checkpoint(out,report)

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
    report={'day':day,'run_id':int(rid),'official_roster_conflicts':[],'archive_errors':[],'source_errors':[],'snapshots':[],'races':[],'primary_index':{'state':'INDEX_NOT_SAVED','discovery_state':'NOT_EVALUATED'},'jra_requests':0,'production_coverage_authorized':False,'status':'SOURCE_ONLY_IN_PROGRESS','roster_recovery_state':'NOT_EVALUATED'}
    checkpoint(out,report)
    roster,conflicts,errors=gather_official(day,key,Budget(55),sp_reader=os.environ.get('KYOTO_WORKOUT_SP_READER')) if today==target else ({},[],[])
    report.update(official_roster_conflicts=conflicts,archive_errors=errors,roster_recovery_state='SAME_DAY_REPLAY_FINISHED' if today==target else 'PREDAY_WAIT',
        roster_source_races={lane:sorted(n for n,v in roster.items() if v.get('source_lane','pc')==lane) for lane in ('pc','auxiliary','sp')})
    checkpoint(out,report)
    saved_budget=Budget(55)
    items=unique_snapshots(previews(day,key,Budget(30))+previous(day,key,saved_budget)+preday_saved(day,key,saved_budget))
    fetch=PublicFetch(Budget(160))
    save=lambda x:append_snapshot(out,report,key,x)
    for x in items:save(x)
    items,labels,source_errors=collect_primary(day,items,roster,fetch,on_snapshot=save,
        on_index=lambda raw,stamp:append_primary_index(out,report,key,raw,stamp),
        on_discovery=lambda races:record_primary_discovery(out,report,races))
    report['source_errors']=source_errors;checkpoint(out,report)
    attempted=set()
    # Current observed supplemental pages can be frozen before the official roster.
    for (d,n),urls in SEEDS.items():
        if d!=day or (n in roster and now()>=utc(roster[n]['start'])):continue
        for url in urls:
            if any(x['kind']=='SECONDARY' and x['race']==n and x['url']==url for x in items):continue
            attempted.add((n,url))
            try:
                x=source_record(fetch(url),now().isoformat(),url,'SECONDARY',n);items.append(x);save(x)
            except Exception as e:report['source_errors'].append(f'S{n}:{type(e).__name__}')
    cache={}
    for n in range(1,13):
        if n not in roster:
            report['races'].append({'race':n,'status':'OFFICIAL_ROSTER_NOT_AVAILABLE','snapshot_count':sum(x['race']==n for x in items)});continue
        o=roster[n];clock_observations={};values,proofs,issues=combine_primary(day,n,items,o,clock_observations=clock_observations)
        missing=[k for k in o['roster'] if not values[k]];obs={k:[] for k in missing}
        # Existing prestart secondary bytes remain usable even after start.
        for x in items:
            if x['kind']!='SECONDARY' or x['race']!=n:continue
            for k in missing:
                rec=secondary_record(x,o['roster'][k],day,o['start'])
                if rec:obs[k].append({'provider':urlsplit(x['url']).hostname,'record':rec})
        if missing and now()<utc(o['start']):
            # Include observed previously saved secondary URLs even when the
            # current index omits them; keep exact URL, date/race and source.
            urls=set(secondary_candidates(day,n,missing,o['roster'],labels,fetch,cache))
            urls.update(x['url'] for x in items if x['kind']=='SECONDARY' and x['race']==n)
            refreshed=refresh_missing_secondary(day,n,missing,o,sorted(urls)[:8],items,fetch,save,attempted)
            for k,rows in refreshed.items():
                for row in rows:
                    if row not in obs[k]:obs[k].append(row)
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
        variants=clock_variant_receipt(clock_observations)
        payload=json.dumps({'roster':o,'records':merged,'provenance':proofs,'recovery':audit,'partial_observations':partial,'clock_variant_observations':variants},sort_keys=True,ensure_ascii=False,allow_nan=False).encode()
        sh=seal(out,f'r{n:02d}_normalized.aesgcm',payload,key,a)
        report['races'].append({'race':n,'status':'SOURCE_JOINED','official_horses':len(o['roster']),'covered_horses':sum(bool(v) for v in merged.values()),'records':sum(map(len,merged.values())),'issues':len(issues),'partial_observations':len(partial),'clock_variant_groups':len(variants),'clock_variant_values':sum(len(v['variants']) for v in variants),'recovery':audit,'normalized_ciphertext_sha256':sh,'normalized_aad':a.decode()})
        checkpoint(out,report)
    report['source_requests']=fetch.requests
    report['status']='SOURCE_ONLY_FINISHED'
    checkpoint(out,report)
    print('WORKOUT_RUNTIME='+json.dumps({'day':day,'snapshots':len(report['snapshots']),'source_requests':fetch.requests,'races_joined':sum(r['status']=='SOURCE_JOINED' for r in report['races']),'covered_horses':sum(r.get('covered_horses',0) for r in report['races']),'official_horses':sum(r.get('official_horses',0) for r in report['races']),'production_coverage_authorized':False},sort_keys=True))
if __name__=='__main__':
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    run(os.environ['KYOTO_TARGET_DAY'],os.environ.get('WORKOUT_OUT','workout_sealed'),key,os.environ['GITHUB_RUN_ID'])
