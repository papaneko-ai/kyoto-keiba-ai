"""Read-only, independent SP saved-roster assessment. No requests or promotion.

A captured raw page is not a verified roster. Reuse the existing mobile parser,
then require exact observed navigation, SHA, UTC, page heading and head count.
Unrecognized headings remain unverified; no odds, cancellation or PC parity claim.
"""
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, parse_qs
from bs4 import BeautifulSoup
from diagnostics.jra_pc_sp_benchmark import sp_rows
from diagnostics.kyoto_weekend_postflight import check_originals
from diagnostics.kyoto_weekend_sp_discovery import observed_kyoto_race_candidates

DAYS=("20261128","20261129")

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def utc(value):
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.utcoffset()!=timedelta(0):raise ValueError('not_utc')
    return t

def exact_mobile_race(url,day,number):
    u=urlsplit(url)
    if u.scheme!='https' or u.netloc not in ('sp.jra.jp','app.jra.jp') or u.path!='/JRADB/accessD.html' or u.fragment:return False
    q=parse_qs(u.query,strict_parsing=True)
    return set(q)=={'CNAME'} and len(q['CNAME'])==1 and bool(re.fullmatch(r'sw01dde(?:01|10)08[0-9]{8}'+f'{number:02d}'+day+r'/[A-Za-z0-9]+',q['CNAME'][0],re.I))

def inspect_heading(raw,day,number):
    # Only a heading before the first table may establish the event identity.
    # Links and historical form elsewhere on the page are not heading evidence.
    try: text=raw.decode('utf8')
    except UnicodeDecodeError:text=raw.decode('cp932')
    soup=BeautifulSoup(text,'html.parser')
    first=soup.find('table')
    if first is None:raise ValueError('no_roster_table')
    candidates=[]
    for tag in soup.find_all(['h1','h2','h3','h4','caption']):
        if tag is first or first in tag.parents:continue
        if not any(t is tag for t in first.previous_elements):continue
        if tag.find('a'):continue
        heading=' '.join(tag.stripped_strings)
        datepat=rf'{day[:4]}\s*年\s*0?{int(day[4:6])}\s*月\s*0?{int(day[6:])}\s*日'
        if not re.search(datepat,heading) or '京都' not in heading or '出馬表' not in heading:continue
        races={int(x) for x in re.findall(r'(?<![0-9])(0?[1-9]|1[0-2])\s*(?:R|レース)(?![0-9])',heading,re.I)}
        counts={int(x) for x in re.findall(r'(?<![0-9])([0-9]{1,2})\s*頭(?![0-9])',heading)}
        if races=={number} and len(counts)==1:candidates.append(next(iter(counts)))
    if len(candidates)!=1 or not 2<=candidates[0]<=18:raise ValueError('heading_or_count_unverified')
    # The legacy SP parser consumes CP932. A UTF-8 original must be decoded
    # strictly before parsing; never let replacement characters certify a name.
    canonical=text.encode('cp932',errors='strict')
    if canonical.decode('cp932',errors='strict')!=text:raise ValueError('lossy_sp_encoding')
    rows=sp_rows(canonical)
    if len(rows)!=candidates[0]:raise ValueError('roster_count_mismatch')
    return rows

