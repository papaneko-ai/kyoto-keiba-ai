"""Discover odds navigation on two official 2026-11-07 Kyoto 11R racecards.

Only the source HTML's own links/actions are recorded; no synthesized odds
tokens, no market download and no implied odds availability.
"""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen, Request
from hashlib import sha256
from bs4 import BeautifulSoup
import argparse, json, re, time

SOURCES={
 "PC":"https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261107%2F13",
 "SP":"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261107%2FA0"
}
MAX=1_000_000
MARKETS=("オッズ","馬連","枠連","馬券")
UA_MOBILE="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"

def links(raw):
 soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
 result=[]
 for a in soup.select("a"):
  label=a.get_text(" ",strip=True)[:80]
  href=a.get("href","")
  onclick=a.get("onclick","")
  if any(x in label+" "+href+" "+onclick for x in MARKETS) or "accessO.html" in onclick or "accessO.html" in href:
   result.append({"label":label,"href":href[:250],"onclick":onclick[:300],
                  "mentions_official_odds_endpoint":"accessO.html" in href+" "+onclick})
 return {"html_title":soup.title.get_text(" ",strip=True) if soup.title else "",
         "relevant_anchor_count":len(result),"relevant_anchors":result[:70],
         "odds_endpoints_visible":sum(x["mentions_official_odds_endpoint"] for x in result)}

def run(folder):
 out=Path(folder);out.mkdir(parents=True,exist_ok=True)
 report={"schema_version":"jra_official_odds_nav.v1",
 "race":"2026-11-07-KYOTO-11R","sources":[],"market_odds_verified":False,
 "source_type":"source_racecard_navigation_only","training_ready":False}
 for i,(channel,url) in enumerate(SOURCES.items()):
  if i:time.sleep(1)
  result={"channel":channel,"source":url,
      "captured_at_utc":datetime.now(timezone.utc).isoformat(),"status":"STARTED"}
  try:
   host="jra.jp" if channel=="PC" else "sp.jra.jp"
   with urlopen(Request(url,headers={"User-Agent":UA_MOBILE if channel=="SP" else "Mozilla/5.0",
                      "Accept":"text/html"},method="GET"),timeout=20) as response:
    raw=response.read(MAX+1)
    code=response.status;ctype=response.headers.get("Content-Type","")
    final=urlsplit(response.geturl())
   if (code!=200 or not 0<len(raw)<=MAX or "html" not in ctype.lower()
       or final.scheme!="https" or final.hostname not in
       (("jra.jp","www.jra.go.jp") if channel=="PC" else ("sp.jra.jp",))):
    raise ValueError("unexpected_official_html")
   inspection=links(raw)
   (out/f"race11_{channel.lower()}.html").write_bytes(raw)
   result.update(status="NAVIGATION_AUDITED",sha256=sha256(raw).hexdigest(),
     bytes=len(raw),http_status=code,**inspection)
  except Exception as exc:
   result.update(status="FAILED",error=type(exc).__name__+":"+str(exc)[:200])
  report["sources"].append(result)
 (out/"navigation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 return report

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--out",default="jra_odds_nav");a=p.parse_args()
 print(json.dumps({"sources":[{"channel":r["channel"],"status":r["status"],
  "odds_endpoints_visible":r.get("odds_endpoints_visible")} for r in run(a.out)["sources"]]},ensure_ascii=False))
