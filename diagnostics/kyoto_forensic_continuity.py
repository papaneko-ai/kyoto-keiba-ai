"""Preserve bounded evidence for the next repair. Never grant acquisition credit."""
import base64,gzip,hashlib,json,os,re,time
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPO="papaneko-ai/kyoto-keiba-ai"
SCHEMA="kyoto_forensic_capsule.v1"
MAX_LOG=2_000_000
MAX_TOTAL=8_000_000
MAX_JOBS=12

def canon(v):
    return json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def identity(run):
    if type(run.get("id")) is not int or run["id"]<=0 or not re.fullmatch(r"[a-f0-9]{40}",run.get("head_sha","")):
        raise ValueError("forensic_run_identity")
    return {"schema":SCHEMA,"repo":REPO,"source_run_id":run["id"],"source_head_sha":run["head_sha"]}

def key_bytes(key):
    if not isinstance(key,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",key):
        raise ValueError("forensic_key_unavailable")
    return bytes.fromhex(key)

def log_index(raw):
    rows=[]
    for n,line in enumerate(raw.splitlines(),1):
        if re.search(rb"Traceback \(most recent call last\)|(?:[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Rejected)):",line):
            rows.append({"line":n,"sha256":sha(line)})
            if len(rows)>=80:break
    return rows

def capture(run,jobs,arts,out,key,read_log,*,clock=time.monotonic):
    bind=identity(run);k=key_bytes(key);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rows=jobs["jobs"]
    if jobs["total_count"]!=len(rows) or len({j["id"] for j in rows})!=len(rows) or any(type(j["id"]) is not int or j["id"]<=0 or j.get("run_id")!=run["id"] for j in rows):
        raise ValueError("forensic_job_identity")
    if arts["total_count"]!=len(arts["artifacts"]):raise ValueError("forensic_artifact_index")
    logs={};raw_cache={};index=[];size=0;end=clock()+60
    for i,j in enumerate(sorted(rows,key=lambda x:x["id"])):
        jid=j["id"];row={"job_id":jid}
        if j.get("conclusion")=="skipped":
            row.update(state="SKIPPED_NO_LOG_EXPECTED",next_action="REOPEN_EXACT_JOB_CONDITION")
        elif i>=MAX_JOBS or size>=MAX_TOTAL or clock()+24>end:
            row.update(state="LOG_BUDGET_EXHAUSTED",next_action="FETCH_EXACT_JOB_LOG_BEFORE_EXPIRY")
        else:
            try:
                fetched=read_log(jid)
                raw,fmt=fetched if isinstance(fetched,tuple) else (fetched,"JOB_API_RAW")
                if fmt not in ("JOB_API_RAW","GH_RUN_VIEW_RENDERED"):raise ValueError("forensic_log_format")
                if type(raw) is not bytes or not 0<len(raw)<=MAX_LOG:raise ValueError("forensic_log_size")
                if size+len(raw)>MAX_TOTAL:raise ValueError("forensic_total_log_size")
                logs[jid]=raw;size+=len(raw)
                if fmt=="JOB_API_RAW":raw_cache[jid]=raw
                row.update(state="LOG_BYTES_PRESERVED",log_format=fmt,bytes=len(raw),sha256=sha(raw),exception_line_refs=log_index(raw))
            except Exception as exc:
                row.update(state="LOG_UNAVAILABLE",error_class=type(exc).__name__,next_action="RECOVER_LOG_OR_RUNNER_PROVIDER_EVIDENCE")
        index.append(row)
    doc={"identity":bind,"run":run,"jobs":jobs,"artifacts":arts,"log_index":index,"logs":{str(j):base64.b64encode(v).decode("ascii") for j,v in logs.items()}}
    payload=canon(doc);nonce=os.urandom(12)
    sealed=AESGCM(k).encrypt(nonce,gzip.compress(payload,mtime=0),canon(bind))
    manifest={**bind,"nonce_hex":nonce.hex(),"ciphertext_sha256":sha(sealed),"payload_sha256":sha(payload),"log_index":index,"source_artifact_ids":sorted(a["id"] for a in arts["artifacts"]),"state":("SEALED_WITH_RENDERED_LOGS" if any(x.get("log_format")=="GH_RUN_VIEW_RENDERED" for x in index) else "SEALED_COMPLETE_LOG_SET") if index and all(x["state"] in ("LOG_BYTES_PRESERVED","SKIPPED_NO_LOG_EXPECTED") for x in index) else "SEALED_WITH_EVIDENCE_GAPS","new_source_http_requests":0}
    (out/"forensic.aesgcm.tmp").write_bytes(sealed)
    (out/"forensic.json.tmp").write_bytes(canon(manifest)+b"\n")
    (out/"forensic.aesgcm.tmp").replace(out/"forensic.aesgcm")
    (out/"forensic.json.tmp").replace(out/"forensic.json")
    if restore(out,key,run)!=doc:raise ValueError("forensic_roundtrip")
    return manifest,raw_cache

def restore(out,key,run):
    out=Path(out);bind=identity(run);m=json.loads((out/"forensic.json").read_bytes());sealed=(out/"forensic.aesgcm").read_bytes()
    if any(m.get(k)!=v for k,v in bind.items()) or m.get("ciphertext_sha256")!=sha(sealed) or not re.fullmatch(r"[a-f0-9]{24}",m.get("nonce_hex","")):
        raise ValueError("forensic_manifest_mismatch")
    payload=gzip.decompress(AESGCM(key_bytes(key)).decrypt(bytes.fromhex(m["nonce_hex"]),sealed,canon(bind)))
    if sha(payload)!=m["payload_sha256"]:raise ValueError("forensic_payload_mismatch")
    doc=json.loads(payload)
    if doc["identity"]!=bind or doc["log_index"]!=m["log_index"]:raise ValueError("forensic_payload_identity")
    if sorted(a["id"] for a in doc["artifacts"]["artifacts"])!=m["source_artifact_ids"]:raise ValueError("forensic_artifact_mismatch")
    for row in m["log_index"]:
        val=doc["logs"].get(str(row["job_id"]))
        if row["state"]=="LOG_BYTES_PRESERVED":
            if val is None or row.get("log_format") not in ("JOB_API_RAW","GH_RUN_VIEW_RENDERED"):raise ValueError("forensic_log_missing_or_format")
            raw=base64.b64decode(val,validate=True)
            if sha(raw)!=row["sha256"] or len(raw)!=row["bytes"]:raise ValueError("forensic_log_mismatch")
        elif val is not None:raise ValueError("forensic_index_mismatch")
    return doc

FAIL_FIELDS={"reason","error","error_class","error_code","failure_reason","failure_class","results_meeting_state","payout_meeting_state","transport_stop_reason","racecard_error_class","track_error_class"}
SAFE_PATH={"races","requests","attempts","records","errors","failures","stages","observations","market","markets","profile","profiles","horses","results","payout","quinella","bracket_quinella","navigation","independent_reconciliation"}|FAIL_FIELDS

def receipt_refs(root,files):
    """Locate exact values in existing authenticated receipts without exposing them."""
    root=Path(root);refs=[];incomplete=False
    def visit(v,path,name,file_sha):
        nonlocal incomplete
        if len(refs)>=400 or len(path)>20:
            incomplete=True;return
        if isinstance(v,dict):
            for k,x in sorted(v.items()):
                safe=k if k in SAFE_PATH or re.fullmatch(r"[0-9]{1,4}",k) else "key_sha256:"+sha(k.encode())
                if k in FAIL_FIELDS and isinstance(x,str) and x:
                    if len(refs)>=400:incomplete=True;return
                    refs.append({"file":name,"file_sha256":file_sha,"path":path+[safe],"value_sha256":sha(x.encode())})
                elif isinstance(x,(dict,list)):visit(x,path+[safe],name,file_sha)
        elif isinstance(v,list):
            for n,x in enumerate(v):
                if isinstance(x,(dict,list)):visit(x,path+[str(n)],name,file_sha)
    for name,meta in sorted(files.items()):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,110}",name) or not name.endswith("receipt.json"):continue
        p=root/name
        try:
            if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=1_500_000:raise ValueError("receipt_size")
            raw=p.read_bytes()
            if sha(raw)!=meta["sha256"]:raise ValueError("receipt_sha")
            visit(json.loads(raw),[],name,meta["sha256"])
        except (ValueError,OSError,TypeError):incomplete=True
    return {"refs":refs,"incomplete":incomplete}

