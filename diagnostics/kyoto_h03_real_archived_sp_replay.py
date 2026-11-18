"""Historical-only independent SP 12R proof; never treats post-event pages as pre-race odds."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlsplit
import json,time
from diagnostics.jra_pc_sp_benchmark import sp_rows,frozen

DAY="20261107"
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def fetch(url):
    u=urlsplit(url)
    if (u.scheme!="https" or u.hostname!="sp.jra.jp" or
        u.path!="/JRADB/accessD.html" or not u.query.startswith("CNAME=")
        or DAY not in u.query or u.fragment):
        raise ValueError("unobserved_or_invalid_sp_source")
    request=Request(url,headers={"User-Agent":UA,"Accept":"text/html"},method="GET")
    with build_opener(NoRedirect()).open(request,timeout=18) as response:
        raw=response.read(1_000_001)
        actual=response.geturl()
        typ=response.headers.get("Content-Type","")
        if response.status!=200 or actual!=url or not 0<len(raw)<=1_000_000 or "html" not in typ.lower():
            raise ValueError("response_invalid_or_redirected")
    return raw

def run():
    nav=json.loads(Path("docs/diagnostics/JRA_SP_NAV_LINKS_20261106.json").read_text())
    links={int(k):v for k,v in nav["official_race_links"].items()}
    assert set(links)==set(range(1,13)) and len(set(links.values()))==12
    out=Path("h03_archived_sp_evidence");out.mkdir(exist_ok=False)
    records=[]
    for race in range(1,13):
        url=links[race]
        rec={"race":race,"url":url,"historical_day":DAY,
             "official_link_from_saved_sp_navigation_receipt":True,
             "prediction_ready":False,"historical_only":True}
        try:
            time.sleep(2)
            raw=fetch(url)
            rec.update(source_sha256=sha256(raw).hexdigest(),source_bytes=len(raw),
                captured_utc=datetime.now(timezone.utc).isoformat())
            (out/f"race_{race:02d}.html").write_bytes(raw)
            parsed=sp_rows(raw)
            baseline=frozen(race)["runners"]
            expected=tuple((x["horse_number"],x["frame_number"],x["horse_name"]) for x in baseline)
            rec.update(parsed_count=len(parsed),expected_count=len(expected),
                       individual_roster_match=parsed==expected,
                       observed_horse_numbers=[x[0] for x in parsed],
                       state="PARSED_MATCH" if parsed==expected else "PARSED_MISMATCH")
        except Exception as exc:
            rec.update(state="FAILED",error_class=type(exc).__name__,error_message=str(exc)[:160])
        records.append(rec)
        (out/"partial_receipts.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    passed=sum(r["state"]=="PARSED_MATCH" for r in records)
    result={"schema":"kyoto_h03_historical_sp_12r_real_fetch.v1","day":DAY,
      "matching_races":passed,"total_races":12,"complete_12r_roster_match":passed==12,
      "historical_only":True,"all_horses_profile_verified":False,
      "pre_race_source_proven":False,"h03_certified":False,"records":records}
    (out/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!="records"},ensure_ascii=False))
    return 0 if passed==12 else 2
if __name__=="__main__":
    raise SystemExit(run())
