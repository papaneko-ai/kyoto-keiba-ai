"""Finite Nov21/22 Kyoto source-acquisition experiment closeout.

Classify real GitHub run/artifact metadata without claiming source authentication.
After 2026-11-22 04:00 UTC, close experiment even with missing or failed runs.
Never call JRA or modify production collector/DB.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.request

DAYS=("20261121","20261122")
CUTOFF=datetime(2026,11,22,4,0,tzinfo=timezone.utc)
WORKFLOW="kyoto-20261121-22-two-source-production-observer.yml"
REPO="papaneko-ai/kyoto-keiba-ai"
LANES=("pc","sp")

def classify(runs: list[dict], artifacts_by_run: dict, *, now: datetime) -> dict:
    if now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("UTC_CLOCK_REQUIRED")
    if now < CUTOFF:
        raise ValueError("EXPERIMENT_NOT_YET_ENDED")
    if not isinstance(runs,list) or not isinstance(artifacts_by_run,dict):
        raise ValueError("INVALID_SOURCE_METADATA")
    result={"schema":"kyoto_weekend_fixed_end.v1",
            "closed_at_utc":now.isoformat(),
            "cutoff_utc":CUTOFF.isoformat(),
            "experiment_status":"CLOSED",
            "date_scope":list(DAYS),
            "source_accepted":False,
            "prediction_ready":False,
            "independent_live_connections_certified":0,
            "external_timer_latency_proven":False,
            "no_new_retries_authorized_by_this_report":True,
            "days":{}}
    for day in DAYS:
        valid=[]
        for run in runs:
            if not isinstance(run,dict):continue
            if run.get("event") not in ("schedule","workflow_dispatch"):continue
            if not isinstance(run.get("created_at"),str):continue
            if run["created_at"][:10].replace("-","") != day:continue
            if str(run.get("id","")).isdigit():
                valid.append(run)
        valid.sort(key=lambda x:(x["created_at"],int(x["id"])))
        details=[]
        for run in valid:
            rid=str(run["id"])
            artifacts=artifacts_by_run.get(rid,[])
            if not isinstance(artifacts,list):raise ValueError("MALFORMED_ARTIFACT_LIST")
            lanes={}
            for lane in LANES:
                expected=f"kyoto-{lane}-{rid}-{day}"
                matches=[a for a in artifacts if isinstance(a,dict)
                         and a.get("name")==expected and a.get("expired") is False]
                lanes[lane]={"artifact_present":len(matches)==1,
                             "artifact_count":len(matches),
                             "artifact_id":str(matches[0]["id"]) if len(matches)==1 and str(matches[0].get("id","")).isdigit() else None,
                             "artifact_digest":matches[0].get("digest") if len(matches)==1 else None,
                             "originals_authenticated":False}
            details.append({"run_id":rid,"created_at":run["created_at"],
                            "event":run["event"],"run_status":run.get("status"),
                            "run_conclusion":run.get("conclusion"),
                            "lanes":lanes,
                            "verified_source_claim":False})
        if not valid:
            status="NOT_EXECUTED"
        elif any(any(info["artifact_present"] for info in d["lanes"].values()) for d in details):
            status="ARTIFACT_PRESENT_CONTENT_UNVERIFIED"
        else:
            status="EXECUTED_WITHOUT_SOURCE_ARTIFACT"
        result["days"][day]={"outcome":status,"run_count":len(details),"runs":details}
    # This contract deliberately never upgrades artifact presence to official
    # pre-race source success. Independent decrypt+SHA/UTC+market checks are needed.
    outcomes={v["outcome"] for v in result["days"].values()}
    result["data_outcome"]=("NO_RUN" if outcomes=={"NOT_EXECUTED"} else
      "UNVERIFIED_OR_INCOMPLETE")
    result["terminal_decision"]="EXPERIMENT_ENDED_PROCESS_NEXT_PHASE_SEPARATELY"
    return result

def fetch_api(path:str,token:str):
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+"/"+path,
      headers={"Authorization":"Bearer "+token,
               "Accept":"application/vnd.github+json",
               "X-GitHub-Api-Version":"2022-11-28",
               "User-Agent":"Kyoto-AI-final-evidence-only"})
    with urllib.request.urlopen(req,timeout=18) as response:
        return json.load(response)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    now=datetime.now(timezone.utc)
    if now<CUTOFF:raise SystemExit("EXPERIMENT_CUTOFF_NOT_REACHED")
    token=os.environ["GH_TOKEN"]
    runs=[]
    # Explicit pagination prevents silently omitting earlier opportunities.
    for page in range(1,11):
        batch=fetch_api("actions/workflows/"+WORKFLOW+
          "/runs?created=2026-11-21..2026-11-22&per_page=100&page="+str(page),token).get("workflow_runs",[])
        if not isinstance(batch,list):raise SystemExit("RUN_API_INVALID")
        runs.extend(batch)
        if len(batch)<100:break
    else:
        raise SystemExit("RUN_HISTORY_OVER_1000_REQUIRES_REVIEW")
    artifacts={}
    for run in runs:
        rid=run.get("id")
        if not str(rid).isdigit():continue
        response=fetch_api("actions/runs/"+str(rid)+"/artifacts?per_page=100",token)
        if response.get("total_count",0)>100:raise SystemExit("ARTIFACT_PAGINATION_REQUIRED")
        artifacts[str(rid)]=response.get("artifacts",[])
    receipt=classify(runs,artifacts,now=now)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    args.out.write_bytes(raw)
    (args.out.parent/"closeout.sha256").write_text(
        hashlib.sha256(raw).hexdigest()+"  "+args.out.name+"\n")
    print("EXPERIMENT_TERMINAL_STATUS=CLOSED")
    print("DATA_OUTCOME="+receipt["data_outcome"])
    print("DAY21_RUN_COUNT="+str(receipt["days"]["20261121"]["run_count"]))
    print("DAY22_RUN_COUNT="+str(receipt["days"]["20261122"]["run_count"]))
    print("JRA_HTTP_REQUESTS_BY_CLOSEOUT=0")

if __name__=="__main__":
    main()
