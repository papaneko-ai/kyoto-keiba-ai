"""Offline JRA result/profile crosswalk. No network; never guesses permanent horse IDs."""
from collections import Counter
from hashlib import sha256
from datetime import datetime
from urllib.parse import urlsplit,parse_qs
from bs4 import BeautifulSoup
import json,re

def official(url):
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in ("www.jra.go.jp","jra.go.jp"):
        raise ValueError("official HTTPS JRA source required")
    return p

def crosswalk(result_html:bytes,*,result_url:str):
    official(result_url)
    if not 0<len(result_html)<=2000000:raise ValueError("invalid source size")
    s=BeautifulSoup(result_html.decode("cp932",errors="replace"),"html.parser")
    tables=[t for t in s.select("table") if all(t.select_one("th."+k) for k in ("horse","num","waku","place"))]
    if not tables:raise ValueError("missing result tables")
    records=[]; errors=[]
    for race,table in enumerate(tables,1):
        for row in table.select("tr"):
            td=row.select_one("td.horse")
            if td is None:continue
            a=td.select_one("a[href]")
            n=row.select_one("td.num"); w=row.select_one("td.waku img[alt]")
            if not (a and n and w):
                errors.append({"race":race,"reason":"missing_fields"});continue
            link=urlsplit(a.get("href",""));token=parse_qs(link.query).get("CNAME",[])
            m=re.search(r"枠([1-8])",w.get("alt",""))
            num=n.get_text(" ",strip=True)
            if link.path!="/JRADB/accessU.html" or len(token)!=1 or not m or not num.isascii() or not num.isdigit() or not 1<=int(num)<=18:
                errors.append({"race":race,"reason":"unverified_profile_or_number"});continue
            records.append({"race_number":race,"horse_number":int(num),"frame_number":int(m.group(1)),
                            "horse_name":a.get_text(" ",strip=True),"profile_navigation_token":token[0],
                            "permanent_jra_horse_id":None,"permanent_id_verified":False,
                            "source_type":"POST_RACE_RESULT"})
    counts=Counter(x["race_number"] for x in records)
    for race,count in counts.items():
        if len({x["horse_number"] for x in records if x["race_number"]==race})!=count:
            errors.append({"race":race,"reason":"duplicate_horse_number"})
    if len(set(x["profile_navigation_token"] for x in records))!=len(records):
        errors.append({"reason":"duplicate_profile_token"})
    return {"schema_version":"jra_crosswalk.v1","source_sha256":sha256(result_html).hexdigest(),
            "race_count":len(tables),"runner_row_count":len(records),
            "per_race_counts":[counts[i] for i in range(1,len(tables)+1)],
            "parse_errors":errors,"runners":records,
            "pre_race_entries_confirmed":False,"permanent_ids_verified":False,"prediction_ready":False}

def inspect_entry_snapshot(raw:bytes,*,source_url:str,fetched_at_utc:datetime|None=None,
                           first_race_start_utc:datetime|None=None):
    official(source_url)
    s=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    title=s.title.get_text(" ",strip=True) if s.title else ""
    if "開催選択" in title:status="MEETING_SELECTION_NOT_RACECARD"
    elif not s.select("table"):status="NO_RACECARD_TABLE"
    elif not any(t.select_one("td.horse") and t.select_one("td.num") for t in s.select("table")):
        status="NO_RUNNER_ROWS_VERIFIED"
    else:status="RACECARD_CANDIDATE_UNVERIFIED"
    time_valid=(isinstance(fetched_at_utc,datetime) and fetched_at_utc.tzinfo is not None and
                isinstance(first_race_start_utc,datetime) and first_race_start_utc.tzinfo is not None and
                fetched_at_utc<first_race_start_utc)
    return {"status":status,"title":title,"source_sha256":sha256(raw).hexdigest(),
            "timestamp_pre_start":bool(time_valid),"racecard_certified":False,"ready_for_prediction":False}

def reconcile_counts(result,independent_entry_counts=None):
    counts=result["per_race_counts"]
    if independent_entry_counts is None:
        return {"status":"MISSING_INDEPENDENT_RACECARD","counts":counts,"verified":False}
    delta=[i for i,n in enumerate(counts,1) if independent_entry_counts.get(i)!=n]
    return {"status":"COUNTS_DIFFER" if delta else "COUNTS_MATCH_NOT_CERTIFIED",
            "race_number_differences":delta,"verified":False,
            "reason":"cancellations and independent provenance not yet validated"}

def canonical_json(result):
    return json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
