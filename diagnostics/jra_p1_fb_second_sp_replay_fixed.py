"""P1-FB: offline replay SP second horse 39 events, source SHA and time gated.
No PC-parity claim for horse 2, no new verified-runner admission, no HTTP.
"""
from datetime import datetime,date,timezone
from pathlib import Path
from hashlib import sha256
import argparse,json
from diagnostics.jra_p1_sp_profile_offline import parse
from diagnostics.jra_pending_profile_plan import canonical
ROOT=Path("docs/diagnostics/jra_p1_fb_offline_20261106")
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
def replay(folder):
    receipt=json.loads((ROOT/"sp_profile_second_receipt.json").read_text(encoding="utf8"))
    candidates=list(Path(folder).rglob("sp_11r_horse02.html"))
    if len(candidates)!=1:raise ValueError("source_original_not_unique")
    raw=candidates[0].read_bytes();digest=sha256(raw).hexdigest()
    if digest!=receipt["source_sha256"] or len(raw)!=receipt["source_bytes"] or receipt["network_requests"]!=1 or not receipt["original_saved_before_parser"]:
        raise ValueError("source_integrity_mismatch")
    if receipt["source_url"]!="https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002019105761/89" or receipt["horse_name"]!="エティエンヌ":
        raise ValueError("not_same_official_horse")
    stamp=datetime.fromisoformat(receipt["captured_at_utc"].replace("Z","+00:00"))
    if stamp.tzinfo is None or stamp.astimezone(timezone.utc)>=CUTOFF:raise ValueError("not_before_cutoff")
    parsed=parse(raw,receipt["horse_name"])
    rows=parsed["prior_rows"]
    if parsed["history_rows_total"]!=39 or len(rows)!=37 or parsed["invalid_rows"] or len(parsed["administrative_events"])!=2 or parsed["nonfinish_rows"]:
        raise ValueError("SP_39_row_safety_gate_failed")
    if {x["event_type"] for x in parsed["administrative_events"]}!={"JRA_TRANSFER_IN","JRA_TRANSFER_OUT"}:
        raise ValueError("misclassified_transfer_event")
    local=[x for x in rows if x["jurisdiction"]=="LOCAL"]
    missing=[x for x in rows if x["popularity_missing"]]
    if len(local)!=11 or len(missing)!=1 or missing[0]["venue"]!="園田" or missing[0]["popularity"] is not None:
        raise ValueError("missing_local_race_policy_failed")
    if any(x["date"]>="2026-11-07" or not(1<=x["finish_position"]<=x["field_size"]) for x in rows):
        raise ValueError("future_or_invalid_historical_finish")
    return {"schema":"p1_fb_sp_second_independent_replay.v1","source_sha256":digest,
      "horse_name":receipt["horse_name"],"race":11,"number":2,
      "source_time_utc":receipt["captured_at_utc"],"history_rows":39,
      "prior_valid_finishes":37,"local_race_finishes":11,"jra_race_finishes":26,
      "administrative_events":2,"popularity_missing_count":1,
      "invalid_rows":0,"source_first":True,"new_network_requests":0,
      "profile_count_addition_to_148":0,"pc_full_parity_verified":False,
      "live_automatic_fallback_authorized":False,
      "training_ready":False,"prediction_ready":False}
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--artifact",required=True);a.add_argument("--out",required=True);args=a.parse_args()
    data=replay(args.artifact);o=Path(args.out);o.parent.mkdir(parents=True,exist_ok=True)
    o.write_bytes(canonical(data));print(json.dumps(data,ensure_ascii=False))
