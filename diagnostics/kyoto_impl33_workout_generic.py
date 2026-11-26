"""Reusable discovery and canonical bridge for independently observed workout pages.
No network in this module. No final coverage from special registration alone.
"""
import json,re
from datetime import date,datetime,timedelta
from hashlib import sha256
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from diagnostics.kyoto_impl33_whitegreen_probe import HOST,JST,inspect,tables,text,timing,FINAL,FINAL_SHORT,PREVIEW
from diagnostics.kyoto_impl31_workout_intake import inspect_workouts

def discover(raw,day,index_url=HOST+'/keiba/'):
    if not re.fullmatch(r'20\d{6}',day):raise ValueError('day_identity')
    if urlsplit(index_url).netloc!=urlsplit(HOST).netloc:raise ValueError('index_origin')
    soup=BeautifulSoup(raw,'html.parser');out={}
    for a in soup.find_all('a',href=True):
        u=urljoin(index_url,a['href'])
        m=re.fullmatch(re.escape(HOST)+rf'/race/{day}-kyoto-(0[1-9]|1[0-2])/',u)
        if m:out[int(m[1])]=u
    return out

def candidate_links(raw,index_url,*,allowed_hosts,horse_names,race_name):
    """Only observed links; candidate relevance is not source verification."""
    if urlsplit(index_url).hostname not in allowed_hosts:raise ValueError('unapproved_index')
    soup=BeautifulSoup(raw,'html.parser');out=set()
    for a in soup.find_all('a',href=True):
        label=text(a);url=urljoin(index_url,a['href']);u=urlsplit(url)
        if u.scheme!='https' or u.hostname not in allowed_hosts or u.username or u.password or u.fragment:continue
        if '追い切り' not in label and '調教' not in label:continue
        if not (race_name and race_name in label or any(n in label for n in horse_names)):continue
        out.add(url)
    return sorted(out)

def parse_observed(raw,day,race,url,captured_utc,observed_urls):
    """Name-bound dated records. A preview never creates official horse numbers."""
    receipt=inspect(raw,day,race,url,captured_utc,observed_urls)
    d=date.fromisoformat(day[:4]+'-'+day[4:6]+'-'+day[6:])
    stamp=datetime.fromisoformat(captured_utc.replace('Z','+00:00'))
    soup=BeautifulSoup(raw,'html.parser')
    choices=[(h,r) for _,h,r in tables(soup) if h in (FINAL,FINAL_SHORT,PREVIEW)]
    h,rows=next(((h,r) for h,r in choices if h in (FINAL,FINAL_SHORT)),choices[0])
    final=h in (FINAL,FINAL_SHORT)
    names={r[2] if final else r[0]:int(r[1]) if final else None for r in rows}
    records={n:[] for n in names};seen=set();issues=[]
    for node,header,rows in tables(soup):
        if header not in (('日','コース','本線','終い'),('日','コース','本線','終い','脚色')):continue
        h3=node.find_previous('h3');h4=node.find_previous('h4')
        if h3 is None or h4 is None or text(h3) not in names:issues.append('unbound_table');continue
        # Preview uses a different heading from final race-day format.
        if text(h4) not in ('最終追い切りまでの21日間','1週前追い切りまでの21日間','1週前の追い切りまでの21日間','直近21日間','21日間の調教記録'):
            # The header/date/horse are verified, but the unfamiliar history
            # section is not silently treated as dated workouts.
            issues.append('unknown_history_heading');continue
        name=text(h3)
        if name in seen:issues.append('duplicate_horse_table');records[name]=[];continue
        seen.add(name);keys=set()
        for row in rows:
            if len(row)!=len(header) or not re.fullmatch(r'\d{1,2}/\d{1,2}',row[0]):issues.append('row_shape');continue
            mm,dd=map(int,row[0].split('/'));dates=[]
            for y in (d.year-1,d.year):
                try:dt=date(y,mm,dd)
                except ValueError:continue
                if d-timedelta(days=31)<=dt<d and dt<=stamp.astimezone(JST).date():dates.append(dt)
            value=timing(*row[1:4])
            if len(dates)!=1 or value is None:issues.append('partial_or_invalid');continue
            r={'training_date':dates[0].isoformat(),**value};k=tuple(sorted(r.items()))
            if k not in keys:records[name].append(r);keys.add(k)
        records[name].sort(key=lambda r:tuple(sorted(r.items())))
    return receipt,names,records,issues

def bridge(raw,day,race,url,captured_utc,observed_urls,roster,start_utc):
    """Validate official names separately; accept only prestart observations."""
    receipt,names,records,issues=parse_observed(raw,day,race,url,captured_utc,observed_urls)
    if not isinstance(roster,dict) or len(set(roster.values()))!=len(roster):raise ValueError('roster_identity')
    if receipt['result_section_present']:raise ValueError('result_section_present')
    if receipt['summary_kind']=='FINAL_NUMBERED' and any(names.get(v)!=n for n,v in roster.items() if v in names):raise ValueError('number_mismatch')
    # Preview may contain nonstarters; exclude them, don't assign fake numbers.
    # Existing intake schema v1 keeps the core clock fields. Preserve richer
    # fields in the separate encrypted normalized original; never conflate.
    fields=('training_date','course','distance_m','elapsed_s')
    canonical=json.dumps({'schema':'kyoto_workout_canonical.v1','source':'OTHER_AUTHORIZED','day':day,'venue':'08','race':race,'original_sha256':sha256(raw).hexdigest(),
        'horses':[{'number':n,'name':v,'workouts':[dict((k,r[k]) for k in fields) for r in records.get(v,[])]} for n,v in sorted(roster.items())]},sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    result=inspect_workouts(original=raw,canonical=canonical,expected_day=day,race_number=race,expected_roster=roster,verified_start_utc=start_utc,captured_utc=captured_utc,expected_original_sha256=sha256(raw).hexdigest(),expected_canonical_sha256=sha256(canonical).hexdigest())
    return result,canonical,{n:records.get(v,[]) for n,v in roster.items()},issues
