"""Finish only the TWO never-requested batch13 horses, using source-FIRST preservation.
Exactly two planned official URLs, no retries, no automatic JRA backfills.
"""
import argparse,hashlib,json,time
from pathlib import Path
from datetime import date,datetime,timezone
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from diagnostics.jra_pending_profile_plan import trusted_url,canonical
from diagnostics.jra_prior_form_offline import parse_horse_history
ROOT=Path("docs/diagnostics")
PLAN=ROOT/"JRA_PENDING_136_PROFILES_PLAN_20261106.json"
STATUS=ROOT/"jra_p1_transfer_fixed_88_profiles_20261106/status.json"
LEDGER=ROOT/"jra_p1_transfer_fixed_88_profiles_20261106/feature_rows_148.json"
OUTPUT_RECEIPT=ROOT/"jra_p1_profile_batches_20261106/batch_13_remaining_two_receipt.json"
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
MAX_BYTES=1_800_000
def now():return datetime.now(timezone.utc)
def preflight():
    if OUTPUT_RECEIPT.exists():raise ValueError("prior_two_horse_attempt_exists_no_retry")
    st=json.loads(STATUS.read_text(encoding="utf-8"))
    if st.get("profile_details_source_verified")!=88 or st.get("detailed_profiles_unqueried")!=60 or st.get("total_finished_prior_rows")!=355 or st.get("next_batch")!="batch_13_REMAINING_R8_HORSES_3_4_NEED_NEW_PLAN":
        raise ValueError("checkpoint_mismatch")
    batch=json.loads(PLAN.read_text(encoding="utf-8"))["batches"][12]
    if batch["batch_id"]!="batch_13" or len(batch["items"])!=6 or hashlib.sha256(canonical(batch["items"])).hexdigest()!=batch["batch_content_sha256"]:
        raise ValueError("fixed_plan_mismatch")
    prior=json.loads((ROOT/"jra_p1_profile_batches_20261106/batch_13_receipt.json").read_text(encoding="utf-8"))
    diagnostic=json.loads((ROOT/"jra_p1_r8h02_diagnosis_20261106/replayed_fixed_parser/replay_receipt.json").read_text(encoding="utf-8"))
    partial=json.loads((ROOT/"jra_p1_profile_batches_20261106/replayed_batch_13_partial/replay_receipt.json").read_text(encoding="utf-8"))
    if (prior["state"]!="BLOCKED" or prior["verified_count"]!=3 or prior["official_network_requests"]!=4
        or partial["verified_profiles"]!=3 or partial["new_network_requests"]!=0
        or diagnostic["state"]!="REPLAYED_SHA_VALIDATED_TRANSFER_EVENTS" or diagnostic["new_network_requests"]!=0):
        raise ValueError("partial_provenance_missing")
    rows=json.loads(LEDGER.read_text(encoding="utf-8"))
    if len(rows)!=148:raise ValueError("ledger_size")
    two=batch["items"][4:]
    if [(x["race_number"],x["horse_number"]) for x in two]!=[(8,3),(8,4)]:raise ValueError("incorrect_queue_slice")
    for x in two:
        candidates=[r for r in rows if r["race_number"]==x["race_number"] and r["horse_number"]==x["horse_number"]]
        if len(candidates)!=1:raise ValueError("ambiguous_race_horse")
        row=candidates[0];u=urlsplit(x["profile_url"])
        if row["horse_name"]!=x["horse_name"] or row["source_coverage"]["horse_profile"]!="NOT_QUERIED" or row["profile_href"]!=u.path+"?"+u.query or row["racecard_source_sha256"]!=x["racecard_sha256"]:
            raise ValueError("planned_unqueried_horse_identity_mismatch")
        if u.scheme!="https" or u.hostname!="jra.jp" or u.path!="/JRADB/accessU.html" or trusted_url(u.path+"?"+u.query)!=x["profile_url"]:
            raise ValueError("untrusted_official_url")
    return two,batch["batch_content_sha256"]
def capture(out,*,opener=urlopen,clock=now,sleep=time.sleep):
    two,batch_sha=preflight()
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    receipt={"schema":"jra_p1_batch13_source_first_remainder.v1",
        "batch_id":"batch_13_REMAINING_TWO","batch_content_sha256":batch_sha,
        "state":"BLOCKED","official_network_requests":0,"verified_count":0,
        "failed_count":0,"items":[],"retries":0,"prediction_ready":False,
        "training_ready":False}
    def save():(folder/"batch_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if clock()>=CUTOFF:
        receipt["reason"]="cutoff_expired_zero_requests";save();return receipt
    for i,x in enumerate(two):
        if i:sleep(2)
        rec={"race":x["race_number"],"horse_number":x["horse_number"],"horse_name":x["horse_name"],"source_url":x["profile_url"],"state":"BLOCKED"}
        try:
            if clock()>=CUTOFF:raise ValueError("cutoff_during_remainder")
            receipt["official_network_requests"]+=1
            request=Request(x["profile_url"],headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},method="GET")
            with opener(request,timeout=20) as response:
                raw=response.read(MAX_BYTES+1);http_code=response.status
                content_type=response.headers.get("Content-Type","");dest=urlsplit(response.geturl())
            stamp=clock()
            if http_code!=200 or not 0<len(raw)<=MAX_BYTES or "html" not in content_type.lower() or dest.scheme!="https" or dest.hostname not in ("jra.jp","www.jra.go.jp") or dest.path!="/JRADB/accessU.html" or stamp>=CUTOFF:
                raise ValueError("untrusted_response_or_cutoff")
            rec["captured_at_utc"]=stamp.isoformat()
            rec["source_sha256"]=hashlib.sha256(raw).hexdigest()
            rec["source_bytes"]=len(raw)
            # The crucial bugfix: save byte-exact original BEFORE parsing and exceptions.
            (folder/f"race_08_horse_{x['horse_number']:02d}.html").write_bytes(raw)
            rec["original_saved_before_parser"]=True
            receipt["items"].append(rec);save()
            parsed=parse_horse_history(raw,source_url=x["profile_url"],
                fetched_at_utc=stamp,prediction_cutoff_utc=CUTOFF,
                target_date=date(2026,11,7),expected_horse_name=x["horse_name"],
                allow_verified_no_history=True)
            rec["invalid_rows"]=parsed["invalid_rows"]
            rec["administrative_events"]=parsed.get("administrative_events",[])
            rec["prior_valid_finishes"]=parsed["prior_row_count"]
            rec["nonfinish_events"]=len(parsed["nonfinish_rows"])
            rec["history_status"]=parsed["history_status"]
            if parsed["invalid_rows"]:raise ValueError("invalid_history_rows")
            rec["state"]="SOURCE_PARSED"
            receipt["verified_count"]+=1
            save()
        except Exception as exc:
            rec["state"]="BLOCKED";rec["error"]=type(exc).__name__+":"+str(exc)[:180]
            receipt["failed_count"]+=1
            if rec not in receipt["items"]:receipt["items"].append(rec)
            receipt["reason"]="stop_on_first_error"
            save();return receipt
    receipt["state"]="SOURCE_PARSED_TEMPORARY";save();return receipt
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--out",required=True);v=a.parse_args()
    result=capture(v.out);print(json.dumps(result,ensure_ascii=False))
    if result["state"]!="SOURCE_PARSED_TEMPORARY":raise SystemExit(1)
