"""Historical day-wide workout research; no live JRA HTTP or production promotion."""
import hashlib, io, json, os, re, secrets, tarfile, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from bs4 import BeautifulSoup
from diagnostics.kyoto_impl33_whitegreen_probe import HOST, AGENT, JST, get
from diagnostics.kyoto_impl33_workout_binding import bind
from diagnostics.kyoto_g03_all_races import parse

DAY='20261122'
INDEX=HOST+'/keiba/'
# Exact URLs independently observed in published search results, not guessed.
OBSERVED={n:HOST+'/race/20261122-kyoto-'+s+'/' for n,s in
          ((1,'01'),(2,'02'),(4,'04'),(5,'05'),(6,'06'),(7,'07'),(11,'11'),(12,'12'))}
ARCHIVE_DIGEST='8896f2738926dde2b4a7ae7753da5ec0e809c4c188ed36fba34e9ab528374ca9'
PREVIOUS_SOURCE_DIGEST='222a72506c60f4d8c539b3715d71eccf7a4501430f052c482875959c6540985c'
PREVIOUS_AAD=b'kyoto-workout-research-v1|papaneko-ai/kyoto-keiba-ai|45754622928|20261122'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def discover(raw,day):
    soup=BeautifulSoup(raw,'html.parser')
    found={}
    for a in soup.find_all('a',href=True):
        u=urljoin(INDEX,a['href'])
        m=re.fullmatch(re.escape(HOST)+rf'/race/{day}-kyoto-(0[1-9]|1[0-2])/',u)
        if m:found[int(m[1])]=u
    return found

def seal(out,name,raw,key,aad):
    nonce=secrets.token_bytes(12);cipher=AESGCM(key).encrypt(nonce,raw,aad)
    assert AESGCM(key).decrypt(nonce,cipher,aad)==raw
    (out/name).write_bytes(nonce+cipher)
    return digest(nonce+cipher)

def official_rosters(key):
    blob=(Path('pc_archive')/'originals_all12.tar.gz.aesgcm').read_bytes()
    if digest(blob)!=ARCHIVE_DIGEST:raise ValueError('archive_hash')
    original=AESGCM(key).decrypt(blob[:12],blob[12:],b'kyoto-nov22-observed-official-all12-source-only')
    rosters={}
    with tarfile.open(fileobj=io.BytesIO(original),mode='r:gz') as arc:
        meta=json.loads(arc.extractfile('receipt.json').read(1500001))['races']
        for n in range(1,13):
            m=meta[str(n)]['PC']
            raw=arc.extractfile(f'r{n:02d}_pc_official_racecard.html').read(1500001)
            if not 0<len(raw)<=1500000 or digest(raw)!=m['sha256']:raise ValueError('official_raw_hash')
            official=parse(raw,DAY,n,m['observed_official_url'],m['captured_at_utc'])
            roster={h['number']:h['name'] for h in official['runners']}
            if len(roster)!=len(official['runners']):raise ValueError('official_duplicate_number')
            start=datetime.fromisoformat('2026-11-22T'+official['start_time_jst']).replace(tzinfo=JST).astimezone(timezone.utc).isoformat()
            rosters[n]=(roster,start,digest(raw))
    return rosters

def reuse_r1(key):
    p=Path('previous_binding')
    receipt=json.loads((p/'receipt.json').read_text())
    blob=(p/'source.aesgcm').read_bytes()
    if receipt['archive_aad'].encode()!=PREVIOUS_AAD or digest(blob)!=receipt['source_ciphertext_sha256']:raise ValueError('previous_cipher_identity')
    raw=AESGCM(key).decrypt(blob[:12],blob[12:],PREVIOUS_AAD)
    if digest(raw)!=PREVIOUS_SOURCE_DIGEST or digest(raw)!=receipt['source_sha256']:raise ValueError('previous_source_identity')
    return raw,receipt['source_captured_utc']

def run():
    out=Path('all12_workout');out.mkdir(exist_ok=True)
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    rosters=official_rosters(key)
    urls=dict(OBSERVED);index_status='NOT_FETCHED';rp=None;delay=2
    try:
        try:robots=get(HOST+'/robots.txt').decode('utf8')
        except HTTPError as e:
            if e.code!=404:raise
            robots='User-agent: *\nDisallow:'
        rp=RobotFileParser();rp.parse(robots.splitlines())
        delay=max(2,rp.crawl_delay(AGENT) or 0)
        if delay>15:rp=None;raise ValueError('crawl_delay_budget')
        if rp.can_fetch(AGENT,INDEX):
            time.sleep(delay);index=get(INDEX)
            urls.update(discover(index,DAY));index_status='PARSED'
        else:index_status='ROBOTS_DISALLOW'
    except Exception as e:index_status=type(e).__name__
    approved=tuple((DAY,n,u) for n,u in urls.items())
    report={'day':DAY,'jra_requests':0,'official_archive_run_id':44966013490,
            'index_status':index_status,'observed_url_count':len(urls),'races':[],
            'production_coverage_authorized':False}
    for n in range(1,13):
        roster,start,official_hash=rosters[n]
        item={'race':n,'official_horses':len(roster),'official_original_sha256':official_hash}
        try:
            if n==1:
                raw,stamp=reuse_r1(key);item['reuse_original']=True
            else:
                if n not in urls:raise ValueError('unobserved_url')
                if rp is None or not rp.can_fetch(AGENT,urls[n]):raise ValueError('robots_unverified_or_disallow')
                time.sleep(delay);raw=get(urls[n]);stamp=datetime.now(timezone.utc).isoformat()
            aad=f'kyoto-workout-all12-v1|{os.environ["GITHUB_REPOSITORY"]}|{os.environ["GITHUB_RUN_ID"]}|{DAY}|{n}'.encode()
            item.update(source_sha256=digest(raw),source_captured_utc=stamp,
                        source_ciphertext_sha256=seal(out,f'r{n:02d}.aesgcm',raw,key,aad),archive_aad=aad.decode())
            receipt,records=bind(raw,DAY,n,urls[n],stamp,roster,start,approved)
            item.update(receipt,status='HISTORICAL_BINDING_VERIFIED')
        except Exception as e:
            item.update(status='UNVERIFIED',error_type=type(e).__name__)
            if isinstance(e,ValueError):item['error_code']=str(e)[:100]
            if isinstance(e,HTTPError):item['http_status']=e.code
        report['races'].append(item)
        # Save incrementally, including failure receipts.
        (out/'receipt.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf8')
    report['races_bound']=sum(x['status']=='HISTORICAL_BINDING_VERIFIED' for x in report['races'])
    report['official_horses']=sum(x['official_horses'] for x in report['races'])
    report['horses_with_dated_workout']=sum(x.get('horses_with_dated_workout',0) for x in report['races'])
    report['dated_records']=sum(x.get('bound_dated_records',0) for x in report['races'])
    report['status']='HISTORICAL_RESEARCH_FINISHED'
    (out/'receipt.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf8')
    print('ALL12_WORKOUT='+json.dumps(report,sort_keys=True))
if __name__=='__main__':run()
