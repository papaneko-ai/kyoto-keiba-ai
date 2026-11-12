"""Historical JRA two-day one-shot diagnostic: never pre-race evidence.

Only 2 preverified URLs. No crawling, speculation, retries, DB writes or bets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler

LIMIT=2_000_000
KNOWN=(
 ("2026-10-25",10,"https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde1008202604091020261025%2F1F"),
 ("2026-11-08",11,"https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde1008202605021120261108%2FDE"),
)
class HistoricalRejected(ValueError):
 pass

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,msg,headers,newurl):
  raise HistoricalRejected("redirect_disallowed")

class Summary(HTMLParser):
 def __init__(self):
  super().__init__()
  self.words=[];self.tables=0;self.hidden=0;self.title=[];self.in_title=False
 def handle_starttag(self,tag,attrs):
  if tag=="table":self.tables+=1
  if tag in ("script","style"):self.hidden+=1
  if tag=="title":self.in_title=True
 def handle_endtag(self,tag):
  if tag in ("script","style"):self.hidden=max(0,self.hidden-1)
  if tag=="title":self.in_title=False
 def handle_data(self,data):
  if self.in_title:self.title.append(data)
  if not self.hidden:self.words.append(data)

def validate_identity(date,race,url):
 if type(date) is not str or type(race) is not int or type(url) is not str or (date,race,url) not in KNOWN:
  raise HistoricalRejected("not_explicitly_verified_official_url")
 u=urlsplit(url)
 if (u.scheme!="https" or u.netloc!="www.jra.go.jp" or
     u.path!="/JRADB/accessS.html" or u.fragment or
     len(parse_qs(u.query).get("CNAME",[]))!=1):
  raise HistoricalRejected("invalid_url")
 return True

def parse_official_result_identity(raw,date,race,url):
 validate_identity(date,race,url)
 if type(raw) is not bytes or not 0<len(raw)<=LIMIT:
  raise HistoricalRejected("source_bytes_invalid")
 p=Summary()
 p.feed(raw.decode("cp932",errors="replace"))
 body=re.sub(r"\\s+","","".join(p.words))
 year,month,day=map(int,date.split("-"))
 if f"{year}年{month}月{day}日" not in body:
  raise HistoricalRejected("wrong_date")
 if "京都" not in body or not re.search(rf"(?<!\\d){race}(?:レース|R)",body):
  raise HistoricalRejected("wrong_venue_or_race")
 if "レース結果" not in body or "着順" not in body or p.tables<1:
  raise HistoricalRejected("not_race_result_table")
 return dict(date=date,race=race,venue="KYOTO",source_sha256=hashlib.sha256(raw).hexdigest(),
  bytes=len(raw),tables=p.tables,title="".join(p.title).strip()[:140],
  post_race_result_identity_verified=True,runner_rows_parsed=False,payout_parsed=False,
  official_prerace_odds=False,training_ready=False,real_paper_trade_ready=False,
  evidence_scope="POST_RACE_RESULT_ONLY_NOT_A_PRERACE_SNAPSHOT")

def capture_one(date,race,url,directory,*,opener=None,clock=None):
 validate_identity(date,race,url)
 opener=opener or build_opener(NoRedirect())
 clock=clock or (lambda:datetime.now(timezone.utc))
 request=Request(url,headers={"User-Agent":"KyotoRaceAI-Research/0.1","Accept":"text/html"},method="GET")
 with opener.open(request,timeout=15) as response:
  if response.getcode()!=200 or response.geturl()!=url:
   raise HistoricalRejected("http_status_or_redirect")
  if "html" not in response.headers.get("Content-Type","").lower():
   raise HistoricalRejected("not_html")
  raw=response.read(LIMIT+1)
 report=parse_official_result_identity(raw,date,race,url)
 now=clock()
 if not isinstance(now,datetime) or now.tzinfo is None:
  raise HistoricalRejected("clock_without_timezone")
 report.update(source_url=url,fetched_at_utc=now.astimezone(timezone.utc).isoformat())
 folder=Path(directory);folder.mkdir(parents=True,exist_ok=True)
 slug=date.replace("-","")+f"_kyoto_{race:02d}"
 html_path=folder/(slug+".html")
 receipt=folder/(slug+".json")
 if html_path.exists() or receipt.exists():
  raise HistoricalRejected("capture_must_not_overwrite")
 html_path.write_bytes(raw)
 receipt.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\\n",encoding="utf-8")
 return report

def main():
 a=argparse.ArgumentParser()
 a.add_argument("--out",required=True,type=Path)
 args=a.parse_args()
 reports=[]
 for date,race,url in KNOWN:
  reports.append(capture_one(date,race,url,args.out))
 receipt={"schema":"kyoto_historical_two_day_source_capture.v1",
  "new_historical_days_confirmed":len({r["date"] for r in reports}),
  "official_html_requests":len(reports),"reports":reports,
  "prerace_evidence_verified":False,"training_ready":False}
 (args.out/"summary.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\\n",encoding="utf-8")
 print(json.dumps(receipt,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
