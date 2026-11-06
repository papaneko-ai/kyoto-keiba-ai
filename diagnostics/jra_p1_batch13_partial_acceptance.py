"""Offline acceptance for three valid batch13 originals without retrying blocked fourth."""
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
import json,argparse
from diagnostics.jra_p1_batch12_acceptance import build as baseline_build
from diagnostics.jra_feature_coverage_148 import first_features
from diagnostics.jra_pending_profile_plan import canonical

ROOT=Path("docs/diagnostics")
FOLDER=ROOT/"jra_p1_profile_batches_20261106/replayed_batch_13_partial"
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def build():
    status,previous=baseline_build()
    if status["profile_details_source_verified"]!=84 or status["detailed_profiles_unqueried"]!=64 or status["total_finished_prior_rows"]!=282 or status["next_batch"]!="batch_13":
        raise ValueError("wrong_previous_checkpoint")
    proof_path=FOLDER/"replay_receipt.json"
    proof=read(proof_path)
    if proof["verified_profiles"]!=3 or proof["new_network_requests"]!=0 or proof["batch_state"]!="PARTIAL_SOURCE_REPLAYED_DO_NOT_REPEAT":
        raise ValueError("partial_replay_not_verified")
    rows={(r["race_number"],r["horse_number"]):dict(r) for r in previous}
    added=0
    for entry in proof["items"]:
        race,num=entry["race"],entry["horse_number"]
        if race!=7 or num not in (9,10,11):raise ValueError("unexpected_partial_race")
        target=rows[(race,num)]
        d=read(FOLDER/f"race_{race:02d}_horse_{num:02d}_form.json")
        if target["source_coverage"]["horse_profile"]!="NOT_QUERIED" or target["horse_name"]!=d["horse_name"] or d["source_sha256"]!=entry["source_sha256"] or len(d["prior_rows"])!=entry["prior_rows"]:
            raise ValueError("partial_identity_or_provenance_mismatch")
        stamp=datetime.fromisoformat(d["captured_at_utc"].replace("Z","+00:00"))
        if stamp.tzinfo is None or stamp.astimezone(timezone.utc)>=CUTOFF:raise ValueError("postcutoff")
        target["source_coverage"]["horse_profile"]="VERIFIED_SOURCE_ROWS" if d["prior_rows"] else "VERIFIED_EMPTY_HISTORY"
        target["profile_status"]=d["history_status"]
        target["profile_source_sha256"]=d["source_sha256"]
        target["profile_captured_at_utc"]=d["captured_at_utc"]
        target["profile_source_batch"]="batch_13_PARTIAL"
        target["nonfinish_event_count"]=len(d["nonfinish_rows"])
        target["performance_features"]=first_features(d["prior_rows"])
        added+=len(d["prior_rows"])
    r7=[r for r in rows.values() if r["race_number"]==7]
    if len(r7)!=11 or any(r["source_coverage"]["horse_profile"]=="NOT_QUERIED" for r in r7):raise ValueError("kyoto7_not_complete")
    if len(rows)!=148 or sum(r["source_coverage"]["horse_profile"]!="NOT_QUERIED" for r in rows.values())!=87:raise ValueError("wrong_total")
    if rows[(8,2)]["source_coverage"]["horse_profile"]!="NOT_QUERIED":raise ValueError("failed_source_must_remain_unverified")
    status.update(schema_version="jra_kyoto_p1_87_profiles_seven_complete_races_partial_batch13.v1",
        profile_details_source_verified=87,detailed_profiles_unqueried=61,
        total_finished_prior_rows=282+added,
        completed_races=[1,2,3,4,5,6,7],
        completed_race_runner_counts={"1":9,"2":15,"3":13,"4":15,"5":8,"6":11,"7":11},
        partial_batch={"batch_id":"batch_13","verified_originals":3,"attempted_official_http":4,
                       "failed_official_profiles":[{"race":8,"horse_number":2,"reason":"invalid_history_rows"}],
                       "unattempted_in_batch":[{"race":8,"horse_number":3},{"race":8,"horse_number":4}],
                       "independent_replay_sha256":sha256(proof_path.read_bytes()).hexdigest()},
        next_batch="batch_13_BLOCKED_AT_R8_HORSE2",next_batch_automatically_authorized=False,
        prediction_ready=False,training_ready=False,feature_complete=False)
    return status,[rows[k] for k in sorted(rows)]
def write(out):
    path=Path(out);path.mkdir(parents=True,exist_ok=True)
    status,rows=build()
    (path/"status.json").write_bytes(canonical(status))
    (path/"feature_rows_148.json").write_bytes(canonical(rows))
    return status
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    print(json.dumps(write(a.out),ensure_ascii=False))
