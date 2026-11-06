"""One official *future* Kyoto racecard GET with origin-byte provenance.
No retries or background polling; file in short-lived GitHub Actions Artifact only.
"""
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from hashlib import sha256
from html.parser import HTMLParser
import argparse,json
URL="https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605010720261107%2FFF"
class Summary(HTMLParser):
 def __init__(self):
  super().__init__();self.title_mode=False;self.title="";self.tables=0;self.tr=0;self.anchors=0
 def handle_starttag(self,tag,attrs):
  if tag=="title":self.title_mode=True
  if tag=="table":self.tables+=1
  if tag=="tr":self.tr+=1
  if tag=="a":self.anchors+=1
 def handle_endtag(self,tag):
  if tag=="title":self.title_mode=False
 def handle_data(self,data):
  if self.title_mode:self.title+=data
def run(folder):
 dst=Path(folder);dst.mkdir(parents=True,exist_ok=True)
 now=datetime.now(timezone.utc).isoformat()
 result={"schema_version":"kyoto_fresh_prerace_probe.v1","source_url":URL,
  "date_of_race_jst":"2026-11-07","race_number":7,"fetched_at_utc":now,
  "status":"STARTED","http_status":None,"source_sha256":None,"source_bytes":None,
  "raw_html_path":None,"horse_rows_verified":False,"official_id_verified":False,
  "ready_for_prediction":False,"training_ready":False}
 try:
  p=urlsplit(URL)
  if p.hostname!="jra.jp" or p.scheme!="https":raise ValueError("source_not_verified")
  with urlopen(Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html,application/xhtml+xml"},method="GET"),timeout=20) as resp:
   status=resp.status;resp_url=resp.geturl();ctype=resp.headers.get("Content-Type","")
   raw=resp.read(1500001)
  result["http_status"]=status;final=urlsplit(resp_url)
  if final.scheme!="https" or final.hostname not in ("jra.jp","www.jra.go.jp","www.jra.jp","own.jra.jp","app.jra.jp","sp.jra.jp"):
   raise ValueError("untrusted_final_host")
  if status!=200 or not 0<len(raw)<=1500000 or "html" not in ctype.lower():
   raise ValueError("invalid_response")
  s=Summary();s.feed(raw.decode("cp932",errors="replace"))
  (dst/"future_kyoto_r7.html").write_bytes(raw)
  result.update(status="HTML_RECEIVED_NEEDS_ROSTER_AUDIT",source_sha256=sha256(raw).hexdigest(),
    source_bytes=len(raw),raw_html_path="future_kyoto_r7.html",
    html_title=s.title.strip(),html_tables=s.tables,html_rows=s.tr,
    response_url=resp_url,contains_kyoto="京都".encode("cp932") in raw)
  if s.tables>0 and s.tr>1 and "出馬表" in s.title:
   result["status"]="PRERACE_RACECARD_STRUCTURE_CANDIDATE"
 except Exception as err:
  result.update(status="CAPTURE_FAILED",error_type=type(err).__name__,error_message=str(err)[:350])
 finally:
  result["finished_at_utc"]=datetime.now(timezone.utc).isoformat()
  (dst/"receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 return result
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--out",default="jra_future_probe");a=p.parse_args()
 print(json.dumps(run(a.out),ensure_ascii=False,indent=2))
