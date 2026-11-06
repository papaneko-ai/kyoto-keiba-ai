"""Offline JRA horse-history reader. Only prior-date runs, never subsequent profile summaries."""
from bs4 import BeautifulSoup
from datetime import date,datetime,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from hashlib import sha256
import re

HEADERS=('年月日','場','レース名','距離','馬場','頭数','人気','着順','騎手名','負担重量','馬体重','タイム','Rt','1着馬（2着馬）')
DATE=re.compile(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$')
COURSE=re.compile(r'^(芝|ダ|ダート|障)(\d{3,4})$')

def parse_horse_history(raw:bytes,*,source_url:str,fetched_at_utc:datetime,
                        prediction_cutoff_utc:datetime,target_date:date,
                        expected_horse_name:str|None=None)->dict:
    u=urlsplit(source_url)
    if u.scheme!='https' or u.hostname not in ('www.jra.go.jp','jra.go.jp','jra.jp') or u.path!='/JRADB/accessU.html':
        raise ValueError('jra_profile_url_required')
    if not raw or len(raw)>2_000_000:raise ValueError('invalid_html_size')
    for x in (fetched_at_utc,prediction_cutoff_utc):
        if not isinstance(x,datetime) or x.tzinfo is None or x.utcoffset() is None:
            raise ValueError('aware_timestamps_required')
    if not isinstance(target_date,date) or isinstance(target_date,datetime):
        raise ValueError('target_date_required')
    soup=BeautifulSoup(raw.decode('cp932',errors='replace'),'html.parser')
    identity=None
    for item in soup.select('span.txt'):
        if item.select_one('span.opt') and '競走馬情報' in item.get_text(' ',strip=True):
            copy=BeautifulSoup(str(item),'html.parser')
            for child in copy.select('span.opt,span.name_en'):child.decompose()
            identity=copy.get_text(' ',strip=True) or None
            break
    if expected_horse_name and identity!=expected_horse_name:
        raise ValueError('profile_horse_name_mismatch')
    table=next((t for t in soup.select('table') if t.select_one('th.date') and
                t.select_one('th.place') and t.select_one('th.dist')),None)
    if table is None:raise ValueError('history_table_missing')
    headers=tuple(th.get_text(' ',strip=True) for th in table.select('tr th'))
    if headers!=HEADERS:raise ValueError('history_schema_changed')
    accepted,excluded,invalid=[],[],[]
    seen=set()
    cutoff_date=prediction_cutoff_utc.astimezone(ZoneInfo('Asia/Tokyo')).date()
    for row,tr in enumerate(table.select('tr')[1:],1):
        cells=tr.find_all('td',recursive=False)
        if len(cells)!=len(HEADERS):
            invalid.append({'row':row,'reason':'column_count_changed'});continue
        v=[td.get_text(' ',strip=True) for td in cells]
        m=DATE.fullmatch(v[0])
        try:dt=date(*map(int,m.groups())) if m else None
        except ValueError:dt=None
        if dt is None:
            invalid.append({'row':row,'reason':'invalid_date'});continue
        if dt>=target_date:
            excluded.append({'row':row,'date':dt.isoformat(),'reason':'same_day_or_future_event'});continue
        if dt>=cutoff_date:
            excluded.append({'row':row,'date':dt.isoformat(),'reason':'cutoff_date_not_proven'});continue
        if dt in seen:
            invalid.append({'row':row,'reason':'duplicate_race_date_unresolved'});continue
        seen.add(dt)
        cm=COURSE.fullmatch(v[3])
        if not cm:
            invalid.append({'row':row,'reason':'unparsed_surface_or_distance'});continue
        try:
            n=int(v[5]);rank=int(v[7]);distance=int(cm.group(2))
            if n<2 or not(1<=rank<=n):raise ValueError()
        except ValueError:
            invalid.append({'row':row,'reason':'missing_or_invalid_finish'});continue
        accepted.append({'date':dt.isoformat(),'venue':v[1],'race_title':v[2],
                         'surface':cm.group(1),'distance_m':distance,'going':v[4],
                         'field_size':n,'popularity':v[6],'finish_position':rank,
                         'jockey':v[8],'carried_weight':v[9],'body_weight':v[10],
                         'time':v[11],'finish_percentile':(n-rank)/(n-1)})
    accepted.sort(key=lambda x:x['date'],reverse=True)
    return {'schema_version':'jra_prior_form_offline.v1','source_url':source_url,
            'source_sha256':sha256(raw).hexdigest(),
            'fetched_at_utc':fetched_at_utc.astimezone(timezone.utc).isoformat(),
            'prediction_cutoff_utc':prediction_cutoff_utc.astimezone(timezone.utc).isoformat(),
            'target_date':target_date.isoformat(),'profile_horse_name':identity,
            'jra_horse_id':None,'jra_horse_id_verified':False,
            'profile_captured_before_cutoff':fetched_at_utc<=prediction_cutoff_utc,
            'history_rows_total':len(table.select('tr'))-1,'prior_rows':accepted,
            'prior_row_count':len(accepted),'excluded_rows':excluded,'invalid_rows':invalid,
            'pre_race_snapshot_verified':False,'prediction_ready':False,
            'missing_reason':'profile_snapshot_or_official_id_not_verified_at_prediction_cutoff'}
