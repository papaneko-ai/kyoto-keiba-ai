"""Offline source-locked SP horse-history parser, no network or auto adoption."""
from bs4 import BeautifulSoup
from hashlib import sha256
from datetime import date
import re
DATE=re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+")
COURSE=re.compile(r"(障芝|障ダ|芝ダ|ダート|芝|ダ|障)(\d{3,4})")
FIELD=re.compile(r"(\d{1,2})頭")
FINISH=re.compile(r"^(\d+)着\s+(\d+)人気")
VENUES=("札幌","函館","福島","新潟","東京","中山","中京","京都","阪神","小倉")
LOCAL_VENUES=("園田","船橋","水沢","盛岡")
FINISH_WITHOUT_POPULARITY=re.compile(r"^(\d+)着(?:\s|$)")
def parse(raw,expected_horse):
    if not raw or len(raw)>1800000:raise ValueError("invalid_bytes")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    names=soup.select("div.bameiSection")
    if len(names)!=1 or not any(str(t).strip()==expected_horse for t in names[0].strings):
        raise ValueError("sp_profile_identity_anchor_missing_or_mismatch")
    table=next((t for t in soup.select("table") if "出走レース" in t.get_text(" ",strip=True)[:80]),None)
    if table is None:raise ValueError("sp_history_not_found")
    valid=[];nonfinish=[];invalid=[];administrative=[]
    rows=table.select("tr")[1:]
    for i,tr in enumerate(rows,1):
        cells=tr.find_all("td",recursive=False)
        if len(cells)!=2:
            invalid.append({"row":i,"reason":"sp_cell_count"});continue
        left,right=[x.get_text(" ",strip=True) for x in cells]
        d=DATE.match(left)
        event=re.fullmatch(r"\s*(JRAへ転入|JRAより転出)\s*",left[d.end():]) if d else None
        if event and not right.strip():
            try:
                event_date=date(*map(int,d.groups())).isoformat()
            except ValueError:
                invalid.append({"row":i,"reason":"sp_invalid_transfer_date"});continue
            administrative.append({"row":i,"date":event_date,
                "event_type":"JRA_TRANSFER_IN" if event.group(1)=="JRAへ転入" else "JRA_TRANSFER_OUT",
                "included_in_finish_metrics":False})
            continue
        c=COURSE.search(left)
        f=FIELD.search(left)
        venue=next((v for v in VENUES+LOCAL_VENUES if left[d.end():].startswith(v+" ")) ,None) if d else None
        if not d or not c or not f or not venue:
            invalid.append({"row":i,"reason":"sp_history_left_unparsed"});continue
        try:
            date_value=date(*map(int,d.groups())).isoformat()
        except ValueError:
            invalid.append({"row":i,"reason":"sp_invalid_date"});continue
        if right.startswith(("除","取消","中止","失格")):
            nonfinish.append({"row":i,"date":date_value,"status":right.split()[0]})
            continue
        finish=FINISH.match(right)
        if finish:
            rank,pop=map(int,finish.groups())
        else:
            missing=FINISH_WITHOUT_POPULARITY.match(right)
            if not missing or venue not in LOCAL_VENUES or "人気" in right:
                invalid.append({"row":i,"reason":"sp_finish_unparsed"});continue
            rank=int(missing.group(1));pop=None
        size=int(f.group(1))
        if size<2 or rank<1 or rank>size:
            invalid.append({"row":i,"reason":"sp_rank_out_of_range"});continue
        valid.append({"row":i,"date":date_value,"venue":venue,
            "surface":c.group(1),"distance_m":int(c.group(2)),
            "jurisdiction":"JRA" if venue in VENUES else "LOCAL",
            "field_size":size,"finish_position":rank,"popularity":pop,
            "popularity_missing":pop is None,
            "finish_percentile":(size-rank)/(size-1)})
    return {"horse_name":expected_horse,"source_sha256":sha256(raw).hexdigest(),
        "history_rows_total":len(rows),"prior_rows":valid,
        "nonfinish_rows":nonfinish,"invalid_rows":invalid,
        "administrative_events":administrative,
        "prediction_ready":False,"training_ready":False}
