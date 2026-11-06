"""Compare one official SP racecard to previously frozen PC entrants; single GET only."""
import json,re,hashlib
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from pathlib import Path
from bs4 import BeautifulSoup

URL='https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261107%2FA0'
PC_SNAPSHOT=Path('docs/diagnostics/remaining8_20261106/kyoto_11_snapshot.json')

def inspect(raw, pc):
    soup=BeautifulSoup(raw.decode('cp932',errors='replace'),'html.parser')
    text=soup.get_text(' ',strip=True)
    horse_names=[h['horse_name'] for h in pc['runners']]
    full_text_matches=[h for h in horse_names if h in text]
    tables=soup.select('table')
    candidate=[]
    for ti,t in enumerate(tables):
        heads=t.get_text(' ',strip=True)[:180]
        trs=t.select('tr')
        candidate.append({'table_index':ti,'rows':len(trs),'header':heads})
    # Document DOM classes, not scraped names and not personal information
    classes={}
    for el in soup.select('[class]'):
        for c in el.get('class',[]):classes[c]=classes.get(c,0)+1
    links=[]
    for a in soup.select('a[href]'):
        u=a.get('href','')
        if '/JRADB/accessU.html' in u:
            links.append({'name':a.get_text(' ',strip=True)[:45],'path':u[:150]})
    # Match full unique official 16 horse names as observed in visible page body.
    return {'title':soup.title.get_text(' ',strip=True) if soup.title else '',
      'html_tables':len(tables),'table_shapes':candidate[:8],
      'tr_count':len(soup.select('tr')),'div_count':len(soup.select('div')),
      'official_horse_names_expected':len(horse_names),
      'horse_names_found_in_visible_text':len(full_text_matches),
      'horse_names_missing':[h for h in horse_names if h not in text],
      'horse_profile_links_count':len(links),'profile_links_sample':links[:3],
      'likely_classes':sorted(classes.items(),key=lambda x:-x[1])[:30],
      'first_450_chars':text[:450],
      'roster_equivalence_certified':False,
      'ready_for_prediction':False,'ready_for_training':False}

def run(out,opener=urlopen,clock=lambda:datetime.now(timezone.utc)):
 root=Path(out);root.mkdir(parents=True,exist_ok=True)
 pc=json.loads(PC_SNAPSHOT.read_text(encoding='utf-8'))
 stamp=clock()
 receipt={'schema_version':'jra_pc_sp_11r_probe.v1','race':'KYOTO_2026-11-07_11R',
   'source_url':URL,'captured_at_utc':stamp.isoformat(),'status':'ATTEMPTED',
   'pc_horse_count':pc['runner_count'],'pc_sha256':pc['source_sha256'],
   'sp_sha256':None,'sp_html_bytes':None,'error':None,
   'html_raw_persisted_to_public_repo':False,'comparison_verified':False,
   'ready_for_training':False}
 try:
    if stamp>=datetime.fromisoformat('2026-11-07T06:35:00+00:00'):
        raise ValueError('race_cutoff_passed')
    req=Request(URL,headers={'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1','Accept':'text/html'},method='GET')
    with opener(req,timeout=20) as response:
        raw=response.read(1000001);status=response.status
        final=urlsplit(response.geturl());ct=response.headers.get('Content-Type','')
    if status!=200 or not 0<len(raw)<=1000000 or 'html' not in ct.lower():
        raise ValueError('non_html_or_http_failure')
    if final.scheme!='https' or final.hostname not in ('sp.jra.jp','app.jra.jp','jra.jp'):
        raise ValueError('unexpected_origin')
    summary=inspect(raw,pc)
    (root/'sp_kyoto11r.html').write_bytes(raw)
    receipt.update(status='HTML_SAVED_NEEDS_PARSER_VALIDATION',http_status=status,
        sp_sha256=hashlib.sha256(raw).hexdigest(),sp_html_bytes=len(raw),
        final_hostname=final.hostname,title=summary['title'],
        all_16_names_located=summary['horse_names_found_in_visible_text']==pc['runner_count'])
    (root/'structure.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 except Exception as e:
    receipt.update(status='FAILED',error=type(e).__name__+':'+str(e)[:180])
 finally:
    receipt['completed_at_utc']=clock().isoformat()
    (root/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return receipt

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--out',default='jra_pc_sp_probe');a=p.parse_args()
 print(json.dumps(run(a.out),ensure_ascii=False))
