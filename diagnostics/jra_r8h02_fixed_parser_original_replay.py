"""Independent replay of the original that failed before transfer-row repair.
No HTTP; keep training and model disabled. Prove SHA, timestamps, 26 valid
finishes, 2 exact administrative transfer events, 0 invalid rows.
"""
import argparse,hashlib,json
from datetime import date,datetime,timezone
from pathlib import Path
from diagnostics.jra_prior_form_offline import parse_horse_history
from diagnostics.jra_pending_profile_plan import canonical
from diagnostics.jra_batch13_r8h02_one_shot_diagnostic import URL,EXPECTED,CUTOFF
RECEIPT=Path("docs/diagnostics/jra_p1_r8h02_diagnosis_20261106/receipt.json")
def replay(originals,out):
    r=json.loads(RECEIPT.read_text(encoding="utf-8"))
    if r["state"]!="DIAGNOSED" or r["source_url"]!=URL or r["horse_name"]!=EXPECTED or r["network_requests"]!=1 or r["prior_failed_source_original_recovered"]:
        raise ValueError("diagnostic_identity_or_provenance_changed")
    paths=list(Path(originals).rglob("race_08_horse_02_diagnostic.html"))
    if len(paths)!=1:raise ValueError("source_missing_or_ambiguous")
    raw=paths[0].read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!=r["source_sha256"] or len(raw)!=r["source_bytes"]:raise ValueError("source_bytes_differ")
    stamp=datetime.fromisoformat(r["captured_at_utc"].replace("Z","+00:00"))
    if stamp.tzinfo is None or stamp.astimezone(timezone.utc)>=CUTOFF:raise ValueError("post_cutoff_original")
    d=parse_horse_history(raw,source_url=URL,fetched_at_utc=stamp,
                          prediction_cutoff_utc=CUTOFF,target_date=date(2026,11,7),
                          expected_horse_name=EXPECTED,allow_verified_no_history=True)
    admin=d.get("administrative_events",[])
    if (d["history_rows_total"]!=28 or d["prior_row_count"]!=26 or d["invalid_rows"]
        or len(admin)!=2 or {e["event_type"] for e in admin}!={"JRA_TRANSFER_IN","JRA_TRANSFER_OUT"}
        or {e["row"] for e in admin}!={17,23}
        or any(e.get("included_in_finish_metrics") is not False for e in admin)):
        raise ValueError("original_source_not_precisely_repaired")
    result={"schema_version":"jra_p1_r8h02_offline_transfer_replay.v1",
        "race":8,"horse_number":2,"horse_name":EXPECTED,"source_sha256":digest,
        "source_bytes":len(raw),"captured_at_utc":r["captured_at_utc"],
        "source_is_new_diagnostic_snapshot_not_original_failed_http":True,
        "previous_failed_http_was_not_reused":True,
        "new_network_requests":0,
        "history_rows_total":28,"prior_valid_finishes":26,"invalid_rows":[],
        "administrative_events":admin,"training_ready":False,"prediction_ready":False,
        "state":"REPLAYED_SHA_VALIDATED_TRANSFER_EVENTS"}
    normalized={"race":8,"horse_number":2,"horse_name":EXPECTED,
        "source_sha256":digest,"captured_at_utc":r["captured_at_utc"],
        "prior_rows":d["prior_rows"],"excluded_rows":d["excluded_rows"],
        "nonfinish_rows":d["nonfinish_rows"],"administrative_events":admin,
        "history_status":d["history_status"],"training_ready":False,"prediction_ready":False}
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    (p/"replay_receipt.json").write_bytes(canonical(result))
    (p/"race_08_horse_02_form.json").write_bytes(canonical(normalized))
    return result
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--artifact",required=True);a.add_argument("--out",required=True);v=a.parse_args()
    print(json.dumps(replay(v.artifact,v.out),ensure_ascii=False))
