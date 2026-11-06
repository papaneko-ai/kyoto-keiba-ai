"""Reproducible, zero-network intake queue for 136 unqueried Kyoto JRA horses.

It does not grant permission to fetch, certify official usage terms, or
convert current post-event profile pages into historical as-of evidence.
"""
from __future__ import annotations
import argparse,json,re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

ROOT=Path("docs/diagnostics/jra_feature_coverage_20261106")
EXPECTED_RACES=12
EXPECTED_RUNNERS=148
EXPECTED_ALREADY=12
EXPECTED_PENDING=136
BATCH_SIZE=6
class PlanningError(ValueError):pass

def canonical(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf8")

def trusted_url(href):
    if not isinstance(href,str) or not href.startswith("/JRADB/accessU.html?"):
        raise PlanningError("not_official_card_profile_path")
    url="https://jra.jp"+href
    u=urlsplit(url)
    if u.scheme!="https" or u.hostname!="jra.jp" or u.path!="/JRADB/accessU.html":
        raise PlanningError("untrusted_profile_origin")
    keys=parse_qs(u.query,keep_blank_values=True)
    if list(keys)!=(["CNAME"] if "CNAME" in keys else []) or len(keys.get("CNAME",[]))!=1:
        raise PlanningError("ambiguous_profile_token")
    token=keys["CNAME"][0]
    if not re.fullmatch(r"pw[0-9A-Za-z]+/[0-9A-Za-z]+",token):
        raise PlanningError("invalid_official_token")
    return url

def compile_plan(features,coverage):
    if len(features)!=EXPECTED_RUNNERS or coverage.get("runner_count")!=EXPECTED_RUNNERS:
        raise PlanningError("unexpected_card_total")
    if coverage.get("race_count")!=EXPECTED_RACES or coverage.get("profile_sources_queried")!=EXPECTED_ALREADY:
        raise PlanningError("unexpected_previous_coverage")
    seen=set()
    known=[];pending=[];per_race=Counter()
    for row in sorted(features,key=lambda x:(x["race_number"],x["horse_number"])):
        race=row.get("race_number");number=row.get("horse_number")
        if type(race) is not int or type(number) is not int or not 1<=race<=12 or not 1<=number<=18:
            raise PlanningError("invalid_runner_identity")
        key=(race,number)
        if key in seen:raise PlanningError("duplicate_runner")
        seen.add(key);per_race[race]+=1
        expected_id=f"2026-11-07_KYOTO_{race:02d}R"
        if row.get("race")!=expected_id:raise PlanningError("race_identity_mismatch")
        hash_value=row.get("racecard_source_sha256")
        if not isinstance(hash_value,str) or not re.fullmatch(r"[0-9a-f]{64}",hash_value):
            raise PlanningError("unproven_racecard_original")
        if row.get("prediction_ready") is not False or row.get("training_ready") is not False:
            raise PlanningError("misrepresented_model_release")
        url=trusted_url(row.get("profile_href"))
        status=row.get("source_coverage",{}).get("horse_profile")
        entry={"race_id":expected_id,"race_number":race,"horse_number":number,
               "horse_name":row["horse_name"],"profile_url":url,
               "racecard_sha256":hash_value,
               "requested_source":"JRA_OFFICIAL_PC",
               "snapshot_asof_verified":False,
               "future_training_allowed":False}
        if status=="NOT_QUERIED":
            if row.get("performance_features") is not None or row.get("profile_status")!="NOT_QUERIED":
                raise PlanningError("pending_runner_contains_fake_history")
            pending.append(entry)
        elif status in ("VERIFIED_SOURCE_ROWS","VERIFIED_EMPTY_HISTORY"):
            if "profile_source_sha256" not in row:raise PlanningError("verified_record_without_original")
            known.append(key)
        else:raise PlanningError("unrecognized_profile_status")
    if len(seen)!=EXPECTED_RUNNERS or set(per_race)!=set(range(1,13)):
        raise PlanningError("missing_race_or_horse")
    if len(known)!=EXPECTED_ALREADY or len(pending)!=EXPECTED_PENDING:
        raise PlanningError("pending_or_completed_count_mismatch")
    batches=[]
    for start in range(0,len(pending),BATCH_SIZE):
        subset=pending[start:start+BATCH_SIZE]
        batch_id=f"batch_{start//BATCH_SIZE+1:02d}"
        batches.append({"batch_id":batch_id,"items":subset,
                        "batch_content_sha256":sha256(canonical(subset)).hexdigest(),
                        "state":"PLANNED_NOT_FETCHED",
                        "request_count":len(subset)})
    if sum(x["request_count"] for x in batches)!=EXPECTED_PENDING:
        raise PlanningError("batch_partition_error")
    return {"schema_version":"jra_kyoto_pending_profiles.v1",
        "race_date":"2026-11-07","racecourse":"KYOTO",
        "frozen_runners":EXPECTED_RUNNERS,"already_verified":len(known),
        "pending_profiles":len(pending),"batch_size":BATCH_SIZE,
        "batch_count":len(batches),"batches":batches,
        "planning_sha256":sha256(canonical(pending)).hexdigest(),
        "extraction_authorized":False,
        "historical_asof_reconstruction_authorized":False,
        "production_writes_authorized":False,
        "prediction_ready":False,"training_ready":False,
        "next_step":"Review official use conditions and durable source retention before any live batch."}

def resume_candidates(plan,receipts):
    if not isinstance(receipts,dict):raise PlanningError("receipts_must_be_dictionary")
    catalog={x["batch_id"]:x for x in plan["batches"]}
    unexpected=set(receipts)-set(catalog)
    if unexpected:raise PlanningError("unexpected_batch_receipts")
    outstanding=[];completed=[]
    for batch_id,b in catalog.items():
        item=receipts.get(batch_id)
        if item is None:
            outstanding.append(batch_id);continue
        if item.get("batch_content_sha256")!=b["batch_content_sha256"]:
            raise PlanningError("receipt_batch_hash_conflict")
        if item.get("state")=="COMPLETED_WITH_SOURCE_EVIDENCE":
            if item.get("verified_count")!=b["request_count"] or not item.get("sources_retained"):
                raise PlanningError("receipt_claim_not_proven")
            completed.append(batch_id)
        elif item.get("state") in ("BLOCKED","PARTIAL"):
            outstanding.append(batch_id)
        else:raise PlanningError("unknown_receipt_state")
    return {"completed":completed,"outstanding":outstanding,
            "do_not_retry_without_receipt_inspection":True}

def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    features=json.loads((ROOT/"feature_rows_148.json").read_text(encoding="utf8"))
    coverage=json.loads((ROOT/"feature_coverage.json").read_text(encoding="utf8"))
    plan=compile_plan(features,coverage)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(canonical(plan))
    print(json.dumps({k:v for k,v in plan.items() if k!="batches"},ensure_ascii=False))
if __name__=="__main__":main()
