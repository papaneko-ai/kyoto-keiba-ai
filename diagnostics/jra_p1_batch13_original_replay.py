"""Replay the six JRA source originals from Actions artifact before they expire.

No live HTTP. Verify each byte SHA, race/name identity, all observed runs,
and preserve their normalized rows with provenance separately from raw HTML.
"""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,date,timezone
from pathlib import Path
from diagnostics.jra_prior_form_offline import parse_horse_history
from diagnostics.jra_pending_profile_plan import canonical

PLAN=Path("docs/diagnostics/JRA_PENDING_136_PROFILES_PLAN_20261106.json")

CUTOFF=datetime.fromisoformat("2026-11-07T00:00:00+00:00")

def replay(originals,out,*,batch_id="batch_13"):
    if batch_id not in ("batch_13",):
        raise ValueError("batch_out_of_scope")
    d=json.loads(PLAN.read_text(encoding="utf8"))
    batch=next(x for x in d["batches"] if x["batch_id"]==batch_id)
    rec=json.loads((Path("docs/diagnostics/jra_p1_profile_batches_20261106")/(batch_id+"_receipt.json")).read_text(encoding="utf8"))
    if rec["batch_id"]!=batch_id or rec["state"]!="PARSED_ORIGINALS_TEMPORARY" or rec["verified_count"]!=6 or len(rec["items"])!=6:
        raise ValueError("source_batch_not_fully_captured")
    if rec["batch_content_sha256"]!=batch["batch_content_sha256"] or rec["official_network_requests"]!=6:
        raise ValueError("batch_receipt_provenance_mismatch")
    root=Path(originals);target=Path(out);target.mkdir(parents=True,exist_ok=True)
    reports=[]
    for expected,entry in zip(batch["items"],rec["items"]):
        race=expected["race_number"];num=expected["horse_number"]
        if entry["race"]!=race or entry["horse_number"]!=num or entry["horse_name"]!=expected["horse_name"]:
            raise ValueError("wrong_horse_or_order")
        paths=list(root.rglob(f"race_{race:02d}_horse_{num:02d}.html"))
        if len(paths)!=1:raise ValueError("original_missing_or_ambiguous")
        raw=paths[0].read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        if digest!=entry["original_sha256"] or len(raw)!=entry["source_bytes"]:
            raise ValueError("original_bytes_not_matching_prior_receipt")
        captured=datetime.fromisoformat(entry["captured_at_utc"].replace("Z","+00:00"))
        if captured.tzinfo is None or captured>=CUTOFF:raise ValueError("not_prerace_source")
        result=parse_horse_history(raw,source_url=expected["profile_url"],
            fetched_at_utc=captured,prediction_cutoff_utc=CUTOFF,
            target_date=date(2026,11,7),
            expected_horse_name=expected["horse_name"],
            allow_verified_no_history=True)
        if result["invalid_rows"] or result["prior_row_count"]!=entry["prior_valid_finishes"]:
            raise ValueError("source_parse_disagrees_with_receipt")
        if len(result.get("nonfinish_rows",[]))!=entry["nonfinish_events"]:
            raise ValueError("source_nonfinish_disagrees")
        data={"race":race,"horse_number":num,"horse_name":expected["horse_name"],
            "captured_at_utc":entry["captured_at_utc"],
            "source_sha256":digest,"prior_rows":result["prior_rows"],
            "nonfinish_rows":result.get("nonfinish_rows",[]),
            "history_status":result.get("history_status"),
            "historical_asof_leakage_prohibited":True,
            "prediction_ready":False,"training_ready":False}
        (target/f"race_{race:02d}_horse_{num:02d}_form.json").write_bytes(canonical(data))
        reports.append({"race":race,"horse_number":num,"horse_name":expected["horse_name"],
            "source_sha256":digest,"prior_rows":result["prior_row_count"],
            "state":"REPLAYED_FROM_ORIGINAL_SHA_VERIFIED"})
    summary={"schema_version":"jra_next_batch_independent_replay.v1",
        "batch_id":batch_id,"verified_profiles":len(reports),
        "total_profiles_including_prior_12":84+len(reports),
        "remaining_unqueried_profiles":64-len(reports),
        "new_network_requests":0,"original_artifact_durably_retained":False,
        "source_status":"PRE_RACE_ORIGINAL_SHA_REPLAYED",
        "items":reports,"prediction_ready":False,"training_ready":False}
    (target/"replay_receipt.json").write_bytes(canonical(summary))
    return summary

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);p.add_argument("--batch",required=True);a=p.parse_args()
 print(json.dumps(replay(a.artifact,a.out,batch_id=a.batch),ensure_ascii=False))
