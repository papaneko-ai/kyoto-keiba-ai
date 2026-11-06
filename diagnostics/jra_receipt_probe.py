"""One official JRA GET with durable success/failure receipt; no retries."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit,parse_qs
from hashlib import sha256
from html.parser import HTMLParser
URL="https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604100120261031%2F52"
class Summary(HTMLParser):
 def __init__(self):super().__init__();self.title_mode=False;self.title='';self.tables=0
 def handle_starttag(self,tag,attrs):
  if tag=="title":self.title_mode=True
  if tag=="table":self.tables+=1
 def handle_endtag(self,tag):
  if tag=="title":self.title_mode=False
 def handle_data(self,data):
  if self.title_mode:self.title+=data
def run(out,opener=urlopen,clock=lambda:datetime.now(timezone.utc)):
 p=Path(out);p.mkdir(parents=True,exist_ok=True)
 r={"schema_version":"jra_get_receipt.v1","target_url":URL,
  "started_at_utc":clock().astimezone(timezone.utc).isoformat(),
  "completed_at_utc":None,"status":"STARTED","http_status":None,
  "html_saved":False,"html_sha256":None,"html_bytes":0,"html_tables":None,
  "error_type":None,"error_message":None,"historical_pre_race_proven":False,
  "full_roster_verified":False,"ready_for_training":False}
 try:
  u=urlsplit(URL)
  if u.scheme!="https" or u.hostname!="www.jra.go.jp" or u.path!="/JRADB/accessD.html" or len(parse_qs(u.query).get("CNAME",[]))!=1:raise ValueError("disallowed_url")
  req=Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},method="GET")
  with opener(req,timeout=15) as resp:
   r["http_status"]=getattr(resp,"status",200)
   final=urlsplit(resp.geturl())
   if final.hostname not in ("www.jra.go.jp","jra.go.jp") or final.scheme!="https":raise ValueError("unsafe_redirect")
   raw=resp.read(2_000_001)
   ct=resp.headers.get("Content-Type","")
  if r["http_status"]!=200:raise ValueError("bad_http_status")
  if not raw or len(raw)>2_000_000 or "html" not in ct.lower():raise ValueError("not_bounded_html")
  (p/"jra_response_unclassified.html").write_bytes(raw)
  r.update(html_saved=True,html_sha256=sha256(raw).hexdigest(),html_bytes=len(raw),content_type=ct,final_url=resp.geturl() if False else URL)
  r["head_sample_text"]=raw[:500].decode("cp932",errors="replace")
  summary=Summary();summary.feed(raw.decode("cp932",errors="replace"))
  if summary.tables==0 or not summary.title.strip():
   r.update(status="HTML_RECEIVED_NOT_RACECARD",html_title=summary.title.strip(),html_tables=summary.tables)
   return r
  r.update(status="CAPTURED_STRUCTURE_UNVERIFIED",html_saved=True,html_sha256=sha256(raw).hexdigest(),html_bytes=len(raw),html_tables=summary.tables,html_title=summary.title.strip())
  (p/"jra_racecard_response.html").write_bytes(raw)
 except Exception as exc:
  r.update(status="CAPTURE_FAILED",error_type=type(exc).__name__,error_message=str(exc)[:400])
 finally:
  r["completed_at_utc"]=clock().astimezone(timezone.utc).isoformat()
  (p/"receipt.json").write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 return r
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--out",default="jra_receipt_evidence");a=ap.parse_args()
 print(json.dumps(run(a.out),ensure_ascii=False,indent=2))
