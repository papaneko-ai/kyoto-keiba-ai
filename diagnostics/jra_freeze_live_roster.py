"""Fail-closed official JRA live Kyoto racecard parser; freeze minimal before-race facts.
Never treats CNAME as verified permanent horse ID or as model-ready training data.
"""
from datetime import datetime,timezone,date
from hashlib import sha256
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import re,json,argparse
from pathlib import Path
TARGET_DATE=date(2026,11,7)
EXPECTED_RACE=7
def parse(raw,receipt):
 if sha256(raw).hexdigest()!=receipt.get('source_sha256') or len(raw)!=receipt.get('source_bytes'):
  raise ValueError('source_bytes_mismatch')
 src=urlsplit(receipt.get('source_url',''))
 if src.scheme!='https' or src.hostname not in ('jra.jp','www.jra.go.jp'):
  raise ValueError('not_official_jra_source')
 ts=datetime.fromisoformat(receipt.get('fetched_at_utc','').replace('Z','+00:00'))
 if ts.tzinfo is None:raise ValueError('missing_UTC_timestamp')
 ts=ts.astimezone(timezone.utc)
 cutoff=datetime.fromisoformat('2026-11-07T04:25:00+00:00')
 if ts>=cutoff:raise ValueError('not_pre_race_capture')
 soup=BeautifulSoup(raw.decode('cp932',errors='replace'),'html.parser')
 tables=[t for t in soup.select('table') if t.select_one('th.horse') and t.select_one('th.num') and t.select_one('th.waku')]
 if len(tables)!=1:raise ValueError('ambiguous_racecard_tables')
 out=[];errors=[]
 for row_index,tr in enumerate(tables[0].select('tr')):
  n=tr.select_one('td.num');td=tr.select_one('td.horse')
  if n is None and td is None:continue
  if n is None or td is None:
   errors.append({'row':row_index,'reason':'missing_horse_cell'});continue
  value=n.get_text(' ',strip=True)
  a=td.select_one('a[href*="/JRADB/accessU.html"]')
  if not value.isascii() or not value.isdigit() or a is None:
   errors.append({'row':row_index,'reason':'invalid_number_or_name_link'});continue
  horse=int(value);name=a.get_text(' ',strip=True)
  href=a.get('href','')
  if not name or not href.startswith('/JRADB/accessU.html?CNAME='):
   errors.append({'row':row_index,'reason':'invalid_horse_profile'});continue
  frame=tr.select_one('td.waku')
  alts=[x.get('alt','') for x in frame.select('img[alt]')] if frame else []
  frame_num=None
  for alt in alts:
   m=re.search(r'枠\s*([1-8])|([1-8])\s*枠',alt)
   if m:frame_num=int(m.group(1) or m.group(2));break
  dates=[]
  for c in tr.select('td.past'):
   txt=c.get_text(' ',strip=True)
   m=re.search(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日',txt)
   if m:
    try:dt=date(*map(int,m.groups()))
    except ValueError:
     errors.append({'horse_number':horse,'reason':'invalid_history_date'});continue
    if dt>=TARGET_DATE:errors.append({'horse_number':horse,'reason':'history_not_prior'})
    else:dates.append(dt.isoformat())
  out.append({'horse_number':horse,'frame_number':frame_num,'horse_name':name,
   'horse_profile_href':href,'profile_navigation_only':True,
   'official_permanent_horse_id':None,'prior_race_dates':dates,
   'historical_results_are_prior_by_date':all(date.fromisoformat(x)<TARGET_DATE for x in dates),
   'status':'ENTRY_LISTED_NOT_INDEPENDENTLY_CONFIRMED'})
 numbers=[x['horse_number'] for x in out]
 if len(numbers)!=len(set(numbers)):errors.append({'reason':'duplicate_horse_number'})
 if sorted(numbers)!=list(range(1,len(out)+1)):errors.append({'reason':'horse_numbers_non_contiguous'})
 if len(out)!=11:errors.append({'reason':'unexpected_horse_count','actual':len(out)})
 ready=not errors and len(out)==11
 return {'schema_version':'jra_prerace_roster_20261107_kyoto7.v1',
         'venue':'KYOTO','race_date':'2026-11-07','race_number':EXPECTED_RACE,
         'fetched_at_utc':ts.isoformat(),'source_sha256':receipt['source_sha256'],
         'source_url':receipt['source_url'],'source_bytes':len(raw),
         'raw_capture_verified':True,'racecard_horse_rows_verified':ready,
         'runners':out,'runner_count':len(out),'errors':errors,
         'all_frames_extracted':all(x['frame_number'] is not None for x in out),
         'official_permanent_ids_verified':False,'scratches_verified':False,
         'odds_snapshot_verified':False,'ready_for_prediction':False,
         'ready_for_training':False,
         'reason':'needs_stable_ids_scratches_odds_and_independent_evidence'}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--html',required=True);ap.add_argument('--receipt',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 result=parse(Path(a.html).read_bytes(),json.loads(Path(a.receipt).read_text(encoding='utf8')))
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({k:v for k,v in result.items() if k!='runners'},ensure_ascii=False))
