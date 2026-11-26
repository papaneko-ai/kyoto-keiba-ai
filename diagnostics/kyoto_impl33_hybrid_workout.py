"""Field-level recovery of missing dated workouts, independent of the primary provider."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import re
from bs4 import BeautifulSoup
from diagnostics.kyoto_impl33_whitegreen_probe import text, tables, timing, JST
from datetime import datetime

COURSES={'京都芝':'KYOTO_TURF','京都ダート':'KYOTO_DIRT','栗東坂路':'RITTO_HILL','栗坂':'RITTO_HILL','栗東CW':'RITTO_CW','栗東W':'RITTO_CW','栗W':'RITTO_CW','美浦W':'MIHO_W','美W':'MIHO_W','美浦坂路':'MIHO_HILL','美坂':'MIHO_HILL'}

def normalized_course(value):
    value=re.sub(r'[（(][^）)]*[）)]','',value).strip()
    return COURSES.get(value)

def record(day, month, dd, course, f, total, last):
    d=date.fromisoformat(day)
    dates=[]
    for year in (d.year-1,d.year):
        try:t=date(year,int(month),int(dd))
        except ValueError:continue
        if d-timedelta(days=31)<=t<d:dates.append(t)
    if len(dates)!=1 or course not in COURSES.values() or f not in range(2,10):return None
    try:
        a,b=Decimal(total),Decimal(last)
        if not a.is_finite() or not b.is_finite() or not 0<b<a<=600:return None
    except (InvalidOperation,ValueError):return None
    return {'training_date':dates[0].isoformat(),'course':course,'distance_m':f*200,'elapsed_s':float(a),'last_1f_s':float(b)}

def section(soup,name):
    matches=[h for h in soup.find_all(re.compile(r'^h[2-6]$')) if text(h)==name]
    if len(matches)!=1:return []
    h=matches[0];level=int(h.name[1]);nodes=[]
    for n in h.find_all_next(['h2','h3','h4','h5','h6','p','table']):
        if n.name.startswith('h') and int(n.name[1])<=level:break
        nodes.append(n)
    return nodes

def parse_table(raw,name,day):
    soup=BeautifulSoup(raw,'html.parser'); nodes=section(soup,name)
    for i,n in enumerate(nodes):
        if n.name!='table':continue
        date_text=' '.join(text(v) for v in nodes[max(0,i-4):i] if v.name!='table')
        m=re.search(r'(\d{1,2})月(\d{1,2})日',date_text)
        if not m:continue
        rows=[[text(c) for c in tr.find_all(['th','td'],recursive=False)] for tr in n.find_all('tr')]
        if not rows:continue
        header=rows[0]
        if not all(k in header for k in ('時期','場所','1F')):continue
        for row in rows[1:]:
            if len(row)!=len(header) or row[header.index('時期')]!='最終追切':continue
            course=normalized_course(row[header.index('場所')])
            for f in range(9,1,-1):
                key=str(f)+'F'
                if key in header and re.fullmatch(r'\d+(?:\.\d+)?',row[header.index(key)]):
                    result=record(day,*m.groups(),course,f,row[header.index(key)],row[header.index('1F')])
                    if result:return result
    return None

def parse_turf_line(raw,name,day):
    # Public G1 training summary uses five cumulative values for this six-furlong
    # Kyoto turf layout (6F, 5F, 4F, 3F, 1F). Do not infer other course layouts.
    soup=BeautifulSoup(raw,'html.parser')
    for n in section(soup,name):
        if n.name!='p':continue
        m=re.fullmatch(r'(\d{1,2})/(\d{1,2})[（(][^）)]*[）)]\s+京都芝\s+(\d+\.\d+)[-－]\d+\.\d+[-－]\d+\.\d+[-－]\d+\.\d+[-－](\d+\.\d+)',text(n))
        if m:return record(day,m[1],m[2],'KYOTO_TURF',6,m[3],m[4])
    return None

def recover(primary, roster, observations):
    """Observations are already source/identity validated. Only fill missing horses.
    Two matching provider records required; conflicting records stay unresolved."""
    if set(primary)!=set(roster):raise ValueError('roster_keys')
    result={n:list(rows) for n,rows in primary.items()}; audit=[]
    for n in sorted(roster):
        if result[n]:continue
        candidates=observations.get(n,[])
        groups={}
        for c in candidates:
            k=tuple(sorted(c['record'].items()));groups.setdefault(k,set()).add(c['provider'])
        if len(groups)==1 and len(next(iter(groups.values())))>=2:
            k=next(iter(groups));result[n]=[dict(k)];audit.append({'number':n,'status':'CORROBORATED','sources':sorted(groups[k])})
        else:audit.append({'number':n,'status':'CONFLICT' if len(groups)>1 else 'UNRESOLVED','candidate_count':len(candidates)})
    return result,audit

def classify_rejected(raw,day,roster,captured_utc):
    """Reproduce original binding exclusion reasons without changing accepted rows."""
    soup=BeautifulSoup(raw,'html.parser'); d=date.fromisoformat(day);captured=datetime.fromisoformat(captured_utc.replace('Z','+00:00'))
    names=set(roster.values());issues=[];seen=set()
    for node,header,rows in tables(soup):
        if header not in (('日','コース','本線','終い'),('日','コース','本線','終い','脚色')):continue
        h3=node.find_previous('h3');h4=node.find_previous('h4')
        if h3 is None or h4 is None or text(h4)!='最終追い切りまでの21日間' or text(h3) not in names:
            issues.append({'reason':'UNBOUND_TABLE'});continue
        name=text(h3)
        if name in seen:raise ValueError('ambiguous_horse_history')
        seen.add(name);keys=set()
        for row in rows:
            reason=None
            if len(row)!=len(header) or not re.fullmatch(r'\d{1,2}/\d{1,2}',row[0]):reason='ROW_SHAPE_OR_DATE'
            else:
                month,dd=map(int,row[0].split('/'));possible=[]
                for year in (d.year-1,d.year):
                    try:x=date(year,month,dd)
                    except ValueError:continue
                    if d-timedelta(days=31)<=x<d and x<=captured.astimezone(JST).date():possible.append(x)
                times=timing(*row[1:4])
                if len(possible)!=1:reason='OUTSIDE_DATE_WINDOW'
                elif times is None:reason='NONNUMERIC_OR_UNSUPPORTED_COURSE'
                else:
                    k=tuple(sorted({'training_date':possible[0].isoformat(),**times}.items()))
                    if k in keys:reason='DUPLICATE_EXACT_RECORD'
                    keys.add(k)
            if reason:issues.append({'reason':reason,'horse_number':next(n for n,v in roster.items() if v==name),'row_sha256':__import__('hashlib').sha256(repr(row).encode()).hexdigest(),'course':row[1] if len(row)>1 else None,'main':row[2] if len(row)>2 else None,'last':row[3] if len(row)>3 else None})
    return issues
