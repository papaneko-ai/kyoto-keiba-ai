"""Manually triggered, bounded next batch only from frozen JRA official links.

Six sequential official profile GETs, 2s separation, no retry. Never modifies
production, no post-race historical backdating; stores raw HTML as expiring artifact.
"""
from __future__ import annotations
import argparse,json,hashlib,time
from datetime import datetime,date,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from diagnostics.jra_pending_profile_plan import canonical,trusted_url
from diagnostics.jra_prior_form_offline import parse_horse_history

PLAN=Path("docs/diagnostics/JRA_PENDING_136_PROFILES_PLAN_20261106.json")
ASOF_CUTOFF=datetime.fromisoformat("2026-11-07T00:00:00+00:00")
MAX=1800000

def fetch_batch(out,*,batch_id="batch_05",opener=urlopen,clock=lambda:datetime.now(timezone.utc),sleep=time.sleep):
    if batch_id not in ("batch_05","batch_06"):
        raise ValueError("only_reviewed_batches_05_06")
    checkpoint=json.loads(Path("docs/diagnostics/jra_p1_two_complete_races_20261106/status.json").read_text(encoding="utf8"))
    if (checkpoint["next_batch"]!="batch_05" or
        checkpoint["profile_details_source_verified"]!=36 or
        checkpoint["detailed_profiles_unqueried"]!=112 or
        checkpoint["completed_batches"]!=["batch_01","batch_02","batch_03","batch_04"]):
        raise ValueError("wrong_verified_previous_checkpoint")
    if batch_id=="batch_06":
        prior=Path("docs/diagnostics/jra_p1_profile_batches_20261106/batch_05_receipt.json")
        if not prior.exists():raise ValueError("batch05_receipt_missing")
        earlier=json.loads(prior.read_text(encoding="utf8"))
        if (earlier.get("verified_count")!=6 or earlier.get("failed_count")!=0 or
            earlier.get("state")!="PARSED_ORIGINALS_TEMPORARY"):
            raise ValueError("batch05_not_source_verified")
        replay=Path("docs/diagnostics/jra_p1_profile_batches_20261106/replayed_batch_05/replay_receipt.json")
        if not replay.exists() or json.loads(replay.read_text(encoding="utf8")).get("verified_profiles")!=6:
            raise ValueError("batch05_independent_replay_missing")
    plan=json.loads(PLAN.read_text(encoding="utf8"))
    if plan["extraction_authorized"] or plan["production_writes_authorized"] or plan["training_ready"]:
        raise ValueError("offline_plan_must_not_self_authorize")
    batch=next((x for x in plan["batches"] if x["batch_id"]==batch_id),None)
    if batch is None or batch["request_count"]>6 or len(batch["items"])!=batch["request_count"]:
        raise ValueError("batch_limit_or_identity_failed")
    if hashlib.sha256(canonical(batch["items"])).hexdigest()!=batch["batch_content_sha256"]:
        raise ValueError("batch_content_sha256_mismatch")
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    receipt={"schema_version":"jra_six_horse_batch_receipt.v1",
       "batch_id":batch_id,"batch_content_sha256":batch["batch_content_sha256"],
       "attempted":0,"verified_count":0,"failed_count":0,
       "sources_retained":False,"state":"BLOCKED","items":[],
       "official_network_requests":0,"historical_asof_reconstruction_authorized":False,
       "prediction_ready":False,"training_ready":False}
    def persist():
        (folder/"batch_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    if clock()>=ASOF_CUTOFF:
        receipt["reason"]="pre_race_asof_cutoff_expired"
        persist();return receipt
    for i,item in enumerate(batch["items"]):
        if i:sleep(2)
        record={"race":item["race_number"],"horse_number":item["horse_number"],
                "horse_name":item["horse_name"],"state":"STARTED"}
        try:
            if clock()>=ASOF_CUTOFF:raise ValueError("cutoff_expired_during_batch")
            url=trusted_url(urlsplit(item["profile_url"]).path+"?"+urlsplit(item["profile_url"]).query)
            if url!=item["profile_url"]:raise ValueError("source_url_canonical_mismatch")
            request=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},method="GET")
            receipt["official_network_requests"]+=1
            receipt["attempted"]+=1
            with opener(request,timeout=20) as response:
                raw=response.read(MAX+1);status=response.status
                ct=response.headers.get("Content-Type","")
                final=urlsplit(response.geturl())
            captured=clock()
            if (status!=200 or not 0<len(raw)<=MAX or "html" not in ct.lower()
                or final.scheme!="https" or final.hostname not in ("jra.jp","www.jra.go.jp")
                or final.path!="/JRADB/accessU.html"):
                raise ValueError("bad_official_html")
            original_sha=hashlib.sha256(raw).hexdigest()
            (folder/f"race_{item['race_number']:02d}_horse_{item['horse_number']:02d}.html").write_bytes(raw)
            parsed=parse_horse_history(raw,source_url=url,fetched_at_utc=captured,
                prediction_cutoff_utc=ASOF_CUTOFF,target_date=date(2026,11,7),
                expected_horse_name=item["horse_name"],
                allow_verified_no_history=True)
            if parsed["invalid_rows"]:
                raise ValueError("unresolved_profile_history_rows")
            record.update(state="SOURCE_PARSED",original_sha256=original_sha,
                source_bytes=len(raw),captured_at_utc=captured.isoformat(),
                prior_valid_finishes=parsed["prior_row_count"],
                nonfinish_events=len(parsed.get("nonfinish_rows",[])),
                no_history_table=parsed.get("profile_history_table_absent",False),
                history_status=parsed.get("history_status"))
            (folder/f"race_{item['race_number']:02d}_horse_{item['horse_number']:02d}_parsed.json").write_text(
                json.dumps({"race":item["race_number"],"number":item["horse_number"],
                    "name":item["horse_name"],"original_sha256":original_sha,
                    "captured_at_utc":captured.isoformat(),"prior_rows":parsed["prior_rows"],
                    "nonfinish_rows":parsed.get("nonfinish_rows",[]),
                    "history_status":parsed.get("history_status"),
                    "prediction_ready":False,"training_ready":False},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
            receipt["verified_count"]+=1
        except Exception as exc:
            record["state"]="BLOCKED"
            record["error"]=type(exc).__name__+":"+str(exc)[:180]
            receipt["failed_count"]+=1
        receipt["items"].append(record);persist()
    if receipt["verified_count"]==batch["request_count"] and receipt["failed_count"]==0:
        receipt["state"]="PARSED_ORIGINALS_TEMPORARY"
        receipt["sources_retained"]=False  # 3-day artifact is NOT durable retention
    elif receipt["verified_count"]>0:receipt["state"]="PARTIAL"
    else:receipt["state"]="BLOCKED"
    persist()
    return receipt

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    p.add_argument("--batch",default="batch_05");a=p.parse_args()
    print(json.dumps(fetch_batch(a.out,batch_id=a.batch),ensure_ascii=False))
