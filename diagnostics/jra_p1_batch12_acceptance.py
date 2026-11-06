"""P1 full Kyoto R1-R4 provenance-backed profile coverage acceptance.

Rebuilds from immutable prior 148-row baseline plus eight separately SHA-replayed
official source batches. Offline, no JRA requests, no model or production changes.
"""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import argparse,json
from diagnostics.jra_feature_coverage_148 import first_features
from diagnostics.jra_pending_profile_plan import canonical

ROOT=Path("docs/diagnostics")
BASE=ROOT/"jra_feature_coverage_20261106"
BATCH=ROOT/"jra_p1_profile_batches_20261106"
PLAN=ROOT/"JRA_PENDING_136_PROFILES_PLAN_20261106.json"
CUTOFF=datetime.fromisoformat("2026-11-07T00:00:00+00:00")
def read(path):return json.loads(Path(path).read_text(encoding="utf8"))
def build():
  base=read(BASE/"feature_rows_148.json")
  old=read(BASE/"feature_coverage.json")
  plan=read(PLAN)
  if len(base)!=148 or old["profile_sources_with_parsed_form"]!=12:
    raise ValueError("invalid_baseline")
  rows={(r["race_number"],r["horse_number"]):dict(r) for r in base}
  if len(rows)!=148:raise ValueError("duplicate_baseline")
  added=0;more_prior=0;receipt_hashes={}
  for ix in range(1,13):
    key=f"batch_{ix:02d}"
    manifest=plan["batches"][ix-1]
    if manifest["batch_id"]!=key:raise ValueError("batch_id_mismatch")
    receipt=read(BATCH/(key+"_receipt.json"))
    folder=BATCH/("replayed_"+key)
    proof_path=folder/"replay_receipt.json"
    proof=read(proof_path)
    if (receipt["state"]!="PARSED_ORIGINALS_TEMPORARY" or receipt["verified_count"]!=6
         or receipt["failed_count"]!=0 or proof["verified_profiles"]!=6
         or proof["batch_id"]!=key or proof["new_network_requests"]!=0):
      raise ValueError("unverified_batch")
    if receipt["batch_content_sha256"]!=manifest["batch_content_sha256"]:
      raise ValueError("unmatched_queue_receipt")
    receipt_hashes[key]=sha256(proof_path.read_bytes()).hexdigest()
    for source,actual in zip(manifest["items"],proof["items"]):
      race=source["race_number"];no=source["horse_number"]
      if (race,no)!=(actual["race"],actual["horse_number"]) or source["horse_name"]!=actual["horse_name"]:
        raise ValueError("mismatched_replayed_horse")
      b=rows[(race,no)]
      if b["source_coverage"]["horse_profile"]!="NOT_QUERIED":
        raise ValueError("already_verified_profile_would_be_overwritten")
      data=read(folder/f"race_{race:02d}_horse_{no:02d}_form.json")
      if (data["horse_name"]!=b["horse_name"]
          or data["source_sha256"]!=actual["source_sha256"]
          or len(data["prior_rows"])!=actual["prior_rows"]):
        raise ValueError("source_identity_or_result_mismatch")
      stamp=datetime.fromisoformat(data["captured_at_utc"].replace("Z","+00:00"))
      if stamp.tzinfo is None or stamp.astimezone(timezone.utc)>=CUTOFF:
        raise ValueError("post_cutoff_profile")
      if data["prior_rows"]:
        b["source_coverage"]["horse_profile"]="VERIFIED_SOURCE_ROWS"
      else:
        b["source_coverage"]["horse_profile"]="VERIFIED_EMPTY_HISTORY"
      b["profile_status"]=data["history_status"]
      b["profile_source_sha256"]=data["source_sha256"]
      b["profile_captured_at_utc"]=data["captured_at_utc"]
      b["profile_source_batch"]=key
      b["nonfinish_event_count"]=len(data["nonfinish_rows"])
      b["performance_features"]=first_features(data["prior_rows"])
      more_prior+=len(data["prior_rows"])
      added+=1
  verified=[x for x in rows.values() if x["source_coverage"]["horse_profile"]!="NOT_QUERIED"]
  if added!=72 or len(verified)!=84 or sum(x["source_coverage"]["horse_profile"]=="NOT_QUERIED" for x in rows.values())!=64:
    raise ValueError("unexpected_total_after_batches")
  for r in (1,2,3,4,5,6):
    race=[x for x in rows.values() if x["race_number"]==r]
    if not race or any(x["source_coverage"]["horse_profile"]=="NOT_QUERIED" for x in race):
      raise ValueError("race_not_fully_verified")
  summary={"schema_version":"jra_kyoto_p1_84_profiles_twelve_batches.v1",
    "date":"2026-11-07","race_count":12,"runner_count":148,
    "profile_details_source_verified":84,"detailed_profiles_unqueried":64,
    "new_profiles_verified_since_baseline":72,
    "finished_prior_rows_baseline":107,"finished_prior_rows_from_twelve_batches":more_prior,
    "total_finished_prior_rows":107+more_prior,
    "completed_races":[1,2,3,4,5,6],"completed_race_runner_counts":{"1":9,"2":15,"3":13,"4":15,"5":8,"6":11},
    "completed_batches":[f"batch_{i:02d}" for i in range(1,13)],
    "next_batch":"batch_13","next_batch_automatically_authorized":False,
    "source_replay_receipt_sha256":receipt_hashes,
    "permanent_html_archive_completed":False,"feature_complete":False,
    "prediction_ready":False,"training_ready":False,
    "unverified_groups":["race_conditions","jockey_trainer","track_weather",
       "market_odds","training_workouts","official_live_scratches"]}
  return summary,[rows[k] for k in sorted(rows)]
def write(out):
  p=Path(out);p.mkdir(parents=True,exist_ok=True)
  summary,rows=build()
  (p/"status.json").write_bytes(canonical(summary))
  (p/"feature_rows_148.json").write_bytes(canonical(rows))
  return summary
if __name__=="__main__":
  ap=argparse.ArgumentParser();ap.add_argument("--out",required=True);args=ap.parse_args()
  print(json.dumps(write(args.out),ensure_ascii=False,indent=2))
