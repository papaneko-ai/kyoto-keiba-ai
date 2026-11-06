"""Reparse 9 already captured JRA horse originals offline; no additional requests.
Preserves first-run report; materializes new revision rather than overwriting it.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,date,timezone
from hashlib import sha256
from diagnostics.jra_prior_form_offline import parse_horse_history
ROOT=Path("docs/diagnostics")
CUTOFF=datetime.fromisoformat("2026-11-07T00:00:00+00:00")
def replay(originals,output):
 root=Path(originals);out=Path(output);out.mkdir(parents=True,exist_ok=True)
 original_report=json.loads((ROOT/"jra_nine_profiles_20261106"/"report.json").read_text(encoding="utf8"))
 results=[]
 for r in original_report["receipts"]:
  n=r["race"];name=r["name"]
  result={"race":n,"horse_number":r["number"],"horse_name":name,
          "original_sha256":r.get("source_sha256"),"status":"BLOCKED",
          "prediction_ready":False,"training_ready":False}
  try:
   files=list(root.rglob(f"kyoto_{n:02d}_horse_01.html"))
   if len(files)!=1:raise ValueError("not_exactly_one_original")
   raw=files[0].read_bytes()
   if len(raw)!=r["bytes"] or sha256(raw).hexdigest()!=r["source_sha256"]:
    raise ValueError("original_source_hash_mismatch")
   fetched=datetime.fromisoformat(r["captured_at_utc"].replace("Z","+00:00"))
   if fetched>=CUTOFF:raise ValueError("profile_late")
   d=parse_horse_history(raw,source_url=r["source_url"],
      fetched_at_utc=fetched,prediction_cutoff_utc=CUTOFF,
      target_date=date(2026,11,7),expected_horse_name=name,
      allow_verified_no_history=n==6)
   if d["invalid_rows"]:raise ValueError("unresolved_invalid_rows")
   result.update(status="PARSED",prior_count=d["prior_row_count"],
      event_count=d["history_rows_total"],
      nonfinish_count=len(d.get("nonfinish_rows",[])),
      surface_types=sorted(set(x["surface"] for x in d["prior_rows"])),
      empty_history=d.get("profile_history_table_absent",False))
   (out/f"kyoto_{n:02d}_horse_01_form.json").write_text(
      json.dumps({"race":n,"number":r["number"],"name":name,
       "source_sha256":r["source_sha256"],"captured_at_utc":r["captured_at_utc"],
       "prior_rows":d["prior_rows"],"nonfinish_rows":d.get("nonfinish_rows",[]),
       "invalid_rows":d["invalid_rows"],"history_status":d.get("history_status"),
       "prediction_ready":False,"training_ready":False},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  except Exception as exc:
   result["error"]=type(exc).__name__+":"+str(exc)[:160]
  results.append(result)
 report={"schema":"nine_jra_profiles_reparsed_from_originals.v1",
      "original_run_id":42163450529,"reparsed":sum(x["status"]=="PARSED" for x in results),
      "items":results,"source_originals_newly_fetched":0,
      "prediction_ready":False,"training_ready":False}
 (out/"replay_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print(json.dumps(report,ensure_ascii=False))
 return report
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);a=p.parse_args()
 replay(a.artifact,a.out)
