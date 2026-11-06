"""Bounded real JRA historical feature audit: one official first-horse profile per remaining race.
Excludes races already archived (1,5,11). Nine requests total; no retries.
"""
import json,time,hashlib
from pathlib import Path
from datetime import datetime,date,timezone
from urllib.parse import urlsplit,urljoin,parse_qs
from urllib.request import Request,urlopen
from diagnostics.jra_prior_form_offline import parse_horse_history
ROOT=Path("docs/diagnostics")
RACES=(2,3,4,6,7,8,9,10,12)
CUTOFF=datetime.fromisoformat("2026-11-07T00:00:00+00:00")
EVENT_DAY=date(2026,11,7)
def snap(n):
 if n==7:p=ROOT/"JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json"
 elif n in (1,6,12):p=ROOT/"multirace_20261106"/f"kyoto_{n:02d}_snapshot.json"
 else:p=ROOT/"remaining8_20261106"/f"kyoto_{n:02d}_snapshot.json"
 return json.loads(p.read_text(encoding="utf8"))
def one_shot(folder,opener=urlopen,clock=lambda:datetime.now(timezone.utc)):
 out=Path(folder);out.mkdir(parents=True,exist_ok=True);receipts=[]
 for idx,n in enumerate(RACES):
  if idx:time.sleep(2)
  d=snap(n);h=d["runners"][0]
  rec={"race":n,"number":h["horse_number"],"name":h["horse_name"],
       "state":"STARTED","request_attempted":False,"training_ready":False,
       "prediction_ready":False,"stable_id_verified":False}
  try:
   if clock()>=CUTOFF:raise ValueError("pre_race_source_cutoff_passed")
   href=h["horse_profile_href"]
   url=urljoin("https://jra.jp",href);u=urlsplit(url)
   if (u.scheme!="https" or u.hostname!="jra.jp" or
       u.path!="/JRADB/accessU.html" or
       len(parse_qs(u.query).get("CNAME",[]))!=1):
    raise ValueError("invalid_official_profile_url")
   req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},method="GET")
   rec["request_attempted"]=True
   with opener(req,timeout=20) as resp:
    raw=resp.read(1800001);status=resp.status;content_type=resp.headers.get("Content-Type","")
    final=urlsplit(resp.geturl())
   fetched=clock()
   if (status!=200 or not 0<len(raw)<=1800000 or "html" not in content_type.lower()
       or final.hostname not in ("jra.jp","www.jra.go.jp") or
       final.scheme!="https" or final.path!="/JRADB/accessU.html"):
    raise ValueError("invalid_profile_http_response")
   digest=hashlib.sha256(raw).hexdigest()
   (out/f"kyoto_{n:02d}_horse_01.html").write_bytes(raw)
   rec.update(source_sha256=digest,bytes=len(raw),source_url=url,
       captured_at_utc=fetched.isoformat(),http_status=status)
   parsed=parse_horse_history(raw,source_url=url,fetched_at_utc=fetched,
     prediction_cutoff_utc=CUTOFF,target_date=EVENT_DAY,
     expected_horse_name=h["horse_name"],
     allow_verified_no_history=(n==6 and len(h.get("past_race_dates",[]))==0))
   if parsed["invalid_rows"]:
    rec["state"]="PARTIALLY_PARSED_INVALID_ROWS"
   else:rec["state"]="PROFILE_PARSED"
   rec.update(prior_rows=parsed["prior_row_count"],invalid_rows=len(parsed["invalid_rows"]),
     nonfinish_rows=len(parsed.get("nonfinish_rows",[])),
     total_rows=parsed["history_rows_total"],
     no_history_table=parsed.get("profile_history_table_absent",False),
     pre_cutoff=parsed["profile_captured_before_cutoff"])
   (out/f"kyoto_{n:02d}_horse_01_form.json").write_text(
     json.dumps({"race":n,"number":h["horse_number"],"name":h["horse_name"],
       "source_sha256":digest,"captured_at_utc":fetched.isoformat(),
       "prior_rows":parsed["prior_rows"],"excluded_rows":parsed["excluded_rows"],
       "invalid_rows":parsed["invalid_rows"],
       "nonfinish_rows":parsed.get("nonfinish_rows",[]),
       "history_status":parsed.get("history_status"),
       "prediction_ready":False,"training_ready":False},
       ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  except Exception as exc:
   rec.update(state="BLOCKED",error=type(exc).__name__+":"+str(exc)[:190])
  receipts.append(rec)
 result={"schema":"jra_remaining_nine_real_horse_profiles.v1",
   "sample_races":list(RACES),"sources_requested":sum(r["request_attempted"] for r in receipts),
   "parsed":sum(r["state"]=="PROFILE_PARSED" for r in receipts),
   "partially_parsed":sum(r["state"]=="PARTIALLY_PARSED_INVALID_ROWS" for r in receipts),
   "receipts":receipts,"all_148_profiles_fetched":False,
   "prediction_ready":False,"training_ready":False}
 (out/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 return result
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
 print(json.dumps(one_shot(a.out),ensure_ascii=False))
