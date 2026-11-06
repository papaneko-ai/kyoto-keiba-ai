"""One bounded SP navigation discovery; do not guess mobile CNAME suffixes."""
import argparse,json,re
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit,parse_qs
from html.parser import HTMLParser
from hashlib import sha256
from datetime import datetime,timezone
from bs4 import BeautifulSoup
URL="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261107%2FA0"
def discover(raw):
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    found={}
    links=[]
    for a in soup.select("a[href]"):
        href=a.get("href","")
        if "/JRADB/accessD.html" not in href:continue
        u=urlsplit(href)
        token=parse_qs(u.query).get("CNAME",[])
        if len(token)!=1:continue
        cname=token[0]
        m=re.fullmatch(r"(sw01dde010820260501)(\d{2})(20261107)/([A-Za-z0-9]{2})",cname)
        if m:
            race=int(m.group(2))
            if not 1<=race<=12:continue
            prev=found.get(race)
            official="https://sp.jra.jp/JRADB/accessD.html?CNAME="+cname.replace("/","%2F")
            if prev is not None and prev!=official:raise ValueError("conflicting_mobile_link")
            found[race]=official
        links.append({"label":a.get_text(" ",strip=True)[:25],"cname_type":cname[:7],
                      "is_racecard":bool(m)})
    return {"schema":"sp_navigation_discovery_v1",
        "official_race_links":{str(k):v for k,v in sorted(found.items())},
        "link_count":len(links),"race_link_count":len(found),
        "full_12_race_links":len(found)==12,
        "prediction_ready":False,"training_ready":False}
def run(folder):
    p=Path(folder);p.mkdir(parents=True,exist_ok=True)
    receipt={"status":"STARTED","source":URL,"started_at_utc":datetime.now(timezone.utc).isoformat()}
    try:
        with urlopen(Request(URL,headers={"User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"},method="GET"),timeout=20) as resp:
            raw=resp.read(1000001);status=resp.status;ct=resp.headers.get("Content-Type","");host=urlsplit(resp.geturl()).hostname
        if status!=200 or not 0<len(raw)<=1000000 or host!="sp.jra.jp" or "html" not in ct.lower():
            raise ValueError("invalid_html_response")
        data=discover(raw)
        (p/"sp_source.html").write_bytes(raw)
        (p/"navigation.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        receipt.update(status="DISCOVERY_RECORDED",sha256=sha256(raw).hexdigest(),bytes=len(raw),
                       race_links=data["race_link_count"],complete=data["full_12_race_links"])
    except Exception as exc:
        receipt.update(status="DISCOVERY_FAILED",error=type(exc).__name__+":"+str(exc)[:180])
    finally:
        receipt["finished_at_utc"]=datetime.now(timezone.utc).isoformat()
        (p/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return receipt
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--out",default="sp_nav_probe");args=a.parse_args()
    print(json.dumps(run(args.out),ensure_ascii=False))