def obligations(report):
    rows=[]
    for lane,meta in sorted(report["lanes"].items()):
        incidents=list(meta.get("incidents",[]))
        if meta.get("source_acquisition_state")=="PRODUCER_NOT_EXECUTED_SKIP_REASON_UNVERIFIED":
            incidents.append({"stage":"PRODUCER_SKIP","code":"SKIP_REASON_NOT_PROVED","diagnostic_action":"REOPEN_EXACT_JOB_CONDITION_AND_EVENT"})
        for x in incidents:
            origin={"run_id":report["source_run_id"],"lane":lane,"stage":x["stage"],"code":x.get("code") or "UNKNOWN"}
            files=[{"name":n,**meta["files"][n]} for n in x.get("evidence_files",[]) if n in meta.get("files",{})]
            rows.append({**origin,"incident_id":"INC-"+sha(canon(origin))[:24],"state":"OPEN_REPAIR_REQUIRED","root_cause_proved":False,"blocked_by":x.get("blocked_by"),"source_head_sha":report["workflow_head_sha"],"artifact_id":meta.get("artifact_id"),"artifact_authenticated":meta.get("artifact_authenticated") is True,"source_files":files,"receipt_failure_refs":meta.get("receipt_failure_refs",{}),"log_job_ids":[j["job_id"] for j in report.get("jobs",[])],"next_action":x.get("diagnostic_action","REOPEN_EXACT_METADATA_AND_SOURCE_EVIDENCE"),"repair_direction":x.get("repair_direction"),"required_regression":x.get("required_regression"),"target_day":meta.get("target_day"),"missing_evidence":x.get("missing_evidence"),"missing_races":x.get("missing_races",[]),"closure_requires":["EXACT_CAUSE_REPRODUCED","ISOLATED_FIX","NEGATIVE_CASE","DEPLOYMENT_CHECK","NEXT_ACTUAL_CAPTURE"]})
    evidence=report.get("forensic_evidence",{})
    gaps=[]
    if evidence.get("state")=="FORENSIC_CAPSULE_UNAVAILABLE":
        gaps.append(("FORENSIC_CAPSULE_UNAVAILABLE",None,evidence.get("next_action","RECOVER_EXACT_SOURCE_RUN_AND_JOB_LOGS")))
    for log in evidence.get("log_index",[]):
        if log.get("state") in ("LOG_UNAVAILABLE","LOG_BUDGET_EXHAUSTED"):
            gaps.append((log["state"],log["job_id"],log.get("next_action","FETCH_EXACT_JOB_LOG_BEFORE_EXPIRY")))
    for code,jid,action in gaps:
        origin={"run_id":report["source_run_id"],"lane":"forensic","stage":"LOG_EVIDENCE","code":code,"job_id":jid}
        rows.append({**origin,"incident_id":"INC-"+sha(canon(origin))[:24],"state":"OPEN_REPAIR_REQUIRED","root_cause_proved":False,
            "source_head_sha":report["workflow_head_sha"],"artifact_id":None,"artifact_authenticated":False,"source_files":[],
            "log_job_ids":[jid] if jid is not None else [j["job_id"] for j in report.get("jobs",[])],
            "next_action":action,"missing_evidence":"exact source run/job logs and authenticated capsule restoration",
            "closure_requires":["EXACT_EVIDENCE_RECOVERED","AUTHENTICATED_RESTORE"]})
    return rows
