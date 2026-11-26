"""Single historical-source binding; reuse the exact existing official archive."""
import hashlib, io, json, os, secrets, tarfile, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_impl33_whitegreen_probe import HOST, AGENT, SAMPLES, JST, get
from diagnostics.kyoto_impl33_workout_binding import bind
from diagnostics.kyoto_g03_all_races import parse


def digest(raw):return hashlib.sha256(raw).hexdigest()


def main():
    day,race,url=SAMPLES[0]
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    blob=(Path('pc_archive')/'originals_all12.tar.gz.aesgcm').read_bytes()
    assert digest(blob)=='8896f2738926dde2b4a7ae7753da5ec0e809c4c188ed36fba34e9ab528374ca9'
    original=AESGCM(key).decrypt(blob[:12],blob[12:],b'kyoto-nov22-observed-official-all12-source-only')
    with tarfile.open(fileobj=io.BytesIO(original),mode='r:gz') as archive:
        raw=archive.extractfile('r01_pc_official_racecard.html').read(1500001)
        metadata=json.loads(archive.extractfile('receipt.json').read(1500001))['races']['1']['PC']
    assert digest(raw)==metadata['sha256']=='a6c4eb195f50d66c413c49ab00e9322439b7474b2e2aa1c857ca59ab1d8b9448'
    official=parse(raw,day,race,metadata['observed_official_url'],metadata['captured_at_utc'])
    roster={h['number']:h['name'] for h in official['runners']}
    assert len(roster)==12
    start=datetime.fromisoformat('2026-11-22T'+official['start_time_jst']).replace(tzinfo=JST).astimezone(timezone.utc).isoformat()
    out=Path('workout_binding');out.mkdir(exist_ok=True)
    report={'official_original_sha256':digest(raw),'official_archive_run_id':44966013490,'official_roster_count':len(roster),'jra_requests':0,'production_coverage_authorized':False}
    try:
        try: robots=get(HOST+'/robots.txt').decode('utf8')
        except HTTPError as e:
            if e.code!=404:raise
            robots='User-agent: *\nDisallow:'
        rp=RobotFileParser();rp.parse(robots.splitlines())
        if not rp.can_fetch(AGENT,url):raise ValueError('robots_disallow')
        delay=max(2,rp.crawl_delay(AGENT) or 0)
        if delay>30:raise ValueError('crawl_delay_exceeds_research_budget')
        time.sleep(delay)
        source=get(url);stamp=datetime.now(timezone.utc).isoformat()
        # Preserve privately recoverable original, never a public plaintext artifact.
        aad=('kyoto-workout-research-v1|'+os.environ['GITHUB_REPOSITORY']+'|'+os.environ['GITHUB_RUN_ID']+'|'+day).encode()
        nonce=secrets.token_bytes(12);cipher=AESGCM(key).encrypt(nonce,source,aad)
        assert AESGCM(key).decrypt(nonce,cipher,aad)==source
        (out/'source.aesgcm').write_bytes(nonce+cipher)
        report.update(source_sha256=digest(source),source_bytes=len(source),source_captured_utc=stamp,source_ciphertext_sha256=digest(nonce+cipher),archive_aad=aad.decode(),encrypted_readback_verified=True)
        result,records=bind(source,day,race,url,stamp,roster,start)
        report.update(result);report['status']='HISTORICAL_BINDING_VERIFIED'
    except Exception as e:
        report.update(status='BINDING_UNVERIFIED',error_type=type(e).__name__)
        if isinstance(e,ValueError):report['error_code']=str(e)[:100]
    (out/'receipt.json').write_text(json.dumps(report,sort_keys=True,indent=2),encoding='utf8')
    print('WORKOUT_BINDING='+json.dumps(report,sort_keys=True))

if __name__=='__main__':main()
