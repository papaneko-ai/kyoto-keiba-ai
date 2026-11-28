"""Capture and independently compare a cushion workflow trigger even if its
producer job never runs. Only bounded identity metadata; no original data,
tokens, event payload, source HTTP, or authority to dispatch a run.
"""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timedelta
REPO="papaneko-ai/kyoto-keiba-ai"
PREFIX=".github/workflows/kyoto-20261128-29-"
PARENTS={PREFIX+"two-source-production-observer.yml",PREFIX+"auxiliary-refresh.yml"}
PATH=PREFIX+"cushion-source.yml"
CONFIRM="NOV28-29-CUSHION-SOURCE-ONLY"
SCHEMA="kyoto_cushion_trigger_evidence.v1"
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def utc(x):
    if not isinstance(x,str) or not re.fullmatch(r"2026-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z",x):raise ValueError("trigger_timestamp")
    d=datetime.fromisoformat(x.replace("Z","+00:00"))
    if d.utcoffset()!=timedelta(0):raise ValueError("trigger_timestamp")
    return d
def parent(p):
    if type(p.get("id")) is not int or p["id"]<=0 or not re.fullmatch(r"[a-f0-9]{40}",p.get("head_sha","")):raise ValueError("parent_identity")
    at=p["created_at"];utc(at)
    path=p.get("path","").split("@",1)[0]
    event=p.get("event")
    return {"id":p["id"],"head_sha":p["head_sha"],"created_at":at,
        "event":event if event in ("workflow_dispatch","schedule","workflow_run","push","pull_request") else "OTHER",
        "same_repository":p.get("head_repository",{}).get("full_name")==REPO,
        "main_branch":p.get("head_branch")=="main",
        "approved_parent_workflow":path if path in PARENTS else "OTHER"}
def gate(doc):
    if doc["event"]=="workflow_dispatch":
        return [] if doc["manual"]["confirmation_matches"] is True else ["MANUAL_CONFIRMATION_MISMATCH"]
    p=doc["parent"];t=utc(p["created_at"]);reasons=[]
    if not p["same_repository"]:reasons.append("PARENT_REPOSITORY_MISMATCH")
    if not p["main_branch"]:reasons.append("PARENT_BRANCH_MISMATCH")
    if t.strftime("%Y%m%d") not in ("20261128","20261129"):reasons.append("PARENT_DAY_OUTSIDE_SCOPE")
    if p["event"]!="workflow_dispatch":reasons.append("PARENT_EVENT_NOT_AUTHORIZED_DISPATCH")
    if t.hour not in (0,1,3):reasons.append("PARENT_HOUR_NOT_APPROVED")
    return reasons
def capture(payload,env):
    rid=int(env["GITHUB_RUN_ID"]);rev=env["GITHUB_SHA"];event=env["GITHUB_EVENT_NAME"]
    if rid<=0 or not re.fullmatch(r"[a-f0-9]{40}",rev) or env["GITHUB_REPOSITORY"]!=REPO or env["GITHUB_REF"]!="refs/heads/main" or event not in ("workflow_dispatch","workflow_run"):raise ValueError("trigger_identity")
    d={"schema":SCHEMA,"repo":REPO,"run_id":rid,"head_sha":rev,"event":event}
    if event=="workflow_run":d["parent"]=parent(payload["workflow_run"])
    else:
        v=payload["inputs"];day=v.get("race_day")
        d["manual"]={"day":day if day in ("20261128","20261129") else "OTHER","confirmation_matches":v.get("confirmation")==CONFIRM}
    d["gate_reasons"]=gate(d);d["producer_gate_eligible"]=not d["gate_reasons"];d["source_http_requests"]=0
    return d
