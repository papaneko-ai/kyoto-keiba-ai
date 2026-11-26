"""No network: use exactly the retained encrypted bytes to recover missing clock."""
import json,os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_impl33_workout_all12 import official_rosters,seal,digest,DAY
from diagnostics.kyoto_impl33_workout_binding import bind
from diagnostics.kyoto_impl33_hybrid_workout_runner import retained
from diagnostics.kyoto_impl33_hybrid_workout import parse_table_v3,parse_labeled_turf,recover,preserve_partial

def decode(path,s,key,aad):
    blob=path.read_bytes()
    if s['archive_aad'].encode()!=aad or digest(blob)!=s['ciphertext_sha256']:raise ValueError('cipher_identity')
    raw=AESGCM(key).decrypt(blob[:12],blob[12:],aad)
    if digest(raw)!=s['source_sha256']:raise ValueError('raw_identity')
    return raw
def main():
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    out=Path('offline_hybrid');out.mkdir(exist_ok=True)
    prior=json.loads((Path('missing_workout')/'receipt.json').read_text())
    earlier=json.loads((Path('previous_hybrid')/'receipt.json').read_text())
    latest=json.loads((Path('previous_recovery')/'receipt.json').read_text())
    if earlier['covered']!=158 or latest['covered']!=158 or prior['races_bound']!=12:raise ValueError('scope')
    rosters=official_rosters(key);n=11
    roster,start,h=rosters[n];item=next(r for r in prior['races'] if r['race']==n)
    raw=retained(n,item,key)
    old,primary=bind(raw,DAY,n,item['url'],item['captured_utc'],roster,start,((DAY,n,item['url']),))
    if old['normalized_digest']!=item['normalized_digest'] or h!=item['official_original_sha256']:raise ValueError('prior_identity')
    missing=[k for k in roster if not primary[k]];obs={k:[] for k in missing};reports=[]
    src=next(s for r in earlier['races'] if r['race']==n for s in r['sources'] if s['provider']=='umasiru')
    raw1=decode(Path('previous_hybrid')/'r11_umasiru.aesgcm',src,key,f'kyoto-workout-hybrid-v1|{os.environ["GITHUB_REPOSITORY"]}|45756109438|{DAY}|11|umasiru'.encode())
    src2=next(s for s in latest['sources'] if s['provider']=='talmudic')
    raw2=decode(Path('previous_recovery')/'talmudic.aesgcm',src2,key,f'kyoto-workout-hybrid-recovery-v1|{os.environ["GITHUB_REPOSITORY"]}|45756250180|{DAY}|11|talmudic'.encode())
    for provider,data,parser in [('umasiru',raw1,parse_table_v3),('talmudic',raw2,parse_labeled_turf)]:
        s={'provider':provider,'source_sha256':digest(data),'matches':0,'reused_original':True}
        for k in missing:
            rec=parser(data,roster[k],'2026-11-22')
            if rec:obs[k].append({'provider':provider,'record':rec});s['matches']+=1
        reports.append(s)
    merged,audit=recover(primary,roster,obs);added=sum(bool(merged[k]) for k in missing)
    aad=f'kyoto-workout-offline-hybrid-v1|{os.environ["GITHUB_RUN_ID"]}|11'.encode()
    normalized=seal(out,'normalized.aesgcm',json.dumps(merged,sort_keys=True,allow_nan=False).encode(),key,aad)
    item9=next(r for r in prior['races'] if r['race']==9);r9,s9,h9=rosters[9];raw9=retained(9,item9,key)
    if h9!=item9['official_original_sha256']:raise ValueError('official_r9_identity')
    partial=preserve_partial(raw9,'2026-11-22',r9,item9['captured_utc'])
    rejected={r['row_sha256'] for r in latest['r9_rejection']}
    partial=[p for p in partial if p['row_sha256'] in rejected]
    paad=f'kyoto-workout-offline-hybrid-v1|{os.environ["GITHUB_RUN_ID"]}|9-partial'.encode()
    psha=seal(out,'partial.aesgcm',json.dumps(partial,sort_keys=True,allow_nan=False).encode(),key,paad)
    report={'status':'HISTORICAL_OFFLINE_REPLAY_FINISHED','covered':158+added,'official_horses':159,'records':1698+sum(len(merged[k]) for k in missing),'recovery':audit,'sources':reports,'normalized_ciphertext_sha256':normalized,'normalized_aad':aad.decode(),'partial_observations':len(partial),'partial_last_1f_missing':sum(p['last_1f_s'] is None for p in partial),'partial_ciphertext_sha256':psha,'partial_aad':paad.decode(),'network_requests':0,'production_coverage_authorized':False}
    (out/'receipt.json').write_text(json.dumps(report,sort_keys=True,indent=2),encoding='utf8')
    print('OFFLINE_HYBRID='+json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
