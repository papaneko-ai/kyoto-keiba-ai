"""Replay preserved failing source and try independent observed backup pages."""
import json,os,time
from pathlib import Path
from datetime import datetime,timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_impl33_workout_all12 import official_rosters,seal,digest,DAY
from diagnostics.kyoto_impl33_workout_binding import bind
from diagnostics.kyoto_impl33_hybrid_workout_runner import retained,approved_get
from diagnostics.kyoto_impl33_hybrid_workout import parse_table_v2,parse_labeled_turf,parse_news_turf,recover
from bs4 import BeautifulSoup
from diagnostics.kyoto_impl33_whitegreen_probe import text

SOURCES=[('netkeiba','https://news.netkeiba.com/?no=349202&pid=news_view',parse_news_turf),('talmudic','https://talmudic.net/2026-mile-championship-training/',parse_labeled_turf)]
def main():
    key=bytes.fromhex(os.environ['ARCHIVE_KEY'])
    if len(key)!=32:raise ValueError('archive_key')
    out=Path('hybrid_recovery');out.mkdir(exist_ok=True)
    prior=json.loads((Path('missing_workout')/'receipt.json').read_text())
    earlier=json.loads((Path('previous_hybrid')/'receipt.json').read_text())
    if earlier['covered']!=158 or prior['races_bound']!=12:raise ValueError('scope')
    rosters=official_rosters(key);n=11
    roster,start,h=rosters[n];item=next(r for r in prior['races'] if r['race']==n)
    raw=retained(n,item,key)
    old,primary=bind(raw,DAY,n,item['url'],item['captured_utc'],roster,start,((DAY,n,item['url']),))
    if old['normalized_digest']!=item['normalized_digest'] or h!=item['official_original_sha256']:raise ValueError('prior_identity')
    missing=[k for k in roster if not primary[k]]
    obs={k:[] for k in missing};reports=[]
    src=next(s for r in earlier['races'] if r['race']==n for s in r['sources'] if s['provider']=='umasiru')
    blob=(Path('previous_hybrid')/'r11_umasiru.aesgcm').read_bytes()
    aad=f'kyoto-workout-hybrid-v1|{os.environ["GITHUB_REPOSITORY"]}|45756109438|{DAY}|11|umasiru'.encode()
    if src['archive_aad'].encode()!=aad or digest(blob)!=src['ciphertext_sha256']:raise ValueError('cipher_identity')
    data=AESGCM(key).decrypt(blob[:12],blob[12:],aad)
    if digest(data)!=src['source_sha256']:raise ValueError('raw_identity')
    entry={'provider':'umasiru','reused_original':True,'source_sha256':digest(data),'matches':0}
    for k in missing:
        rec=parse_table_v2(data,roster[k],'2026-11-22')
        if rec:obs[k].append({'provider':'umasiru','record':rec});entry['matches']+=1
        else:
            soup=BeautifulSoup(data,'html.parser')
            heads=[v for v in soup.find_all(['h2','h3','h4','h5','h6']) if roster[k] in text(v)]
            entry['heading_matches']=[{'tag':v.name,'exact':text(v)==roster[k]} for v in heads]
            if heads:
                tab=heads[0].find_next('table')
                entry['table_header']=[text(c) for c in tab.find('tr').find_all(['th','td'])] if tab and tab.find('tr') else []
    reports.append(entry)
    for provider,url,parser in SOURCES:
        s={'provider':provider,'url':url,'matches':0}
        try:
            data=approved_get(url);stamp=datetime.now(timezone.utc).isoformat()
            aad=f'kyoto-workout-hybrid-recovery-v1|{os.environ["GITHUB_REPOSITORY"]}|{os.environ["GITHUB_RUN_ID"]}|{DAY}|11|{provider}'.encode()
            s.update(source_sha256=digest(data),captured_utc=stamp,ciphertext_sha256=seal(out,provider+'.aesgcm',data,key,aad),archive_aad=aad.decode())
            for k in missing:
                rec=parser(data,roster[k],'2026-11-22')
                if rec:obs[k].append({'provider':provider,'record':rec});s['matches']+=1
            s['status']='PARSED'
        except Exception as e:
            s.update(status='UNVERIFIED',error_type=type(e).__name__)
        reports.append(s)
        # Stop when two distinct provider formats have matching records.
        _,audit=recover(primary,roster,obs)
        if all(x['status']=='CORROBORATED' for x in audit):break
    merged,audit=recover(primary,roster,obs)
    added=sum(bool(merged[k]) for k in missing)
    aad=f'kyoto-workout-hybrid-recovery-normalized-v1|{os.environ["GITHUB_RUN_ID"]}|11'.encode()
    normalized=seal(out,'normalized.aesgcm',json.dumps(merged,sort_keys=True,allow_nan=False).encode(),key,aad)
    report={'status':'HISTORICAL_RESEARCH_FINISHED','covered':158+added,'official_horses':159,'records':1698+sum(len(merged[k]) for k in missing),'recovery':audit,'sources':reports,'normalized_ciphertext_sha256':normalized,'normalized_aad':aad.decode(),'r9_rejection':earlier['races'][0]['rejected_rows'],'jra_requests':0,'production_coverage_authorized':False}
    (out/'receipt.json').write_text(json.dumps(report,sort_keys=True,indent=2),encoding='utf8')
    print('HYBRID_RECOVERY='+json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
