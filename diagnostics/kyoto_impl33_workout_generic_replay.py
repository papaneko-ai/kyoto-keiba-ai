"""Replay seven preserved pre-day originals. Do not invent official rosters."""
import json,os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_impl33_workout_generic import parse_observed
from diagnostics.kyoto_impl33_workout_all12 import digest,seal
from bs4 import BeautifulSoup
from diagnostics.kyoto_impl33_whitegreen_probe import tables,text
def main():
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('key')
    src=Path('previous_upcoming');old=json.loads((src/'receipt.json').read_text())
    out=Path('generic_workout');out.mkdir(exist_ok=True);report={'races':[],'actual_official_rosters_verified':False,'network_requests':0,'production_coverage_authorized':False}
    for day,group in old['days'].items():
        for item in group['races']:
            if item['status']!='PRE_DAY_SOURCE_FROZEN':continue
            race=item['race'];aad=f'kyoto-workout-upcoming-v1|{os.environ["GITHUB_REPOSITORY"]}|45755377155|{day}|{race}'.encode()
            blob=(src/f'{day}_r{race:02d}.aesgcm').read_bytes()
            if item['archive_aad'].encode()!=aad or digest(blob)!=item['source_ciphertext_sha256']:raise ValueError('cipher')
            raw=AESGCM(key).decrypt(blob[:12],blob[12:],aad)
            if digest(raw)!=item['source_sha256']:raise ValueError('raw')
            rec,names,records,issues=parse_observed(raw,day,race,item['url'],item['captured_utc'],((day,race,item['url']),))
            a=f'kyoto-workout-generic-preview-v1|{os.environ["GITHUB_RUN_ID"]}|{day}|{race}'.encode()
            normalized=seal(out,f'{day}_r{race:02d}.aesgcm',json.dumps(records,ensure_ascii=False,sort_keys=True,allow_nan=False).encode(),key,a)
            # Structural headings only; no names or third-party records in public logs.
            headings={}
            for node,h,rows in tables(BeautifulSoup(raw,'html.parser')):
                if h not in (('日','コース','本線','終い'),('日','コース','本線','終い','脚色')):continue
                h4=node.find_previous('h4');label=text(h4) if h4 else ''
                if len(label)<80 and not any(n in label for n in names):headings[label]=headings.get(label,0)+1
            report['races'].append({'day':day,'race':race,'registered_names':len(names),'name_bound_horses':sum(bool(v) for v in records.values()),'records':sum(map(len,records.values())),'issues':{k:issues.count(k) for k in set(issues)},'headings':headings,'ciphertext_sha256':normalized,'aad':a.decode()})
    report['status']='REPLAY_FINISHED'
    (out/'receipt.json').write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2))
    print('GENERIC_WORKOUT='+json.dumps(report,sort_keys=True,ensure_ascii=False))
if __name__=='__main__':main()
