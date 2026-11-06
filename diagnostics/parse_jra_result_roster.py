"""Read-only extraction from previously captured JRA results HTML. Not a pre-race entry parser."""
from bs4 import BeautifulSoup
from urllib.parse import urljoin,urlsplit,parse_qs
from hashlib import sha256
import re,json
from pathlib import Path

ROOT="https://www.jra.go.jp"
def extract_result_roster(raw:bytes,source_url:str):
    url=urlsplit(source_url)
    if url.scheme!="https" or url.hostname not in ("www.jra.go.jp","jra.go.jp"):
        raise ValueError("official_source_required")
    if not raw or len(raw)>2000000:raise ValueError("invalid_source_size")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    tables=[t for t in soup.select("table") if all(t.select_one("th."+c) for c in ("horse","num","waku","place"))]
    if not tables:raise ValueError("no_official_result_tables")
    races=[];errors=[]
    for idx,table in enumerate(tables,1):
        rows=[]
        for tr in table.select("tr"):
            cell=tr.select_one("td.horse")
            if cell is None:continue
            a=cell.select_one("a[href]")
            num=tr.select_one("td.num");waku=tr.select_one("td.waku")
            place=tr.select_one("td.place")
            if not all((a,num,waku,place)):
                errors.append(f"race_{idx}:missing_fields");continue
            profile=urljoin(ROOT,a.get("href",""))
            u=urlsplit(profile)
            token=parse_qs(u.query).get("CNAME",[None])[0]
            image=waku.select_one("img[alt]")
            frame=re.search(r"枠([1-8])",image.get("alt","")) if image else None
            n=num.get_text(" ",strip=True)
            if u.hostname not in ("www.jra.go.jp","jra.go.jp") or u.path!="/JRADB/accessU.html" or not token or not frame or not n.isdigit():
                errors.append(f"race_{idx}:invalid_profile_or_number");continue
            rows.append({"race_number":idx,"horse_number":int(n),
                         "frame_number":int(frame.group(1)),
                         "horse_name":a.get_text(" ",strip=True),
                         "placing":place.get_text(" ",strip=True),
                         "profile_url":profile,"profile_action_token":token,
                         "jra_horse_id":None,"horse_id_status":"unverified"})
        if len({r["horse_number"] for r in rows})!=len(rows):
            errors.append(f"race_{idx}:duplicate_horse_number")
        races.append({"race_number":idx,"rows":rows,"row_count":len(rows)})
    return {"schema_version":"jra_result_roster.v1",
            "source_url":source_url,"source_sha256":sha256(raw).hexdigest(),
            "source_type":"POST_RACE_RESULT",
            "race_count":len(races),"horse_rows":sum(r["row_count"] for r in races),
            "profile_links":sum(len(r["rows"]) for r in races),
            "per_race_counts":[r["row_count"] for r in races],
            "parse_errors":errors,"races":races,
            "official_entry_counts_verified":False,
            "pre_race_roster_verified":False,
            "all_runner_histories_verified":False,
            "ready_for_prediction":False}

def verify_offline(path:Path,source_url:str):
    return extract_result_roster(path.read_bytes(),source_url)