def verify(doc,run,job_doc,read_parent):
    if (doc.get("schema")!=SCHEMA or doc.get("repo")!=REPO or doc.get("run_id")!=run["id"] or doc.get("head_sha")!=run["head_sha"]
        or doc.get("event")!=run["event"] or run.get("head_branch")!="main" or run.get("head_repository",{}).get("full_name")!=REPO
        or run.get("path","").split("@",1)[0]!=PATH or doc.get("source_http_requests")!=0):raise ValueError("trigger_receipt_identity")
    rows=job_doc["jobs"]
    if job_doc["total_count"]!=len(rows) or len({j["id"] for j in rows})!=len(rows) or any(j.get("run_id")!=run["id"] for j in rows):raise ValueError("trigger_job_index")
    evidence=[j for j in rows if j["name"]=="trigger-evidence" and j.get("status")=="completed" and j.get("conclusion")=="success"]
    producer=[j for j in rows if j["name"]=="cushion-source-only" and j.get("status")=="completed" and j.get("conclusion")=="skipped"]
    if len(evidence)!=1 or len(producer)!=1:raise ValueError("trigger_job_binding")
    if doc["event"]=="workflow_run":
        p=doc["parent"]
        if p.get("approved_parent_workflow") not in PARENTS:raise ValueError("parent_workflow")
        actual=read_parent(p["id"])
        if actual.get("status")!="completed" or parent(actual)!=p or utc(p["created_at"])>utc(run["created_at"]):raise ValueError("parent_run_mismatch")
    else:
        # Confirmation inputs cannot be independently read back from the
        # Actions run API. Preserve the receipt, but do not certify a manual skip.
        raise ValueError("manual_input_independent_proof_unavailable")
    reasons=gate(doc)
    if reasons!=doc.get("gate_reasons") or doc.get("producer_gate_eligible")!= (not reasons):raise ValueError("gate_recompute_mismatch")
    return {"state":"DIRECT_SKIP_CONDITION_VERIFIED" if reasons else "ELIGIBLE_BUT_PRODUCER_SKIPPED",
        "gate_reasons":reasons,"parent_run_id":doc["parent"]["id"],"parent_created_utc":doc["parent"]["created_at"],
        "parent_event":doc["parent"]["event"],"trigger_job_id":evidence[0]["id"],"producer_job_id":producer[0]["id"],
        "trigger_receipt_sha256":sha(canon(doc)),"upstream_scheduler_root_cause_proved":False,"source_success_certified":False}

def read_and_verify(run,job_doc,arts,api):
    name=f"kyoto-cushion-trigger-{run['id']}"
    if arts["total_count"]!=len(arts["artifacts"]):raise ValueError("trigger_artifact_index")
    found=[a for a in arts["artifacts"] if a.get("name")==name and a.get("expired") is False]
    if len(found)!=1:return None
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["gh","run","download",str(run["id"]),"--repo",REPO,"--name",name,"--dir",tmp],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=15)
        p=Path(tmp)/"receipt.json";q=Path(tmp)/"receipt.sha256"
        if p.is_symlink() or q.is_symlink() or not 0<p.stat().st_size<=20000 or not 0<q.stat().st_size<=128:raise ValueError("trigger_receipt_size")
        raw=p.read_bytes()
        if q.read_text().strip()!=sha(raw):raise ValueError("trigger_receipt_sha")
        result=verify(json.loads(raw),run,job_doc,lambda rid:api(f"repos/{REPO}/actions/runs/{rid}"))
        result["artifact_id"]=found[0]["id"]
        return result
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    payload=Path(os.environ["GITHUB_EVENT_PATH"])
    if not 0<payload.stat().st_size<=1_500_000:raise ValueError("event_size")
    doc=capture(json.loads(payload.read_bytes()),os.environ)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    raw=canon(doc)+b"\n";(out/"receipt.json").write_bytes(raw);(out/"receipt.sha256").write_text(sha(raw)+"\n")
    print("CUSHION_TRIGGER_EVIDENCE="+json.dumps({"eligible":doc["producer_gate_eligible"],"gate_reasons":doc["gate_reasons"]},sort_keys=True))
if __name__=="__main__":main()
