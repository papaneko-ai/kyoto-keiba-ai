"""Accept solely the six new SHA-verified source-first profiles, not the old failed HTTP."""
import argparse,json
from pathlib import Path
from hashlib import sha256
from diagnostics.jra_feature_coverage_148 import first_features
from diagnostics.jra_pending_profile_plan import canonical
ROOT=Path("docs/diagnostics")
BASE=ROOT/"jra_p1_batch13_reconciled_90_profiles_20261106"
PROOF=ROOT/"jra_p1_profile_batches_20261106/replayed_batch_14"
def load(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def build():
    status=load(BASE/"status.json")
    rows=load(BASE/"feature_rows_148.json")
    proof_path=PROOF/"replay_receipt.json"
    proof=load(proof_path)
    if (len(rows)!=148 or status["profile_details_source_verified"]!=90
        or status["detailed_profiles_unqueried"]!=58
        or status["total_finished_prior_rows"]!=414
        or status["next_batch"]!="batch_14"
        or proof["state"]!="SIX_ORIGINALS_REPLAYED" or proof["verified_count"]!=6
        or proof["network_requests"]!=0):
        raise ValueError("checkpoint_or_replay_mismatch")
    new_rows=0
    for x in proof["items"]:
        race,n=x["race"],x["horse_number"]
        if (race,n) not in ((8,5),(8,6),(8,7),(8,8),(8,9),(9,2)):raise ValueError("unexpected_source")
        d=load(PROOF/f"race_{race:02d}_horse_{n:02d}_form.json")
        matches=[row for row in rows if row["race_number"]==race and row["horse_number"]==n]
        if len(matches)!=1 or matches[0]["horse_name"]!=x["horse_name"] or d["horse_name"]!=x["horse_name"] or matches[0]["source_coverage"]["horse_profile"]!="NOT_QUERIED" or d["source_sha256"]!=x["source_sha256"] or len(d["prior_rows"])!=x["prior_rows"] or len(d["administrative_events"])!=x["administrative_events"]:
            raise ValueError("would_override_or_source_mismatch")
        row=matches[0]
        row["source_coverage"]["horse_profile"]="VERIFIED_SOURCE_ROWS" if d["prior_rows"] else "VERIFIED_EMPTY_HISTORY"
        row["profile_status"]=d["history_status"]
        row["profile_source_sha256"]=d["source_sha256"]
        row["profile_captured_at_utc"]=d["captured_at_utc"]
        row["profile_source_batch"]="batch_13_SOURCE_FIRST_REMAINDER"
        row["nonfinish_event_count"]=len(d["nonfinish_rows"])
        row["administrative_event_count"]=len(d["administrative_events"])
        row["performance_features"]=first_features(d["prior_rows"])
        new_rows+=len(d["prior_rows"])
    if sum(x["source_coverage"]["horse_profile"]!="NOT_QUERIED" for x in rows)!=96:
        raise ValueError("expected_96_profiles")
    for race in range(1,9):
        rs=[x for x in rows if x["race_number"]==race]
        if any(x["source_coverage"]["horse_profile"]=="NOT_QUERIED" for x in rs):
            raise ValueError("already_complete_race_regressed")
    status.update(schema_version="jra_kyoto_p1_96_profiles_eight_complete_races.v1",
        profile_details_source_verified=96,detailed_profiles_unqueried=52,
        new_profiles_verified_since_baseline=84,total_finished_prior_rows=414+new_rows,
        next_batch="batch_15",
        next_batch_automatically_authorized=False,
        completed_races=[1,2,3,4,5,6,7,8],
        completed_race_runner_counts={"1":9,"2":15,"3":13,"4":15,"5":8,"6":11,"7":11,"8":9},
        completed_batches=[f"batch_{i:02d}" for i in range(1,15)],
        batch14_replayed={"verified_count":6,"source_first":True,"new_network_retries":0,
            "independent_replay_sha256":sha256(proof_path.read_bytes()).hexdigest()},
        prediction_ready=False,training_ready=False,feature_complete=False)
    return status,rows
def write(path):
    status,rows=build();p=Path(path);p.mkdir(parents=True,exist_ok=True)
    (p/"status.json").write_bytes(canonical(status))
    (p/"feature_rows_148.json").write_bytes(canonical(rows))
    return status
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--out",required=True);x=a.parse_args()
    print(json.dumps(write(x.out),ensure_ascii=False))
