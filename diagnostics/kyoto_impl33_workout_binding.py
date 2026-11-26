"""Bind a real workout source to a previously authenticated official roster.
Historical research only; never promote late pages to pre-race inputs.
"""
from datetime import date, datetime, timedelta
from hashlib import sha256
import json, re
from bs4 import BeautifulSoup
from diagnostics.kyoto_impl33_whitegreen_probe import inspect, tables, text, timing, FINAL, FINAL_SHORT, JST


def bind(raw, day, race, url, captured_utc, roster, start_utc, observed_urls=()):
    receipt=inspect(raw,day,race,url,captured_utc,observed_urls)
    if not isinstance(roster,dict) or not 2<=len(roster)<=18 or any(type(n) is not int or not 1<=n<=18 or not isinstance(v,str) or not v for n,v in roster.items()) or len(set(roster.values()))!=len(roster):
        raise ValueError('official_roster_identity')
    start=datetime.fromisoformat(start_utc.replace('Z','+00:00'))
    captured=datetime.fromisoformat(captured_utc.replace('Z','+00:00'))
    d=date.fromisoformat(f'{day[:4]}-{day[4:6]}-{day[6:]}')
    if start.utcoffset()!=timedelta(0) or start.astimezone(JST).date()!=d:
        raise ValueError('official_start_identity')
    if receipt['summary_kind']!='FINAL_NUMBERED':
        raise ValueError('numbered_roster_not_published')
    soup=BeautifulSoup(raw,'html.parser')
    rows=next(rows for _,header,rows in tables(soup) if header in (FINAL,FINAL_SHORT))
    source={int(row[1]):row[2] for row in rows}
    if source!=roster:
        raise ValueError('source_official_roster_mismatch')
    by_name={v:n for n,v in roster.items()}
    records={n:[] for n in roster}; seen=set(); malformed=0
    for node,header,rows in tables(soup):
        if header not in (('日','コース','本線','終い'),('日','コース','本線','終い','脚色')):continue
        h3=node.find_previous('h3'); h4=node.find_previous('h4')
        if h3 is None or h4 is None or text(h4)!='最終追い切りまでの21日間' or text(h3) not in by_name:
            malformed+=1;continue
        n=by_name[text(h3)]
        if n in seen:raise ValueError('ambiguous_horse_history')
        seen.add(n)
        keys=set()
        for row in rows:
            if len(row)!=len(header) or not re.fullmatch(r'\d{1,2}/\d{1,2}',row[0]):
                malformed+=1;continue
            month,dd=map(int,row[0].split('/')); possible=[]
            for year in (d.year-1,d.year):
                try:x=date(year,month,dd)
                except ValueError:continue
                if d-timedelta(days=31)<=x<d and x<=captured.astimezone(JST).date():possible.append(x)
            times=timing(*row[1:4])
            if len(possible)!=1 or times is None:malformed+=1;continue
            rec={'training_date':possible[0].isoformat(),**times}
            key=tuple(sorted(rec.items()))
            if key in keys:malformed+=1;continue
            keys.add(key);records[n].append(rec)
        records[n].sort(key=lambda r:(r['training_date'],r['course'],r['distance_m'],r['elapsed_s'],r['last_1f_s']))
    digest=sha256(json.dumps(records,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    valid=sum(bool(x) for x in records.values())
    return {**receipt,'official_roster_match':True,'independent_roster_verified':True,'horse_history_binding_verified':len(seen)==len(roster),'official_horses':len(roster),'history_horses_bound':len(seen),'horses_with_dated_workout':valid,'bound_dated_records':sum(map(len,records.values())),'unbound_or_invalid_rows':malformed,'normalized_digest':digest,'historical_only':captured>=start or receipt['result_section_present'],'prestart_candidate':captured<start and not receipt['result_section_present'],'production_coverage_authorized':False},records
