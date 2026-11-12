"""Verify two real official historical result HTML sources against GitHub receipts.

Produces only POST-RACE outcome labels, not pre-race model features, prices or bets.
Does not call JRA, change Turso, or use the rejected legacy public app.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,zipfile
from pathlib import Path
from diagnostics.jra_historical_two_day_source_capture import KNOWN,parse_official_result_identity
from diagnostics.parse_jra_result_roster import extract_result_roster

class HistoricalImportRejected(ValueError):pass
FIELDS=("race_date","venue","race_number","horse_number","frame_number",
        "horse_name","placing","source_sha256","source_type")

def import_two_days(archive):
 if type(archive) is not bytes or not 0<len(archive)<=3_000_000:
  raise HistoricalImportRejected("archive_size_invalid")
 names={"summary.json","job_provenance.json"}
 for date,race,_ in KNOWN:
  prefix=date.replace("-","")+f"_kyoto_{race:02d}"
  names.update([prefix+".html",prefix+".json"])
 with zipfile.ZipFile(io.BytesIO(archive)) as z:
  if len(z.namelist())!=len(names) or set(z.namelist())!=names:
   raise HistoricalImportRejected("archive_member_identity_invalid")
  summary=json.loads(z.read("summary.json"))
  provenance=json.loads(z.read("job_provenance.json"))
  if summary.get("schema")!="kyoto_historical_two_day_source_capture.v1" or summary.get("official_html_requests")!=2:
   raise HistoricalImportRejected("source_summary_invalid")
  if provenance.get("run_id")!="43129613002" or provenance.get("scope")!="HISTORICAL_POST_RACE_STRUCTURE_ONLY":
   raise HistoricalImportRejected("source_run_provenance_invalid")
  if type(summary.get("reports")) is not list or len(summary["reports"])!=2:
   raise HistoricalImportRejected("source_reports_incomplete")
  rows=[];races=[]
  for ix,(date,race,url) in enumerate(KNOWN):
   prefix=date.replace("-","")+f"_kyoto_{race:02d}"
   raw=z.read(prefix+".html")
   identity=parse_official_result_identity(raw,date,race,url)
   for r in (json.loads(z.read(prefix+".json")),summary["reports"][ix]):
    for key in ("date","race","venue","bytes","source_sha256","source_url"):
     expected=url if key=="source_url" else identity.get(key)
     if r.get(key)!=expected:
      raise HistoricalImportRejected("receipt_mismatch:"+key)
    if r.get("official_prerace_odds") is not False or r.get("training_ready") is not False:
     raise HistoricalImportRejected("invalid_historical_scope")
   parsed=extract_result_roster(raw,url)
   if parsed["race_count"]!=1 or parsed["parse_errors"] or parsed["horse_rows"]<2:
    raise HistoricalImportRejected("roster_parser_failed")
   seen=set();top_one=0;top_two=0
   for horse in parsed["races"][0]["rows"]:
    num=horse["horse_number"]
    if not 1<=num<=18 or num in seen:
     raise HistoricalImportRejected("horse_number_conflict")
    seen.add(num)
    if horse["placing"]=="1":top_one+=1
    if horse["placing"]=="2":top_two+=1
    rows.append({"race_date":date,"venue":"京都","race_number":race,
                 "horse_number":num,"frame_number":horse["frame_number"],
                 "horse_name":horse["horse_name"],"placing":horse["placing"],
                 "source_sha256":identity["source_sha256"],
                 "source_type":"HISTORICAL_POST_RACE_RESULT"})
   if top_one!=1 or top_two!=1:
    raise HistoricalImportRejected("top_two_not_unique_adjudication_required")
   winner=next(x["horse_number"] for x in rows if x["race_date"]==date and x["placing"]=="1")
   races.append({"date":date,"race_number":race,"runner_rows":len(seen),
                 "winner_horse_number":winner,"source_sha256":identity["source_sha256"]})
 output=io.StringIO(newline="")
 writer=csv.DictWriter(output,fieldnames=FIELDS,lineterminator="\n")
 writer.writeheader();writer.writerows(rows)
 blob=output.getvalue().encode("utf-8")
 receipt={"schema":"kyoto_two_new_official_historical_races_normalized.v1",
   "source_artifact_run_id":43129613002,"source_artifact_id":13904353071,
   "source_artifact_zip_sha256":hashlib.sha256(archive).hexdigest(),
   "csv_sha256":hashlib.sha256(blob).hexdigest(),
   "race_count":len(races),"new_meeting_dates":len(races),"runner_rows":len(rows),"races":races,
   "original_source_html_verified":True,"new_network_requests":0,
   "source_scope":"HISTORICAL_POST_RACE_LABELS_ONLY",
   "pre_race_features_verified":False,"payouts_verified":False,
   "pre_race_odds_verified":False,"training_ready":False,"paper_trading_ready":False}
 return blob,receipt

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--archive",required=True,type=Path)
 p.add_argument("--out",required=True,type=Path)
 args=p.parse_args()
 b,receipt=import_two_days(args.archive.read_bytes())
 args.out.mkdir(parents=True,exist_ok=True)
 (args.out/"historical_outcomes.csv").write_bytes(b)
 (args.out/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(receipt,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
