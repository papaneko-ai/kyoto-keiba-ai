"""P1 incident diagnosis only: at most one JRA GET for unpreserved failed R8 horse02.
Original failed HTTP bytes are unavailable; a NEW timestamp must never be backdated.
No training, acceptance, production writes, or retries.
"""
import argparse,hashlib,json
from datetime import datetime,timezone,date
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from diagnostics.jra_pending_profile_plan import trusted_url
from diagnostics.jra_prior_form_offline import parse_horse_history

ROOT=Path("docs/diagnostics")
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
SOURCE_RECEIPT=ROOT/"jra_p1_profile_batches_20261106/batch_13_receipt.json"
CHECKPOINT=ROOT/"jra_p1_seven_races_partial_20261106/status.json"
ROWS=ROOT/"jra_p1_seven_races_partial_20261106/feature_rows_148.json"
URL="https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103507/A5"
EXPECTED="グラニットピーク"
LIMIT=1_800_000

def now():return datetime.now(timezone.utc)
def preflight():
    r=json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    s=json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    rows=json.loads(ROWS.read_text(encoding="utf-8"))
    if r["state"]!="BLOCKED" or r["official_network_requests"]!=4 or r["verified_count"]!=3 or r["failed_count"]!=1:
        raise ValueError("original_incident_receipt_changed")
    f=r["items"][3]
    if f.get("race")!=8 or f.get("horse_number")!=2 or f.get("horse_name")!=EXPECTED or f.get("source_url")!=URL or f.get("error")!="ValueError:invalid_history_rows":
        raise ValueError("incident_identity_changed")
    if s.get("next_batch")!="batch_13_BLOCKED_AT_R8_HORSE2" or s["profile_details_source_verified"]!=87:
        raise ValueError("incident_checkpoint_changed")
    matches=[x for x in rows if x["race_number"]==8 and x["horse_number"]==2]
    if len(rows)!=148 or len(matches)!=1 or matches[0]["horse_name"]!=EXPECTED or matches[0]["profile_status"]!="NOT_QUERIED":
        raise ValueError("cannot_diagnose_already_verified_or_changed")
    u=urlsplit(URL)
    if u.scheme!="https" or u.hostname!="jra.jp" or u.path!="/JRADB/accessU.html" or trusted_url(u.path+"?"+u.query)!=URL:
        raise ValueError("untrusted_official_url")
    return True

def probe(out,*,opener=urlopen,clock=now):
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    report={"schema_version":"jra_batch13_r8_02_diagnostic.v1","race":8,"horse_number":2,
            "horse_name":EXPECTED,"source_url":URL,"purpose":"INCIDENT_DIAGNOSIS_ONLY",
            "prior_failed_source_original_recovered":False,"network_requests":0,
            "prediction_ready":False,"training_ready":False,"state":"BLOCKED"}
    def save(): (folder/"diagnostic_receipt.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    try:
        preflight()
        if clock()>=CUTOFF:
            report["reason"]="cutoff_expired_no_http";save();return report
        req=Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},method="GET")
        report["network_requests"]=1
        with opener(req,timeout=20) as response:
            raw=response.read(LIMIT+1);status=response.status
            content_type=response.headers.get("Content-Type","")
            final=urlsplit(response.geturl())
        captured=clock()
        report["captured_at_utc"]=captured.isoformat()
        report["http_status"]=status
        report["source_bytes"]=len(raw)
        if status!=200 or not 0<len(raw)<=LIMIT or "html" not in content_type.lower() or final.scheme!="https" or final.hostname not in ("jra.jp","www.jra.go.jp") or final.path!="/JRADB/accessU.html" or captured>=CUTOFF:
            report["reason"]="bad_response_or_cutoff";save();return report
        # Crucial: seal and save original bytes BEFORE parser execution, even if parser fails.
        digest=hashlib.sha256(raw).hexdigest()
        report["source_sha256"]=digest
        (folder/"race_08_horse_02_diagnostic.html").write_bytes(raw)
        report["raw_saved_before_parser"]=True
        save()
        try:
            parsed=parse_horse_history(raw,source_url=URL,fetched_at_utc=captured,
                prediction_cutoff_utc=CUTOFF,target_date=date(2026,11,7),
                expected_horse_name=EXPECTED,allow_verified_no_history=True)
            report["history_rows_total"]=parsed["history_rows_total"]
            report["valid_prior_rows"]=parsed["prior_row_count"]
            report["invalid_rows"]=parsed["invalid_rows"]
            report["excluded_rows"]=parsed["excluded_rows"]
            report["nonfinish_rows"]=parsed["nonfinish_rows"]
            report["state"]="DIAGNOSED" if parsed["invalid_rows"] else "NO_INVALID_ROWS_ON_NEW_SNAPSHOT"
        except Exception as exc:
            report["state"]="PARSER_EXCEPTION_WITH_ORIGINAL_RETAINED"
            report["exception"]=type(exc).__name__+":"+str(exc)[:200]
    except Exception as exc:
        report["state"]="BLOCKED"
        report["reason"]=type(exc).__name__+":"+str(exc)[:200]
    save();return report

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    print(json.dumps(probe(a.out),ensure_ascii=False))
