"""Capture only 8 uncaptured 2026-11-07 Kyoto official racecards from verified live navigation."""
import json,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.parse import quote,urlsplit
from diagnostics.jra_multi_capture_20261106 import parse
MISSING=(2,3,4,5,8,9,10,11)
FIRST_START=datetime.fromisoformat("2026-11-07T01:05:00+00:00")
def urls_from_nav(nav):
 links={}
 prefix="/JRADB/accessD.html?CNAME=pw01dde010820260501"
 for item in nav.get("links",[]):
  href=item.get("href","")
  if not href.startswith(prefix):continue
  tail=href[len(prefix):]
  if len(tail)!=17 or not tail[:2].isdigit() or tail[2:10]!="20261107" or tail[10]!="/":continue
  n=int(tail[:2])
  if not 1<=n<=12:continue
  url="https://jra.jp"+prefix+quote(tail,safe="")
  if n in links and links[n]!=url:raise ValueError("conflicting_race_links")
  links[n]=url
 if set(links)!=set(range(1,13)):raise ValueError("incomplete_official_navigation")
 return links
def run(navfile,out):
 links=urls_from_nav(json.loads(Path(navfile).read_text(encoding="utf8")))
 root=Path(out);root.mkdir(parents=True,exist_ok=True);result=[]
 for idx,n in enumerate(MISSING):
  if idx:time.sleep(1)
  began=datetime.now(timezone.utc)
  rec={"race_number":n,"source_url":links[n],"started_at_utc":began.isoformat(),
       "status":"ATTEMPTED","ready_for_prediction":False,"ready_for_training":False}
  try:
   if began>=FIRST_START:raise ValueError("before_start_gate_closed")
   with urlopen(Request(links[n],headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},method="GET"),timeout=20) as resp:
    raw=resp.read(1500001);status=resp.status;final=urlsplit(resp.geturl())
    content_type=resp.headers.get("Content-Type","")
   ended=datetime.now(timezone.utc)
   if ended>=FIRST_START:raise ValueError("completed_after_first_race")
   if (status!=200 or not 0<len(raw)<=1500000 or "html" not in content_type.lower()
    or final.scheme!="https" or final.hostname not in ("jra.jp","www.jra.go.jp","www.jra.jp")):
    raise ValueError("not_official_bounded_html")
   digest=hashlib.sha256(raw).hexdigest()
   (root/f"kyoto_{n:02d}_raw.html").write_bytes(raw)
   runners,errors=parse(raw,n)
   snap={"schema_version":"jra_kyoto_remaining8.v1","race_date":"2026-11-07","race_number":n,
    "venue":"KYOTO","source_url":links[n],"fetched_at_utc":ended.isoformat(),
    "source_sha256":digest,"source_bytes":len(raw),
    "runners":runners,"runner_count":len(runners),
    "prior_date_count":sum(len(x["past_race_dates"]) for x in runners),
    "errors":errors,"roster_verified":not errors,
    "permanent_ids_verified":False,"scratch_verified":False,"odds_verified":False,
    "prediction_ready":False,"training_ready":False}
   (root/f"kyoto_{n:02d}_snapshot.json").write_text(json.dumps(snap,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
   rec.update(status="ROSTER_VERIFIED" if not errors else "ROSTER_BLOCKED",
    runner_count=len(runners),prior_date_count=snap["prior_date_count"],
    source_sha256=digest,source_bytes=len(raw),http_status=status,errors=errors,
    fetched_at_utc=ended.isoformat())
  except Exception as exc:
   rec.update(status="FAILED",error=type(exc).__name__+":"+str(exc)[:170])
  (root/f"kyoto_{n:02d}_receipt.json").write_text(json.dumps(rec,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  result.append(rec)
 report={"source":"verified JRA R7 official 12-race navigation","attempted":list(MISSING),
  "verified":[x["race_number"] for x in result if x["status"]=="ROSTER_VERIFIED"],
  "receipts":result,"ready_for_prediction":False,"ready_for_training":False}
 (root/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 return report
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--nav",required=True);p.add_argument("--out",default="jra_remaining_8");a=p.parse_args()
 print(json.dumps(run(a.nav,a.out),ensure_ascii=False))
