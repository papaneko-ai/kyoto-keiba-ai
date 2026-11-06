"""Three bounded official current JRA racecards: capture, normalize, keep timestamped receipts."""
import json,re,hashlib
from datetime import datetime,date,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup

DAY=date(2026,11,7)
SOURCES=(
 (1,"https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605010120261107%2FC1","2026-11-07T01:05:00+00:00"),
 (6,"https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605010620261107%2F4A","2026-11-07T03:55:00+00:00"),
 (12,"https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011220261107%2FC8","2026-11-07T07:25:00+00:00"))
DATES=re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
FRAMES=re.compile(r"枠\s*([1-8])|([1-8])\s*枠")
MAX=1500000
def clock():return datetime.now(timezone.utc).isoformat()
def parse(raw,race):
 soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
 text=soup.get_text(" ",strip=True)
 tables=[t for t in soup.select("table") if all(t.select_one("th."+x) for x in ("horse","num","waku"))]
 if len(tables)!=1:return [],["racecard_table_missing_or_ambiguous"]
 rows=[];errors=[]
 for index,tr in enumerate(tables[0].select("tr")):
  h=tr.select_one("td.horse");n=tr.select_one("td.num")
  if h is None and n is None:continue
  if h is None or n is None:errors.append("missing_row_fields");continue
  a=h.select_one('a[href*="/JRADB/accessU.html"]')
  num=n.get_text(" ",strip=True)
  if not num.isascii() or not num.isdigit() or a is None or not 1<=int(num)<=18:
   errors.append("invalid_horse_number_or_link");continue
  link=a.get("href","");name=a.get_text(" ",strip=True)
  if not link.startswith("/JRADB/accessU.html?CNAME=") or not name:
   errors.append("bad_horse_profile");continue
  frame=None;w=tr.select_one("td.waku")
  if w:
   for img in w.select("img[alt]"):
    m=FRAMES.search(img.get("alt",""))
    if m:frame=int(m.group(1) or m.group(2));break
  if frame is None:errors.append("frame_missing")
  prior=[]
  for td in tr.select("td.past"):
   m=DATES.search(td.get_text(" ",strip=True))
   if not m:continue
   try:d=date(*map(int,m.groups()))
   except ValueError:errors.append("bad_history_date");continue
   if d>=DAY:errors.append("history_future_or_same_day")
   else:prior.append(d.isoformat())
  rows.append({"horse_number":int(num),"frame_number":frame,"horse_name":name,
   "horse_profile_href":link,"past_race_dates":prior,
   "permanent_horse_id":None,"permanent_id_verified":False})
 nums=[r["horse_number"] for r in rows]
 if sorted(nums)!=list(range(1,len(rows)+1)):errors.append("non_contiguous_numbers")
 frames=[r["frame_number"] for r in rows]
 if any(x is None for x in frames) or frames!=sorted(x for x in frames if x is not None):errors.append("invalid_frames")
 if not re.search(r"2026年\s*11月\s*7日",text):errors.append("date_not_confirmed")
 if not re.search(r"(?<!\d)"+str(race)+r"\s*(?:レース|R)(?!\d)",text):errors.append("race_number_not_confirmed")
 if not rows:errors.append("no_runner_rows")
 return rows,errors

def capture(output,opener=urlopen,now=clock):
 root=Path(output);root.mkdir(parents=True,exist_ok=True)
 results=[]
 for race,url,start in SOURCES:
  stamp=now();rec={"race_number":race,"race_date":"2026-11-07","source_url":url,
   "started_at_utc":stamp,"status":"STARTED","error":None,"roster_verified":False,
   "ready_for_prediction":False,"ready_for_training":False}
  try:
   dt=datetime.fromisoformat(stamp.replace("Z","+00:00"))
   deadline=datetime.fromisoformat(start)
   if dt>=deadline:raise ValueError("race_already_started")
   p=urlsplit(url)
   if p.scheme!="https" or p.hostname!="jra.jp" or p.path!="/JRADB/accessD.html":
    raise ValueError("unverified_origin")
   request=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},method="GET")
   with opener(request,timeout=20) as resp:
    status=resp.status;final=resp.geturl();ct=resp.headers.get("Content-Type","")
    raw=resp.read(MAX+1)
   if status!=200 or not 0<len(raw)<=MAX or "html" not in ct.lower():
    raise ValueError("invalid_http_response")
   q=urlsplit(final)
   if q.scheme!="https" or q.hostname not in ("jra.jp","www.jra.go.jp","www.jra.jp","own.jra.jp"):
    raise ValueError("external_redirect")
   finished=now()
   if datetime.fromisoformat(finished.replace("Z","+00:00"))>=deadline:
    raise ValueError("response_after_start")
   digest=hashlib.sha256(raw).hexdigest()
   filename=f"kyoto_{race:02d}_source.html"
   (root/filename).write_bytes(raw)
   runners,errors=parse(raw,race)
   rec.update(status="ROSTER_VERIFIED" if not errors else "HTML_SAVED_ROSTER_BLOCKED",
     finished_at_utc=finished,http_status=status,source_sha256=digest,
     source_bytes=len(raw),raw_source_filename=filename,runner_count=len(runners),
     error_list=errors,roster_verified=not errors)
   snapshot={"schema_version":"jra_pre_race_multi_20261106.v1","race_date":"2026-11-07",
    "venue":"KYOTO","race_number":race,"captured_at_utc":finished,
    "source_sha256":digest,"source_bytes":len(raw),"runners":runners,
    "runner_count":len(runners),"prior_date_count":sum(len(r["past_race_dates"]) for r in runners),
    "parse_errors":errors,"roster_verified":not errors,
    "scratch_final_verification":False,"permanent_ids_verified":False,
    "odds_verified":False,"prediction_ready":False,"training_ready":False}
   (root/f"kyoto_{race:02d}_snapshot.json").write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  except Exception as exc:
   rec.update(status="FAILED",error=type(exc).__name__+":"+str(exc)[:200])
  (root/f"kyoto_{race:02d}_receipt.json").write_text(json.dumps(rec,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  results.append(rec)
 summary={"schema_version":"jra_multi_capture_report.v1","receipts":results,
  "verified_races":[r["race_number"] for r in results if r["roster_verified"]],
  "ready_for_training":False}
 (root/"report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 return summary

if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--out",default="jra_multirace_capture");a=p.parse_args()
 print(json.dumps(capture(a.out),ensure_ascii=False))
