"""Replay the saved GitHub Actions source artifact without additional JRA requests.
All source URLs/names/hashes/timestamps are validated against saved first-run receipts.
"""
import argparse, json
from pathlib import Path
from hashlib import sha256
from datetime import datetime,date,timezone
from diagnostics.jra_prior_form_offline import parse_horse_history

ROOT=Path("docs/diagnostics")
SOURCES={1:ROOT/"multirace_20261106"/"kyoto_01_snapshot.json",
         5:ROOT/"remaining8_20261106"/"kyoto_05_snapshot.json",
         11:ROOT/"remaining8_20261106"/"kyoto_11_snapshot.json"}
CUTOFF=datetime.fromisoformat("2026-11-07T00:00:00+00:00")

def replay(artifact,out):
    art=Path(artifact);dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    earlier=json.loads((ROOT/"jra_feature_profiles_20261106"/"report.json").read_text(encoding="utf8"))
    reports=[]
    for r in earlier["profile_receipts"]:
        race=r["race_number"];number=r["horse_number"]
        item={"race":race,"number":number,"name":r.get("horse_name"),"status":"BLOCKED",
              "original_source_sha256":r.get("source_sha256"),
              "prediction_ready":False,"training_ready":False}
        try:
            files=list(art.rglob(f"kyoto_{race:02d}_horse_{number:02d}.html"))
            if len(files)!=1:raise ValueError("source_artifact_missing_or_ambiguous")
            raw=files[0].read_bytes()
            if sha256(raw).hexdigest()!=r["source_sha256"] or len(raw)!=r["source_bytes"]:
                raise ValueError("original_artifact_hash_or_size_mismatch")
            frozen=json.loads(SOURCES[race].read_text(encoding="utf8"))
            horse=next(x for x in frozen["runners"] if x["horse_number"]==number)
            if horse["horse_name"]!=r["horse_name"]:
                raise ValueError("roster_identity_mismatch")
            captured=datetime.fromisoformat(r["captured_at_utc"].replace("Z","+00:00"))
            if captured>=CUTOFF:raise ValueError("late_horse_profile")
            parsed=parse_horse_history(raw,source_url=r["source_url"],
                fetched_at_utc=captured,prediction_cutoff_utc=CUTOFF,
                target_date=date(2026,11,7),expected_horse_name=horse["horse_name"])
            item.update(status="PARSED",prior_rows=parsed["prior_row_count"],
                total_rows=parsed["history_rows_total"],
                excluded_rows=len(parsed["excluded_rows"]),
                invalid_rows=len(parsed["invalid_rows"]),
                extracted_fields=list(parsed["prior_rows"][0].keys()) if parsed["prior_rows"] else [],
                profile_before_cutoff=parsed["profile_captured_before_cutoff"],
                empty_history_verified=(race==5 and parsed["prior_row_count"]==0))
            (dest/f"race_{race:02d}_horse_{number:02d}_form.json").write_text(
                json.dumps({"race":race,"horse_name":horse["horse_name"],
                 "source_sha256":r["source_sha256"],
                 "fetched_at_utc":r["captured_at_utc"],
                 "prior_rows":parsed["prior_rows"],"excluded_rows":parsed["excluded_rows"],
                 "invalid_rows":parsed["invalid_rows"],"prediction_ready":False,
                 "training_ready":False},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        except Exception as exc:
            item["reason"]=type(exc).__name__+":"+str(exc)[:220]
        reports.append(item)
    result={"schema":"real_three_horse_profile_replay.v1",
            "replayed_originals":len(reports),
            "parsed":sum(x["status"]=="PARSED" for x in reports),
            "items":reports,
            "full_148_coverage":False,"prediction_ready":False,"training_ready":False}
    (dest/"replay_report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    print(json.dumps(replay(a.artifact,a.out),ensure_ascii=False))