def inspect_observed_layout(raw,day,number):
    """Real split-title SP view: retain evidence, never infer missing denominator."""
    try: text=raw.decode('utf8')
    except UnicodeDecodeError:text=raw.decode('cp932')
    if text.encode('cp932').decode('cp932')!=text:raise ValueError('lossy_sp_encoding')
    soup=BeautifulSoup(text,'html.parser')
    table=soup.find('table')
    if table is None:raise ValueError('missing_roster_table')
    prior=lambda tag: any(e is tag for e in table.previous_elements)
    titles=[h for h in soup.select('h1') if prior(h) and not h.find('a') and '出馬表' in h.get_text(' ',strip=True)]
    subtitles=[h for h in soup.select('h2.subTitle') if prior(h) and not h.find('a')]
    race_titles=[h for h in soup.select('h3.titleBox') if prior(h) and not h.find('a')]
    if len(titles)!=1 or len(subtitles)!=1 or len(race_titles)!=1:raise ValueError('split_heading_ambiguous')
    subtitle=' '.join(subtitles[0].stripped_strings)
    datepat=rf'{day[:4]}\s*年\s*0?{int(day[4:6])}\s*月\s*0?{int(day[6:])}\s*日'
    dates=re.findall(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',subtitle)
    if len(dates)!=1 or not re.search(datepat,subtitle) or '京都' not in subtitle:raise ValueError('split_date_or_venue_mismatch')
    race_title=' '.join(race_titles[0].stripped_strings)
    races={int(x) for x in re.findall(r'(?<![0-9])(0?[1-9]|1[0-2])\s*(?:R|レース)(?![0-9])',race_title,re.I)}
    if races!={number}:raise ValueError('split_race_mismatch')
    rows=[];frame=None;seen=set();cancelled=0
    for tr in table.select('tr'):
        links=tr.select('a[href*="/JRADB/accessU.html"]');nums=tr.select('.uban')
        if not links and not nums:continue
        if len(links)!=1 or len(nums)!=1:raise ValueError('ambiguous_roster_row')
        f=tr.select_one('.wban')
        if f and f.get_text(strip=True):
            v=f.get_text(strip=True)
            if not v.isascii() or not v.isdigit() or not 1<=int(v)<=8:raise ValueError('frame_invalid')
            frame=int(v)
        if frame is None:raise ValueError('frame_missing')
        name=links[0].get_text(' ',strip=True);v=nums[0].get_text(' ',strip=True)
        if not name:raise ValueError('name_missing')
        if v=='取消':n=None;cancelled+=1
        elif v.isascii() and v.isdigit() and 1<=int(v)<=18:
            n=int(v)
            if n in seen:raise ValueError('duplicate_horse_number')
            seen.add(n)
        else:raise ValueError('number_invalid')
        rows.append((n,frame,name))
    if not 2<=len(rows)<=18 or not seen:raise ValueError('row_count_invalid')
    if len({(f,nm) for _,f,nm in rows})!=len(rows):raise ValueError('duplicate_row_identity')
    numbers=[n for n,_,_ in rows if n is not None]
    if numbers!=sorted(numbers) or any(n>len(rows) for n in numbers):raise ValueError('number_sequence_invalid')
    if not cancelled and numbers!=list(range(1,len(rows)+1)):raise ValueError('number_gap')
    return {'state':'SP_SPLIT_LAYOUT_PARTIAL' if cancelled else 'SP_SPLIT_LAYOUT_OBSERVED',
            'observed_row_count':len(rows),'numeric_row_count':len(numbers),'cancelled_number_unknown_count':cancelled,
            'declared_runner_count_verified':False,
            'roster_sha256':digest(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode())}

def assess(root,day):
    if day not in DAYS:raise ValueError('day')
    root=Path(root)
    return assess_checked(root,day,check_originals(root,day=day,channel='SP'))

def assess_checked(root,day,post):
    # Caller must supply the freshly recomputed postflight result, not a receipt.
    root=Path(root)
    if day not in DAYS or post.get('day')!=day or post.get('channel')!='SP':raise ValueError('postflight_identity')
    verified={x['filename']:x for x in post.get('source_rows',[])}
    anchors={str(n):{} for n in range(1,13)}
    discovery=root/'sp_discovery_receipt.json'
    if discovery.is_file() and not discovery.is_symlink() and discovery.stat().st_size<=1_500_000:
        doc=json.loads(discovery.read_text(encoding='utf8'))
        if doc.get('day')==day and doc.get('not_pc_derived') is True:
            for x in doc.get('attempts',[]):
                name=x.get('file')
                if name not in verified or not re.fullmatch(r'official_sp_discovery_[1-6]\.html',name):continue
                row=verified[name];raw=(root/name).read_bytes()
                if digest(raw)!=row['sha256'] or utc(row['captured_at_utc']).strftime('%Y%m%d')!=day:continue
                if not isinstance(x.get('url'),str):continue
                u=urlsplit(x['url'])
                if u.scheme!='https' or u.netloc not in ('sp.jra.jp','app.jra.jp') or u.fragment:continue
                for n,links in observed_kyoto_race_candidates(raw,x['url'],day).items():
                    for v in links:
                        if exact_mobile_race(v,day,int(n)):
                            stamp=utc(row['captured_at_utc'])
                            anchors[n][v]=min(stamp,anchors[n].get(v,stamp))
    results={}
    for n in range(1,13):
        key=str(n);r={'state':'NO_VERIFIED_RAW_RACECARD','runner_count':None};results[key]=r
        prefix=f'r{n:02d}_';name=prefix+'official_sp_racecard.html'
        if name not in verified or post.get('sp_race_integrity',{}).get(key,{}).get('state')!='DIGEST_UTC_CHECKED_ONLY':continue
        try:
            rp=root/(prefix+'sp_receipt.json')
            if rp.is_symlink() or not rp.is_file():raise ValueError('receipt')
            receipt=json.loads(rp.read_text(encoding='utf8'));url=receipt['observed_sp_source_url']
            if set(anchors[key])!={url} or not exact_mobile_race(url,day,n):raise ValueError('anchor_not_unique')
            raw=(root/name).read_bytes();meta=verified[name]
            if anchors[key][url]>utc(meta['captured_at_utc']):raise ValueError('anchor_after_racecard')
            if digest(raw)!=meta['sha256']:raise ValueError('sha')
            try:
                rows=inspect_heading(raw,day,n)
                r.update(state='SP_STRUCTURAL_ROSTER_OBSERVED',runner_count=len(rows),roster_sha256=digest(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()))
            except ValueError:
                r.update(inspect_observed_layout(raw,day,n))
            r.update(source_sha256=meta['sha256'],captured_at_utc=utc(meta['captured_at_utc']).isoformat())
        except (ValueError,KeyError,TypeError,OSError,AttributeError):r['state']='SP_CONTENT_OR_PROVENANCE_UNVERIFIED'
    count=sum(v['state']=='SP_STRUCTURAL_ROSTER_OBSERVED' for v in results.values())
    return {'schema':'kyoto_impl31_sp_saved_roster_audit.v1','day':day,'races':results,'structural_roster_races':count,'all12_structural_rosters_observed':count==12,'split_layout_races':sum(v['state'] in ('SP_SPLIT_LAYOUT_OBSERVED','SP_SPLIT_LAYOUT_PARTIAL') for v in results.values()),'live_acquisition_certified':False,'market_verified':False,'cancelled_horses_verified':False,'prestart_certified':False,'network_requests':0}
