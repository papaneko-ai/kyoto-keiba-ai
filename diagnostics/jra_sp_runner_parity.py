"""PC/SP parity verification for Kyoto 11R: extract only runner rows, never nonselected horses."""
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from datetime import datetime,timezone
from hashlib import sha256
import json,re,argparse
SP_URL="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261107%2FA0"
PC_PATH=Path('docs/diagnostics/remaining8_20261106/kyoto_11_snapshot.json')
def extract_sp_rows(raw):
 soup=BeautifulSoup(raw.decode('cp932',errors='replace'),'html.parser')
 tab=soup.select_one('table')
 if tab is None:raise ValueError('sp_main_table_missing')
 entries=[]
 for tag in tab.select('.bamei'):
  a=tag.select_one('a[href*="/JRADB/accessU.html"]')
  if a is None:continue
  name=a.get_text(' ',strip=True)
  tr=tag.find_parent('tr')
  if tr is None:raise ValueError('bamei_not_in_table_row')
  numtag=tr.select_one('.uban')
  num_text=numtag.get_text(' ',strip=True) if numtag else ''
  num_match=re.search(r'(?<!\d)(1[0-8]|[1-9])(?!\d)',num_text)
  num=int(num_match.group(1)) if num_match else None
  wban=tr.select_one('.wban')
  frame_hint=wban.get_text(' ',strip=True) if wban else None
  entries.append({'number':num,'name':name,'profile_path':a.get('href',''),
                  'number_cell_text':num_text,'frame_cell_text':frame_hint,
                  'row_classes':tr.get('class',[])})
 return entries

def evaluate(raw,pc):
 entries=extract_sp_rows(raw)
 seen={}
 for x in entries:
  if x['name'] in seen:raise ValueError('duplicate_SP_runner_name')
  seen[x['name']]=x
 checks=[]
 for p in pc['runners']:
  sp=seen.get(p['horse_name'])
  checks.append({'pc_horse_number':p['horse_number'],'pc_horse_name':p['horse_name'],
                 'sp_horse_number':sp['number'] if sp else None,
                 'sp_found':sp is not None,
                 'number_matches':bool(sp and sp['number']==p['horse_number']),
                 'sp_frame_cell_text':sp['frame_cell_text'] if sp else None,
                 'sp_profile_link_present':bool(sp and sp['profile_path'].startswith('/JRADB/accessU.html?CNAME='))})
 return {'schema_version':'jra_pc_sp_11r_runner_comparison.v1',
    'pc_runner_count':len(pc['runners']),'sp_runner_candidate_count':len(entries),
    'unique_sp_candidate_names':len(seen),'number_match_count':sum(x['number_matches'] for x in checks),
    'full_number_name_parity':len(entries)==len(pc['runners']) and all(x['number_matches'] for x in checks),
    'sp_extracted_rows':entries,'checks':checks,
    'profile_navigation_id_equivalence_proven':False,
    'frame_equivalence_proven':False,'past_run_field_equivalence_proven':False,
    'prediction_ready':False,'training_ready':False}

def run(folder,opener=urlopen,clock=lambda:datetime.now(timezone.utc)):
 dst=Path(folder);dst.mkdir(parents=True,exist_ok=True)
 pc=json.loads(PC_PATH.read_text(encoding='utf8'))
 result={'status':'STARTED','source_url':SP_URL,'pc_sha256':pc['source_sha256'],
         'started_at_utc':clock().isoformat(),'sp_source_sha256':None,
         'sp_bytes':None,'error':None,'ready_for_prediction':False}
 try:
  with opener(Request(SP_URL,headers={'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1','Accept':'text/html'},method='GET'),timeout=20) as resp:
   raw=resp.read(1000001);u=urlsplit(resp.geturl())
   status=resp.status;ct=resp.headers.get('Content-Type','')
  if status!=200 or not 0<len(raw)<=1000000 or 'html' not in ct.lower() or u.scheme!='https' or u.hostname not in ('sp.jra.jp','app.jra.jp'):
   raise ValueError('invalid_official_mobile_html')
  data=evaluate(raw,pc)
  (dst/'sp_11r_original.html').write_bytes(raw)
  (dst/'sp_runner_comparison.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  result.update(status='PARITY_OK' if data['full_number_name_parity'] else 'PARITY_BLOCKED',
     sp_source_sha256=sha256(raw).hexdigest(),sp_bytes=len(raw),
     pc_bytes=pc['source_bytes'],pc_horse_count=pc['runner_count'],
     sp_horse_count=data['sp_runner_candidate_count'],
     number_name_matches=data['number_match_count'],
     source_reduction_pct=round((1-len(raw)/pc['source_bytes'])*100,1),
     sp_page_host=u.hostname,sp_row_parity_checked=True,
     frame_equivalence_proven=False,history_equivalence_proven=False)
 except Exception as e:
  result.update(status='FAILED',error=type(e).__name__+':'+str(e)[:200])
 finally:
  result['finished_at_utc']=clock().isoformat()
  (dst/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default='jra_sp_parity');a=p.parse_args()
 print(json.dumps(run(a.out),ensure_ascii=False))
