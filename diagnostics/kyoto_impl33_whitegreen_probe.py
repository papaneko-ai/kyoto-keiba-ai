"""Bounded public-source research. No production collection or prediction authority."""
import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

HOST = 'https://white-green.jp'
AGENT = 'KyotoResearchProbe/1.0'
SAMPLES = (("20261122", 1, HOST + '/race/20261122-kyoto-01/'),
           ("20261128", 9, HOST + '/race/20261128-kyoto-09/'))
MAX_BYTES = 4_000_000
JST = timezone(timedelta(hours=9))
COURSES = {'栗東CW':'RITTO_CW', '栗東坂路':'RITTO_HILL', '美浦W':'MIHO_W', '美浦坂路':'MIHO_HILL'}
FINAL = ('枠','馬番','馬名','判定','コース','本線','終い','併せ馬')
FINAL_SHORT = FINAL[:-1]
PREVIEW = ('馬名','判定','コース','本線','終い')


def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()


def tables(soup):
    for table in soup.find_all('table'):
        rows = [[text(c) for c in tr.find_all(['th','td'], recursive=False)]
                for tr in table.find_all('tr')]
        if rows and rows[0]:
            yield table, tuple(rows[0]), rows[1:]


def timing(course, main, last):
    m = re.fullmatch(r'([1-9])F\s+([0-9]+(?:\.[0-9]+)?)', main)
    if course not in COURSES or not m or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', last):
        return None
    f, total, end = int(m[1]), float(m[2]), float(last)
    if not 0 < end <= total <= 600:
        return None
    return {'course':COURSES[course], 'distance_m':f*200, 'elapsed_s':total, 'last_1f_s':end}


def inspect(raw, day, race, url, captured_utc, observed_urls=()):
    expected = HOST + f'/race/{day}-kyoto-{race:02d}/'
    if (day,race,url) not in SAMPLES and (url != expected or (day,race,url) not in observed_urls or not 1 <= race <= 12):
        raise ValueError('unobserved_sample_identity')
    if not isinstance(raw,bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('invalid_bytes')
    stamp=datetime.fromisoformat(captured_utc.replace('Z','+00:00'))
    if stamp.utcoffset()!=timedelta(0):
        raise ValueError('utc_required')
    d=date.fromisoformat(f'{day[:4]}-{day[4:6]}-{day[6:]}')
    soup=BeautifulSoup(raw,'html.parser')
    h1=soup.find('h1')
    # Identity is established from both the known URL and visible race heading/date.
    if h1 is None or not re.search(rf'京都\s*{race}R\b',text(h1)) or f'{d.year}年{d.month}月{d.day}日' not in text(soup):
        raise ValueError('visible_race_identity')
    result_section=any(text(h)=='レース結果' for h in soup.find_all(['h2','h3','h4']))
    matches=[(header,rows) for _,header,rows in tables(soup) if header in (FINAL,FINAL_SHORT,PREVIEW)]
    finals=[rows for header,rows in matches if header in (FINAL,FINAL_SHORT)]
    previews=[rows for header,rows in matches if header==PREVIEW]
    if len(finals)>1 or len(previews)>1 or not (finals or previews):
        raise ValueError('ambiguous_or_missing_summary')
    final=bool(finals)
    rows=(finals or previews)[0]
    names=set(); numbers=set(); valid=0; missing=0
    for row in rows:
        if (final and len(row) not in (7,8)) or (not final and len(row)!=5):
            raise ValueError('summary_shape')
        if final:
            _,number,name,_,course,main,last=row[:7]
            if not re.fullmatch(r'[1-9]|1[0-8]',number) or number in numbers:
                raise ValueError('duplicate_or_invalid_horse_number')
            numbers.add(number)
        else:
            name,_,course,main,last=row
        if not name or name in names:
            raise ValueError('duplicate_or_missing_name')
        names.add(name)
        if timing(course,main,last) is None: missing+=1
        else: valid+=1
    if not rows or (final and len(rows)>18):
        raise ValueError('roster_size')
    history_tables=0
    history_rows=0
    for _,header,history in tables(soup):
        if header in (('日','コース','本線','終い'),('日','コース','本線','終い','脚色')):
            history_tables+=1
            for row in history:
                if len(row)!=len(header) or not re.fullmatch(r'\d{1,2}/\d{1,2}',row[0]): continue
                month,dd=map(int,row[0].split('/'))
                dates=[]
                for year in (d.year-1,d.year):
                    try: x=date(year,month,dd)
                    except ValueError: continue
                    if d-timedelta(days=31)<=x<d and x<=stamp.astimezone(JST).date(): dates.append(x)
                if len(dates)==1 and timing(*row[1:4]): history_rows+=1
    return {'schema':'kyoto_whitegreen_source_probe.v1','day':day,'race':race,'url':url,
            'captured_utc':stamp.isoformat(),'source_sha256':sha256(raw).hexdigest(),'bytes':len(raw),
            'summary_kind':'FINAL_NUMBERED' if final else 'SPECIAL_REGISTRATION_PREVIEW',
            'summary_rows':len(rows),'rows_with_numeric_times':valid,'rows_without_numeric_times':missing,
            'history_tables':history_tables,'dated_numeric_history_rows':history_rows,
            'result_section_present':result_section,'observed_before_race_day':stamp.astimezone(JST).date()<d,
            'independent_roster_verified':False,'horse_history_binding_verified':False,
            'production_coverage_authorized':False,'live_acquisition_certified':False}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('redirect_not_followed')


def get(url):
    with build_opener(NoRedirect()).open(Request(url,headers={'User-Agent':AGENT}),timeout=10) as r:
        if r.status!=200: raise ValueError('http_status')
        raw=r.read(MAX_BYTES+1)
        if not 0<len(raw)<=MAX_BYTES: raise ValueError('response_size')
        return raw


def probe():
    report={'schema':'kyoto_whitegreen_bounded_probe.v1','samples':[], 'production_coverage_authorized':False,'jra_requests':0}
    try:
        try: robots=get(HOST+'/robots.txt').decode('utf8')
        except HTTPError as e:
            if e.code!=404: raise
            robots='User-agent: *\nDisallow:'
        rp=RobotFileParser(); rp.parse(robots.splitlines())
    except Exception as e:
        report['status']='ROBOTS_UNVERIFIED'; report['error_type']=type(e).__name__; return report
    for day,race,url in SAMPLES:
        item={'url':url,'day':day,'race':race}
        if not rp.can_fetch(AGENT,url):
            item['status']='ROBOTS_DISALLOW'
        else:
            time.sleep(max(2,rp.crawl_delay(AGENT) or 0))
            try:
                raw=get(url); stamp=datetime.now(timezone.utc).isoformat()
                item.update({'source_sha256':sha256(raw).hexdigest(),'bytes':len(raw),'captured_utc':stamp})
                item.update(inspect(raw,day,race,url,stamp)); item['status']='PARSED_RESEARCH_SAMPLE'
            except Exception as e:
                item.update(status='UNVERIFIED',error_type=type(e).__name__)
                if isinstance(e,ValueError): item['error_code']=str(e)[:100]
                if isinstance(e,HTTPError): item['http_status']=e.code
        report['samples'].append(item)
    report['status']='RESEARCH_PROBE_FINISHED'; return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args()
    report=probe(); path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
