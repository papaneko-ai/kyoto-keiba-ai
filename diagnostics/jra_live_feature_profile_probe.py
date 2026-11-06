"""Bounded JRA runner profile feature-evidence probe: 3 official profile GETs only.
Use frozen official racecard links; do not synthesize horse ids.
"""
from datetime import datetime,timezone,date
from urllib.parse import urljoin,urlsplit,parse_qs
from urllib.request import Request,urlopen
from hashlib import sha256
from pathlib import Path
import json,time
from diagnostics.jra_prior_form_offline import parse_horse_history

ROOT=Path("docs/diagnostics")
SAMPLES=((1,1,ROOT/"multirace_20261106/kyoto_01_snapshot.json"),
         (5,1,ROOT/"remaining8_20261106/kyoto_05_snapshot.json"),
         (11,1,ROOT/"remaining8_20261106/kyoto_11_snapshot.json"))
SOURCE_CUTOFF=datetime.fromisoformat("2026-11-07T00:00:00+00:00")
DAY=date(2026,11,7)
USER_AGENT="Mozilla/5.0"
MAX=1800000

def probe(directory,opener=urlopen,clock=lambda:datetime.now(timezone.utc)):
 output=Path(directory);output.mkdir(parents=True,exist_ok=True)
 reports=[]
 for i,(race,horse_no,path) in enumerate(SAMPLES):
  if i:time.sleep(2)
  rec={"race_number":race,"horse_number":horse_no,"state":"STARTED",
       "checked_at_utc":clock().isoformat(),"prediction_ready":False,
       "training_ready":False,"permanent_horse_id_verified":False}
  try:
   frozen=json.loads(path.read_text(encoding="utf8"))
   if frozen["race_number"]!=race or frozen["race_date"]!="2026-11-07":
    raise ValueError("wrong_frozen_race")
   runner=next(x for x in frozen["runners"] if x["horse_number"]==horse_no)
   rec["horse_name"]=runner["horse_name"]
   href=runner["horse_profile_href"]
   url=urljoin("https://jra.jp",href)
   u=urlsplit(url)
   if (u.hostname!="jra.jp" or u.path!="/JRADB/accessU.html" or
       len(parse_qs(u.query).get("CNAME",[]))!=1):
    raise ValueError("official_profile_path_invalid")
   if clock()>=SOURCE_CUTOFF:raise ValueError("prerace_capture_cutoff_passed")
   request=Request(url,headers={"User-Agent":USER_AGENT,"Accept":"text/html"},method="GET")
   with opener(request,timeout=20) as response:
    raw=response.read(MAX+1)
    status=response.status
    final=urlsplit(response.geturl())
    content_type=response.headers.get("Content-Type","")
   captured=clock()
   if status!=200 or not 0<len(raw)<=MAX or "html" not in content_type.lower():
    raise ValueError("profile_http_invalid")
   if (final.hostname not in ("jra.jp","www.jra.go.jp") or final.scheme!="https" or
       final.path!="/JRADB/accessU.html"):
    raise ValueError("profile_redirect_untrusted")
   rawname=f"kyoto_{race:02d}_horse_{horse_no:02d}.html"
   (output/rawname).write_bytes(raw)
   rec.update(source_sha256=sha256(raw).hexdigest(),source_bytes=len(raw),
      captured_at_utc=captured.isoformat(),source_url=url,http_status=status)
   parsed=parse_horse_history(raw,source_url=url,
      fetched_at_utc=captured,prediction_cutoff_utc=SOURCE_CUTOFF,
      target_date=DAY,expected_horse_name=runner["horse_name"])
   rec.update(state="PROFILE_PARSED",history_rows_total=parsed["history_rows_total"],
      prior_row_count=parsed["prior_row_count"],
      invalid_row_count=len(parsed["invalid_rows"]),
      excluded_row_count=len(parsed["excluded_rows"]),
      history_fields=list(parsed["prior_rows"][0]) if parsed["prior_rows"] else [],
      profile_identity_verified=parsed["profile_horse_name"]==runner["horse_name"],
      pre_cutoff=parsed["profile_captured_before_cutoff"])
   summary={"race":race,"horse_number":horse_no,"horse_name":runner["horse_name"],
    "source_sha256":rec["source_sha256"],"source_bytes":len(raw),
    "captured_at_utc":rec["captured_at_utc"],
    "prior_rows":parsed["prior_rows"],"excluded_rows":parsed["excluded_rows"],
    "invalid_rows":parsed["invalid_rows"],"profile_identity_verified":rec["profile_identity_verified"],
    "prediction_ready":False,"training_ready":False,
    "jra_horse_id_verified":False}
   (output/f"kyoto_{race:02d}_horse_{horse_no:02d}_parsed.json").write_text(
      json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  except Exception as e:
   rec.update(state="FAILED",error=type(e).__name__+":"+str(e)[:220])
  reports.append(rec)
 report={"schema_version":"jra_real_profile_feature_probe.v1",
   "sample_races":[x[0] for x in SAMPLES],
   "captured_at_utc":clock().isoformat(),
   "profile_receipts":reports,
   "verified_profile_count":sum(x["state"]=="PROFILE_PARSED" for x in reports),
   "source_cutoff_utc":SOURCE_CUTOFF.isoformat(),
   "full_148_profile_coverage":False,"prediction_ready":False,"training_ready":False}
 (output/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 return report
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--out",default="profile_feature_probe");a=p.parse_args()
 result=probe(a.out)
 print(json.dumps({"verified_profile_count":result["verified_profile_count"],
    "receipts":result["profile_receipts"]},ensure_ascii=False))
