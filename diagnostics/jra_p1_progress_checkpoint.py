"""Durable stage-P1 resume checkpoint from exact six source-verified parsed rows.

No JRA requests, no production writes and no false claim of permanent raw bytes.
"""
import argparse,hashlib,json
from pathlib import Path
from diagnostics.jra_pending_profile_plan import canonical
ROOT=Path("docs/diagnostics")
PLAN=ROOT/"JRA_PENDING_136_PROFILES_PLAN_20261106.json"
REPLAY=ROOT/"jra_p1_profile_batches_20261106/replayed_batch_01"
def checkpoint():
 plan=json.loads(PLAN.read_text(encoding="utf8"))
 receipt=json.loads((REPLAY/"replay_receipt.json").read_text(encoding="utf8"))
 first=plan["batches"][0]
 if first["batch_id"]!="batch_01" or receipt["batch_id"]!="batch_01":
  raise ValueError("first_batch_identity_mismatch")
 if receipt["verified_profiles"]!=6 or receipt["new_network_requests"]!=0 or len(receipt["items"])!=6:
  raise ValueError("replay_not_independently_verified")
 if receipt["prediction_ready"] or receipt["training_ready"]:
  raise ValueError("unauthorized_model_release")
 for a,b in zip(first["items"],receipt["items"]):
  if (a["race_number"],a["horse_number"],a["horse_name"]) != (b["race"],b["horse_number"],b["horse_name"]):
   raise ValueError("wrong_replayed_horse")
  p=REPLAY/f"race_{b['race']:02d}_horse_{b['horse_number']:02d}_form.json"
  parsed=json.loads(p.read_text(encoding="utf8"))
  if parsed["source_sha256"]!=b["source_sha256"] or len(parsed["prior_rows"])!=b["prior_rows"]:
   raise ValueError("structured_profile_disagrees_with_replay")
 completed={(x["race"],x["horse_number"]) for x in receipt["items"]}
 pending=[x for b in plan["batches"][1:] for x in b["items"]]
 if len(pending)!=130 or any((x["race_number"],x["horse_number"]) in completed for x in pending):
  raise ValueError("pending_queue_overlap")
 return {"schema_version":"jra_p1_checkpoint.v1",
  "race_date":"2026-11-07","original_plan_sha256":hashlib.sha256(PLAN.read_bytes()).hexdigest(),
  "batch01_replay_receipt_sha256":hashlib.sha256((REPLAY/"replay_receipt.json").read_bytes()).hexdigest(),
  "original_148_runner_count":148,
  "previous_verified_count":12,"independently_replayed_new_count":6,
  "total_profiles_structured":18,"remaining_unqueried":130,
  "observed_new_finished_runs":sum(x["prior_rows"] for x in receipt["items"]),
  "completed_batch_ids":["batch_01"],
  "pending_batch_ids":[b["batch_id"] for b in plan["batches"][1:]],
  "next_batch_id":"batch_02","pending_profiles_sha256":hashlib.sha256(canonical(pending)).hexdigest(),
  "next_batch_items":plan["batches"][1]["items"],
  "new_http_requests":0,"next_batch_automatically_authorized":False,
  "original_html_long_term_retention_verified":False,
  "all_history_ready":False,"training_ready":False,"prediction_ready":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
 x=checkpoint();target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(canonical(x));print(json.dumps({k:v for k,v in x.items() if k!="next_batch_items"},ensure_ascii=False))
if __name__=="__main__":main()
