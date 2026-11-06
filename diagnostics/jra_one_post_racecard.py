"""Single official historical JRA racecard POST using previously proven doAction request shape.
Bounded diagnostic only. Archive raw source privately in 3-day Artifact; public receipt only metadata.
"""
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from urllib.parse import urlencode,urlsplit
import json,argparse
URL="https://www.jra.go.jp/JRADB/accessD.html"
CNAME="pw01dde0108202604100120261031/52"
class Summary(HTMLParser):
 def __init__(self):super().__init__();self.title_mode=False;self.title="";self.tables=0;self.forms=0
 def handle_starttag(self,tag,attrs):
  if tag=="title":self.title_mode=True
  if tag=="table":self.tables+=1
  if tag=="form":self.forms+=1
 def handle_endtag(self,tag):
  if tag=="title":self.title_mode=False
 def handle_data(self,data):
  if self.title_mode:self.title+=data

def run(output,opener=urlopen,clock=lambda:datetime.now(timezone.utc)):
 folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
 receipt={"schema_version":"jra_racecard_post.v1","method":"POST","request_url":URL,
  "cname_sha256":sha256(CNAME.encode()).hexdigest(),"started_at_utc":clock().astimezone(timezone.utc).isoformat(),
  "status":"STARTED","http_status":None,"bytes":None,"sha256":None,
  "error_type":None,"error_message":None,"pre_race_snapshot":False,
  "whole_racecard_verified":False,"permanent_horse_ids_verified":False,
  "ready_for_training":False}
 try:
  data=urlencode({"cname":CNAME}).encode("ascii")
  req=Request(URL,data=data,headers={"User-Agent":"Mozilla/5.0",
   "Referer":"https://www.jra.go.jp/keiba/","Content-Type":"application/x-www-form-urlencoded",
   "Accept":"text/html,application/xhtml+xml"},method="POST")
  with opener(req,timeout=20) as response:
   status=getattr(response,"status",200)
   final=response.geturl()
   content_type=response.headers.get("Content-Type","")
   raw=response.read(1500001)
  receipt["http_status"]=status
  finalp=urlsplit(final)
  if finalp.scheme!="https" or finalp.hostname not in ("www.jra.go.jp","jra.go.jp"):raise ValueError("unexpected_redirect")
  if status!=200 or not raw or len(raw)>1500000 or "html" not in content_type.lower():raise ValueError("invalid_http_response")
  summary=Summary();summary.feed(raw.decode("cp932",errors="replace"))
  receipt.update(bytes=len(raw),sha256=sha256(raw).hexdigest(),title=summary.title.strip(),
    table_count=summary.tables,form_count=summary.forms,status="HTML_CAPTURED_UNCLASSIFIED")
  (folder/"jra_post_racecard_response.html").write_bytes(raw)
  if summary.tables>0 and "出馬表" in summary.title:
   receipt["status"]="RACECARD_CANDIDATE_NEEDS_ROW_AUDIT"
 except Exception as e:
  receipt.update(status="POST_FAILED",error_type=type(e).__name__,error_message=str(e)[:350])
 finally:
  receipt["finished_at_utc"]=clock().astimezone(timezone.utc).isoformat()
  (folder/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 return receipt

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--output",default="jra_post_probe");args=p.parse_args()
 print(json.dumps(run(args.output),ensure_ascii=False,indent=2))
