"""Guarded batch13 JRA capture. P1 only; no production/model changes."""
from __future__ import annotations
import hashlib, json, time, argparse
from datetime import datetime, date, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from diagnostics.jra_pending_profile_plan import canonical, trusted_url
from diagnostics.jra_prior_form_offline import parse_horse_history

ROOT=Path("docs/diagnostics")
PLAN=ROOT/"JRA_PENDING_136_PROFILES_PLAN_20261106.json"
STATE=ROOT/"jra_p1_twelve_batches_20261106/status.json"
ROWS=ROOT/"jra_p1_twelve_batches_20261106/feature_rows_148.json"
RECEIPT=ROOT/"jra_p1_profile_batches_20261106/batch_13_receipt.json"
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
LIMIT=1800000

def utcnow(): return datetime.now(timezone.utc)

def preflight():
    status=json.loads(STATE.read_text(encoding="utf-8"))
    expected=[f"batch_{i:02d}" for i in range(1,13)]
    if (status.get("next_batch")!="batch_13" or status.get("completed_batches")!=expected
        or status.get("profile_details_source_verified")!=84
        or status.get("detailed_profiles_unqueried")!=64
        or status.get("total_finished_prior_rows")!=282):
        raise ValueError("checkpoint_changed_refuse_duplicate_or_stale_run")
    if RECEIPT.exists(): raise ValueError("batch13_receipt_already_exists_refuse_repeat")
    base=RECEIPT.parent
    for i in range(1,12):
        r=json.loads((base/f"batch_{i:02d}_receipt.json").read_text(encoding="utf-8"))
        replay=json.loads((base/f"replayed_batch_{i:02d}"/"replay_receipt.json").read_text(encoding="utf-8"))
        if r.get("verified_count")!=6 or replay.get("verified_profiles")!=6 or replay.get("new_network_requests")!=0:
            raise ValueError(f"previous_batch_{i:02d}_unverified")
    p=json.loads(PLAN.read_text(encoding="utf-8"))
    if p.get("extraction_authorized") or p.get("production_writes_authorized") or p.get("training_ready"):
        raise ValueError("plan_must_not_self_authorize")
    batch=next(x for x in p["batches"] if x["batch_id"]=="batch_13")
    if batch["request_count"]!=6 or len(batch["items"])!=6 or hashlib.sha256(canonical(batch["items"])).hexdigest()!=batch["batch_content_sha256"]:
        raise ValueError("plan_identity_or_sha_mismatch")
    rows=json.loads(ROWS.read_text(encoding="utf-8"))
    assert len(rows)==148
    for index,item in enumerate(batch["items"]):
        match=[r for r in rows if r["race_number"]==item["race_number"] and r["horse_number"]==item["horse_number"]]
        if len(match)!=1: raise ValueError("race_horse_missing_or_ambiguous")
        row=match[0]
        if (item["horse_number"]!=row["horse_number"] or item["race_number"]!=row["race_number"]
            or row["horse_name"]!=item["horse_name"] or row["profile_status"]!="NOT_QUERIED"
            or row["profile_href"]!=urlsplit(item["profile_url"]).path+"?"+urlsplit(item["profile_url"]).query
            or row["racecard_source_sha256"]!=item["racecard_sha256"]):
            raise ValueError("racecard_or_unqueried_identity_mismatch")
        u=urlsplit(item["profile_url"])
        if u.scheme!="https" or u.hostname!="jra.jp" or u.path!="/JRADB/accessU.html":
            raise ValueError("non_official_url")
    return batch

def capture(out,*,opener=urlopen,clock=utcnow,sleep=time.sleep):
    batch=preflight()
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    receipt={"batch_id":"batch_13","batch_content_sha256":batch["batch_content_sha256"],
             "state":"BLOCKED","attempted":0,"official_network_requests":0,
             "verified_count":0,"failed_count":0,"items":[],
             "sources_retained":False,"historical_asof_reconstruction_authorized":False,
             "prediction_ready":False,"training_ready":False}
    def save(): (folder/"batch_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if clock()>=CUTOFF:
        receipt["reason"]="pre_race_asof_cutoff_expired";save();return receipt
    for i,item in enumerate(batch["items"]):
        if i:sleep(2)
        row={"race":item["race_number"],"horse_number":item["horse_number"],"horse_name":item["horse_name"],"source_url":item["profile_url"]}
        try:
            if clock()>=CUTOFF: raise ValueError("cutoff_expired_during_batch")
            u=urlsplit(item["profile_url"])
            verified=trusted_url(u.path+"?"+u.query)
            if verified!=item["profile_url"]: raise ValueError("url_canonical_mismatch")
            receipt["attempted"]+=1;receipt["official_network_requests"]+=1
            req=Request(verified,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},method="GET")
            with opener(req,timeout=20) as resp:
                raw=resp.read(LIMIT+1); status=resp.status
                ct=resp.headers.get("Content-Type","");dest=urlsplit(resp.geturl())
            captured=clock()
            if (status!=200 or not 0<len(raw)<=LIMIT or "html" not in ct.lower()
                or dest.scheme!="https" or dest.hostname not in ("jra.jp","www.jra.go.jp")
                or dest.path!="/JRADB/accessU.html"):
                raise ValueError("unexpected_response")
            if captured>=CUTOFF: raise ValueError("response_after_cutoff")
            parsed=parse_horse_history(raw,source_url=verified,fetched_at_utc=captured,
                prediction_cutoff_utc=CUTOFF,target_date=date(2026,11,7),
                expected_horse_name=item["horse_name"],allow_verified_no_history=True)
            if parsed["invalid_rows"]:raise ValueError("invalid_history_rows")
            sha=hashlib.sha256(raw).hexdigest()
            (folder/f"race_{item['race_number']:02d}_horse_{item['horse_number']:02d}.html").write_bytes(raw)
            row.update(state="SOURCE_PARSED",original_sha256=sha,source_bytes=len(raw),
                captured_at_utc=captured.isoformat(),prior_valid_finishes=parsed["prior_row_count"],
                nonfinish_events=len(parsed.get("nonfinish_rows",[])),
                history_status=parsed.get("history_status"))
            receipt["verified_count"]+=1
        except Exception as exc:
            row["state"]="BLOCKED";row["error"]=type(exc).__name__+":"+str(exc)[:180]
            receipt["failed_count"]+=1
            receipt["items"].append(row);receipt["reason"]="stop_on_first_error";save()
            return receipt
        receipt["items"].append(row);save()
    receipt["state"]="PARSED_ORIGINALS_TEMPORARY";save()
    return receipt

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True);a=ap.parse_args()
    result=capture(a.out)
    print(json.dumps(result,ensure_ascii=False))
    if result["state"]!="PARSED_ORIGINALS_TEMPORARY":raise SystemExit(1)
