"""Recover historical gaps only, authenticating retained sources first."""
import json, os, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_impl33_whitegreen_probe import get, AGENT
from diagnostics.kyoto_impl33_workout_all12 import official_rosters, seal, digest, DAY
from diagnostics.kyoto_impl33_workout_binding import bind
from diagnostics.kyoto_impl33_hybrid_workout import parse_table, parse_turf_line, recover, classify_rejected

# Observed published race-specific pages. Discovery of other races is separate.
SOURCES={('20261122',11):[
 ('umasiru','https://umasiru.com/archives/22392',parse_table),
 ('jravan','https://jravan.jp/fun/tokusyu/g1/mcs/training.html',parse_turf_line)]}
def retained(n,item,key):
    folder='missing_workout' if n in (3,8,9,10) else 'previous_all12'
    run=45755450768 if folder=='missing_workout' else 45755248661
    kind='missing' if folder=='missing_workout' else 'all12'
    aad=f'kyoto-workout-{kind}-v1|{os.environ["GITHUB_REPOSITORY"]}|{run}|{DAY}|{n}'.encode()
    blob=(Path(folder)/f'r{n:02d}.aesgcm').read_bytes()
    if item['archive_aad'].encode()!=aad or digest(blob)!=item['source_ciphertext_sha256']:raise ValueError('retained_cipher_identity')
    raw=AESGCM(key).decrypt(blob[:12],blob[12:],aad)
    if digest(raw)!=item['source_sha256']:raise ValueError('retained_raw_identity')
    return raw

def approved_get(url):
    u=urlsplit(url);origin=u.scheme+'://'+u.netloc
    try:robots=get(origin+'/robots.txt').decode('utf8')
    except HTTPError as e:
        if e.code!=404:raise
        robots='User-agent: *\nDisallow:'
    rp=RobotFileParser();rp.parse(robots.splitlines())
    if not rp.can_fetch(AGENT,url):raise ValueError('robots_disallow')
    delay=max(2,rp.crawl_delay(AGENT) or 0)
    if delay>15:raise ValueError('crawl_delay_budget')
    time.sleep(delay);return get(url)
def main():
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    rosters=official_rosters(key);prior=json.loads((Path('missing_workout')/'receipt.json').read_text())
    if prior['races_bound']!=12 or prior['official_horses']!=159 or prior['horses_with_dated_workout']!=158:raise ValueError('previous_scope')
    out=Path('hybrid_workout');out.mkdir(exist_ok=True)
    result={'status':'HISTORICAL_RESEARCH','prior_run':45755450768,'prior_covered':158,'official_horses':159,'prior_records':1698,'jra_requests':0,'production_coverage_authorized':False,'races':[]}
    for item in prior['races']:
        n=item['race']
        if item['horses_with_dated_workout']==item['official_horses'] and not item['unbound_or_invalid_rows']:continue
        roster,start,official_hash=rosters[n];raw=retained(n,item,key)
        if official_hash!=item['official_original_sha256']:raise ValueError('official_identity')
        stamp=item['captured_utc'];url=item['url']
        receipt,primary=bind(raw,DAY,n,url,stamp,roster,start,((DAY,n,url),))
        if receipt['normalized_digest']!=item['normalized_digest']:raise ValueError('retained_normalization')
        missing=[k for k in roster if not primary[k]]
        issues=classify_rejected(raw,'2026-11-22',roster,stamp)
        if len(issues)!=item['unbound_or_invalid_rows']:raise ValueError('rejection_count_mismatch')
        report={'race':n,'missing_count':len(missing),'rejected_rows':issues,'sources':[]}
        observations={k:[] for k in missing}
        if missing:
            for provider,source_url,parser in SOURCES.get((DAY,n),[]):
                s={'provider':provider,'url':source_url}
                try:
                    data=approved_get(source_url);captured=datetime.now(timezone.utc).isoformat()
                    aad=f'kyoto-workout-hybrid-v1|{os.environ["GITHUB_REPOSITORY"]}|{os.environ["GITHUB_RUN_ID"]}|{DAY}|{n}|{provider}'.encode()
                    s.update(source_sha256=digest(data),captured_utc=captured,ciphertext_sha256=seal(out,f'r{n:02d}_{provider}.aesgcm',data,key,aad),archive_aad=aad.decode())
                    matches=0
                    for k in missing:
                        rec=parser(data,roster[k],'2026-11-22')
                        if rec:observations[k].append({'provider':provider,'record':rec});matches+=1
                    s.update(status='PARSED',matches=matches)
                except Exception as e:
                    s.update(status='UNVERIFIED',error_type=type(e).__name__)
                    if isinstance(e,ValueError):s['reason']=str(e)[:100]
                    if isinstance(e,HTTPError):s['http_status']=e.code
                report['sources'].append(s)
        merged,audit=recover(primary,roster,observations)
        report['recovery']=audit
        report['added_horses']=sum(bool(merged[k]) for k in missing)
        report['added_records']=sum(len(merged[k]) for k in missing)
        # Preserve only encrypted normalized data; public receipt is counts and evidence.
        encoded=json.dumps(merged,sort_keys=True,allow_nan=False).encode()
        aad=f'kyoto-workout-hybrid-normalized-v1|{os.environ["GITHUB_RUN_ID"]}|{n}'.encode()
        report['normalized_ciphertext_sha256']=seal(out,f'r{n:02d}_normalized.aesgcm',encoded,key,aad)
        report['normalized_aad']=aad.decode()
        result['races'].append(report)
        (out/'receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2),encoding='utf8')
    result['covered']=158+sum(r['added_horses'] for r in result['races'])
    result['records']=1698+sum(r['added_records'] for r in result['races'])
    result['status']='HISTORICAL_HYBRID_FINISHED'
    (out/'receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2),encoding='utf8')
    print('HYBRID_WORKOUT='+json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
