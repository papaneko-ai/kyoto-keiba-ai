"""Fill only missing historical race pages; keep eight successful results immutable."""
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_impl33_whitegreen_probe import HOST, AGENT, get
from diagnostics.kyoto_impl33_workout_binding import bind
from diagnostics.kyoto_impl33_workout_all12 import DAY, official_rosters, seal, digest

PREVIOUS_RUN=45755248661
# All four exact URLs separately observed in source search, not extrapolated from R1.
RECOVERY={3:HOST+'/race/20261122-kyoto-03/',8:HOST+'/race/20261122-kyoto-08/',9:HOST+'/race/20261122-kyoto-09/',10:HOST+'/race/20261122-kyoto-10/'}
def merge(previous, new):
    prior={r['race']:r for r in previous}
    if len(previous)!=12 or set(prior)!=set(range(1,13)):raise ValueError('previous_race_inventory')
    missing={n for n,r in prior.items() if r['status']!='HISTORICAL_BINDING_VERIFIED'}
    if len(new)!=len({r['race'] for r in new}) or any(r['race'] not in missing or r['official_horses']!=prior[r['race']]['official_horses'] for r in new):raise ValueError('unexpected_recovery_scope')
    return [({r['race']:r for r in new}.get(n,prior[n])) for n in range(1,13)]

def main():
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    rosters=official_rosters(key)
    previous_dir=Path('previous_all12')
    previous=json.loads((previous_dir/'receipt.json').read_text())
    if previous['day']!=DAY or previous['official_archive_run_id']!=44966013490 or previous['races_bound']!=8:raise ValueError('previous_receipt_scope')
    successful=[r for r in previous['races'] if r['status']=='HISTORICAL_BINDING_VERIFIED']
    if len(successful)!=8:raise ValueError('previous_success_count')
    for r in successful:
        n=r['race'];blob=(previous_dir/f'r{n:02d}.aesgcm').read_bytes()
        aad=f'kyoto-workout-all12-v1|{os.environ["GITHUB_REPOSITORY"]}|{PREVIOUS_RUN}|{DAY}|{n}'.encode()
        if digest(blob)!=r['source_ciphertext_sha256'] or r['archive_aad'].encode()!=aad:raise ValueError('previous_cipher_hash')
        raw=AESGCM(key).decrypt(blob[:12],blob[12:],aad)
        if digest(raw)!=r['source_sha256'] or r['official_original_sha256']!=rosters[n][2]:raise ValueError('previous_source_hash')
    expected={r['race'] for r in previous['races'] if r['status']!='HISTORICAL_BINDING_VERIFIED'}
    if expected!=set(RECOVERY):raise ValueError('recovery_scope_changed')
    rp=RobotFileParser()
    try:robots=get(HOST+'/robots.txt').decode('utf8')
    except HTTPError as e:
        if e.code!=404:raise
        robots='User-agent: *\nDisallow:'
    rp.parse(robots.splitlines());delay=max(2,rp.crawl_delay(AGENT) or 0)
    if delay>15:raise ValueError('crawl_delay_budget')
    out=Path('missing_workout');out.mkdir(exist_ok=True);new=[]
    approved=tuple((DAY,n,u) for n,u in RECOVERY.items())
    report={'day':DAY,'jra_requests':0,'official_archive_run_id':44966013490,'previous_run_id':PREVIOUS_RUN,'reused_races':8,'production_coverage_authorized':False}
    for n,u in RECOVERY.items():
        roster,start,official_hash=rosters[n]
        item={'race':n,'official_horses':len(roster),'official_original_sha256':official_hash}
        try:
            if not rp.can_fetch(AGENT,u):raise ValueError('robots_disallow')
            time.sleep(delay);raw=get(u);stamp=datetime.now(timezone.utc).isoformat()
            aad=f'kyoto-workout-missing-v1|{os.environ["GITHUB_REPOSITORY"]}|{os.environ["GITHUB_RUN_ID"]}|{DAY}|{n}'.encode()
            item.update(source_sha256=digest(raw),source_captured_utc=stamp,source_ciphertext_sha256=seal(out,f'r{n:02d}.aesgcm',raw,key,aad),archive_aad=aad.decode())
            receipt,_=bind(raw,DAY,n,u,stamp,roster,start,approved);item.update(receipt,status='HISTORICAL_BINDING_VERIFIED')
        except Exception as e:
            item.update(status='UNVERIFIED',error_type=type(e).__name__)
            if isinstance(e,ValueError):item['error_code']=str(e)[:100]
            if isinstance(e,HTTPError):item['http_status']=e.code
        new.append(item)
        report['races']=merge(previous['races'],new)
        (out/'receipt.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf8')
    report['races_bound']=sum(x['status']=='HISTORICAL_BINDING_VERIFIED' for x in report['races'])
    report['official_horses']=sum(x['official_horses'] for x in report['races'])
    report['horses_with_dated_workout']=sum(x.get('horses_with_dated_workout',0) for x in report['races'])
    report['dated_records']=sum(x.get('bound_dated_records',0) for x in report['races'])
    report['status']='HISTORICAL_RECOVERY_FINISHED'
    (out/'receipt.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf8')
    print('MISSING_WORKOUT='+json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
