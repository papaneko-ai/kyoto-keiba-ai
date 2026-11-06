"""Independent, zero-HTTP verification of only the six batch14 originals."""
import argparse,hashlib,json
from pathlib import Path
from datetime import date,datetime,timezone
from diagnostics.jra_prior_form_offline import parse_horse_history
from diagnostics.jra_pending_profile_plan import canonical
ROOT=Path("docs/diagnostics")
REC=ROOT/"jra_p1_profile_batches_20261106/batch_14_receipt.json"
PLAN=ROOT/"JRA_PENDING_136_PROFILES_PLAN_20261106.json"
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
def replay(originals,out):
    receipt=json.loads(REC.read_text(encoding="utf-8"))
    plan=json.loads(PLAN.read_text(encoding="utf-8"))["batches"][13]
    two=plan["items"]
    if receipt["state"]!="SOURCE_PARSED_TEMPORARY" or receipt["verified_count"]!=6 or receipt["failed_count"]!=0 or receipt["official_network_requests"]!=6 or receipt["batch_content_sha256"]!=plan["batch_content_sha256"] or len(receipt["items"])!=6:
        raise ValueError("bad_remainder_capture_receipt")
    results=[];dst=Path(out);dst.mkdir(parents=True,exist_ok=True)
    for expected,rec in zip(two,receipt["items"]):
        n=expected["horse_number"];race=expected["race_number"]
        if (rec["state"]!="SOURCE_PARSED" or not rec.get("original_saved_before_parser")
            or rec["race"]!=race or rec["horse_number"]!=n or rec["horse_name"]!=expected["horse_name"]):
            raise ValueError("incorrect_original_receipt_identity")
        paths=list(Path(originals).rglob(f"race_{race:02d}_horse_{n:02d}.html"))
        if len(paths)!=1:raise ValueError("original_not_found_or_multiple")
        raw=paths[0].read_bytes();h=hashlib.sha256(raw).hexdigest()
        if h!=rec["source_sha256"] or len(raw)!=rec["source_bytes"]:raise ValueError("source_sha_mismatch")
        stamp=datetime.fromisoformat(rec["captured_at_utc"].replace("Z","+00:00"))
        if stamp.tzinfo is None or stamp.astimezone(timezone.utc)>=CUTOFF:raise ValueError("postcutoff")
        parsed=parse_horse_history(raw,source_url=expected["profile_url"],
            fetched_at_utc=stamp,prediction_cutoff_utc=CUTOFF,
            target_date=date(2026,11,7),expected_horse_name=expected["horse_name"],
            allow_verified_no_history=True)
        if parsed["invalid_rows"] or parsed["prior_row_count"]!=rec["prior_valid_finishes"] or len(parsed["nonfinish_rows"])!=rec["nonfinish_events"] or parsed.get("administrative_events",[])!=rec["administrative_events"]:
            raise ValueError("offline_replay_disagrees")
        d={"race":race,"horse_number":n,"horse_name":expected["horse_name"],"source_sha256":h,
           "captured_at_utc":rec["captured_at_utc"],"prior_rows":parsed["prior_rows"],
           "nonfinish_rows":parsed["nonfinish_rows"],"administrative_events":parsed.get("administrative_events",[]),
           "history_status":parsed["history_status"],"training_ready":False,"prediction_ready":False}
        (dst/f"race_{race:02d}_horse_{n:02d}_form.json").write_bytes(canonical(d))
        results.append({"race":race,"horse_number":n,"horse_name":expected["horse_name"],
                        "source_sha256":h,"prior_rows":len(parsed["prior_rows"]),"administrative_events":len(d["administrative_events"])})
    report={"schema":"batch14_independent_replay.v1",
        "state":"SIX_ORIGINALS_REPLAYED","verified_count":len(results),"network_requests":0,
        "items":results,"training_ready":False,"prediction_ready":False}
    (dst/"replay_receipt.json").write_bytes(canonical(report))
    return report
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    print(json.dumps(replay(a.artifact,a.out),ensure_ascii=False))
