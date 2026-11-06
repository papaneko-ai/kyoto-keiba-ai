"""Accept only the independently replayed R8 horse2 from diagnosed source, no GET."""
import argparse,json
from pathlib import Path
from hashlib import sha256
from diagnostics.jra_feature_coverage_148 import first_features
from diagnostics.jra_pending_profile_plan import canonical
ROOT=Path("docs/diagnostics")
PREV=ROOT/"jra_p1_seven_races_partial_20261106"
PROOF=ROOT/"jra_p1_r8h02_diagnosis_20261106/replayed_fixed_parser"
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def build():
    s=read(PREV/"status.json")
    rows=read(PREV/"feature_rows_148.json")
    proof_path=PROOF/"replay_receipt.json"
    p=read(proof_path)
    d=read(PROOF/"race_08_horse_02_form.json")
    if (s["profile_details_source_verified"]!=87 or s["detailed_profiles_unqueried"]!=61
        or s["total_finished_prior_rows"]!=329 or s["next_batch"]!="batch_13_BLOCKED_AT_R8_HORSE2"
        or p["state"]!="REPLAYED_SHA_VALIDATED_TRANSFER_EVENTS" or p["new_network_requests"]!=0
        or p["prior_valid_finishes"]!=26 or len(p["administrative_events"])!=2 or
        p["source_sha256"]!=d["source_sha256"] or len(d["prior_rows"])!=26):
        raise ValueError("replay_or_checkpoint_not_authorized")
    found=[x for x in rows if x["race_number"]==8 and x["horse_number"]==2]
    if len(found)!=1 or len(rows)!=148 or found[0]["horse_name"]!="グラニットピーク" or found[0]["source_coverage"]["horse_profile"]!="NOT_QUERIED":
        raise ValueError("would_override_horse_identity_or_verified_data")
    b=found[0]
    b["source_coverage"]["horse_profile"]="VERIFIED_SOURCE_ROWS"
    b["profile_status"]=d["history_status"]
    b["profile_source_sha256"]=d["source_sha256"]
    b["profile_captured_at_utc"]=d["captured_at_utc"]
    b["profile_source_batch"]="batch_13_R8H02_DIAGNOSTIC_REPLAY_NOT_PREVIOUS_FAILED_HTTP"
    b["nonfinish_event_count"]=len(d["nonfinish_rows"])
    b["administrative_event_count"]=len(d["administrative_events"])
    b["performance_features"]=first_features(d["prior_rows"])
    if sum(x["source_coverage"]["horse_profile"]!="NOT_QUERIED" for x in rows)!=88:
        raise ValueError("total_verified_not_88")
    s.update(schema_version="jra_kyoto_p1_88_profiles_transfer_fix.v1",
             profile_details_source_verified=88,detailed_profiles_unqueried=60,
             new_profiles_verified_since_baseline=76,total_finished_prior_rows=355,
             next_batch="batch_13_REMAINING_R8_HORSES_3_4_NEED_NEW_PLAN",
             next_batch_automatically_authorized=False,
             batch13_transfer_bug_repaired={
                 "horse":"グラニットピーク","race":8,"horse_number":2,
                 "replay_sha256":sha256(proof_path.read_bytes()).hexdigest(),
                 "source_sha256":d["source_sha256"],
                 "origin":"new_one_shot_prerace_diagnostic_source_not_original_failed_http",
                 "valid_prior_finishes":26,"administrative_transfers":2,
                 "original_failed_request_restored":False,
                 "batch13_complete":False},
             prediction_ready=False,training_ready=False,feature_complete=False)
    return s,rows
def write(out):
    s,rows=build();p=Path(out);p.mkdir(parents=True,exist_ok=True)
    (p/"status.json").write_bytes(canonical(s))
    (p/"feature_rows_148.json").write_bytes(canonical(rows))
    return s
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--out",required=True);v=a.parse_args()
    print(json.dumps(write(v.out),ensure_ascii=False))
