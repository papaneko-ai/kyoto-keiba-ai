"""Offline SP profile link discovery in archived official racecard HTML."""
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin,urlsplit
from hashlib import sha256
import json
ROOT="https://sp.jra.jp"
def extract(original):
    raw=Path(original).read_bytes()
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    links=[]
    for a in soup.select('a[href*="/JRADB/accessU.html"]'):
        href=a.get("href","")
        url=urljoin(ROOT,href)
        u=urlsplit(url)
        if u.scheme!="https" or u.hostname!="sp.jra.jp" or u.path!="/JRADB/accessU.html" or not u.query.startswith("CNAME="):
            continue
        name=a.get_text(" ",strip=True)
        if name:links.append({"horse_name":name,"url":url})
    return {"source_sha256":sha256(raw).hexdigest(),
            "source_bytes":len(raw),"links":links,
            "official_profile_links_found":len(links),
            "network_requests":0,
            "profile_html_verified":False}
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    data=extract(a.source);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"links_found":data["official_profile_links_found"],"source_sha256":data["source_sha256"]}))
