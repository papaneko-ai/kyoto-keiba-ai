"""Idempotent, verified GitHub archival of ciphertext and SAFE receipts only.

Directly archives observed Nov21 4x PC/SP failure/source attempts plus Nov22
12R success/G03/108-family ledger in a separate evidence branch. Never
touch main, never publish plaintext or use a JRA HTTP request.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

REPO=os.environ["GITHUB_REPOSITORY"]
BRANCH="archive/kyoto-ai-encrypted-original-evidence"
ROOT=Path("intake")
RUNS=(44848944302,44854931835,44857934629,44861934823)
MAX_BYTES=1_500_000
FILES={
    "nov22/full12":("ciphertext_sha256.txt","originals_all12.tar.gz.aesgcm","source_receipts_summary.json"),
    "nov22/g03":("safe_race_parser_results.json",),
    "nov22/ledger":("nov22_108_records.json",)
}
FAILURE_ALLOWED={
    "pc":("manifest.json","safe_stop.json","originals.tar.gz.aesgcm"),
    "sp":("manifest.json","safe_stop.json","originals.tar.gz.aesgcm"),
}

def api(method,path,payload=None):
    cmd=["gh","api","-X",method,f"repos/{REPO}/{path}"]
    if payload is not None:cmd+=["--input","-"]
    p=subprocess.run(cmd,input=json.dumps(payload) if payload is not None else None,
                     text=True,capture_output=True)
    if p.returncode:
        if method=="GET" and "404" in p.stderr:return None
        raise RuntimeError("GitHub API rejected "+method+" "+path+": "+p.stderr[:240])
    return json.loads(p.stdout)

def approved_files():
    for run in RUNS:
        for lane in ("pc","sp"):
            folder=ROOT/"nov21"/str(run)/lane
            if not folder.is_dir():raise ValueError("missing_evidence:"+str(folder))
            names={p.name for p in folder.iterdir()}
            if not names or not names.issubset(FAILURE_ALLOWED[lane]):
                raise ValueError("unapproved_failure_evidence_file:"+str(folder))
            if not ("manifest.json" in names or "safe_stop.json" in names):
                raise ValueError("missing_failure_receipt")
            yield from sorted(folder.iterdir())
    for area,names in FILES.items():
        folder=ROOT/area
        if not folder.is_dir() or set(p.name for p in folder.iterdir())!=set(names):
            raise ValueError("source_success_bundle_incomplete:"+area)
        yield from sorted(folder.iterdir())

def validate(file):
    if file.is_symlink() or not file.is_file():
        raise ValueError("invalid_evidence_file")
    data=file.read_bytes()
    if not 0<len(data)<=MAX_BYTES:raise ValueError("size_out_of_scope")
    name=file.name
    if name.endswith(".aesgcm"):
        if len(data)<32:raise ValueError("ciphertext_too_short")
        kind="ENCRYPTED_SOURCE"
    elif name.endswith(".json"):
        obj=json.loads(data.decode("utf-8"))
        if not isinstance(obj,dict):raise ValueError("unsafe_receipt_type")
        kind="SAFE_METADATA"
    elif name=="ciphertext_sha256.txt":
        if not re.fullmatch(rb"[0-9a-f]{64}\\n?",data):
            raise ValueError("invalid_sha256_file")
        kind="DIGEST"
    else:raise ValueError("unapproved_evidence_extension")
    return data,kind

def main():
    inventory=[]
    files=list(approved_files())
    if len(files)!=18:raise ValueError("expected_evidence_count_18_got_"+str(len(files)))
    # Check parent-source ciphertext before transmitting any archive bytes.
    base=ROOT/"nov22/full12"
    expected=(base/"ciphertext_sha256.txt").read_text().strip()
    actual=hashlib.sha256((base/"originals_all12.tar.gz.aesgcm").read_bytes()).hexdigest()
    if actual!=expected:raise ValueError("REAL_12R_ARCHIVE_SHA_MISMATCH")
    for file in files:
        data,kind=validate(file)
        dest="evidence/2026-11-21_22/"+file.relative_to(ROOT).as_posix()
        sha=hashlib.sha256(data).hexdigest()
        endpoint="contents/"+dest
        prior=api("GET",endpoint+"?ref="+BRANCH)
        if prior is not None:
            existing=base64.b64decode(prior["content"].replace("\n",""))
            if hashlib.sha256(existing).hexdigest()!=sha:
                raise ValueError("ARCHIVE_COLLISION_DIFFERENT_BYTES:"+dest)
            print("EXISTING_BYTE_IDENTICAL",dest,sha)
        else:
            stored=api("PUT",endpoint,{
                "message":"archive immutable Nov21 failure or Nov22 source-proof artifact "+file.name,
                "branch":BRANCH,"content":base64.b64encode(data).decode("ascii")})
            if not stored.get("content",{}).get("sha"):
                raise ValueError("storage_acknowledgment_missing")
            verify=api("GET",endpoint+"?ref="+BRANCH)
            if hashlib.sha256(base64.b64decode(verify["content"].replace("\n",""))).hexdigest()!=sha:
                raise ValueError("ARCHIVED_BYTES_DO_NOT_MATCH")
            print("ARCHIVED_BYTE_IDENTICAL",dest,sha)
        inventory.append({"path":dest,"kind":kind,"size":len(data),"sha256":sha})
    manifest={"schema":"kyoto_encrypted_evidence_archive.v1",
              "source_runs":{"failure":list(RUNS),"all12":44966013490,
                             "g03":44966654858,"ledger":44983258092},
              "day_range":["20261121","20261122"],"files":inventory,
              "real_racecard_originals_12r_proven":True,
              "source_only":True,"markets_unverified":True,
              "plain_html_committed":False}
    payload=(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    mpath="contents/evidence/2026-11-21_22/ARCHIVE_MANIFEST.json"
    old=api("GET",mpath+"?ref="+BRANCH)
    if old is not None:
        if base64.b64decode(old["content"].replace("\n",""))!=payload:
            raise ValueError("MANIFEST_CONFLICT_REVIEW_REQUIRED")
    else:
        api("PUT",mpath,{"message":"final verified Nov21 failures Nov22 successes SHA manifest",
                        "branch":BRANCH,"content":base64.b64encode(payload).decode()})
    Path("evidence_archive_receipt").mkdir(exist_ok=True)
    Path("evidence_archive_receipt/manifest.json").write_bytes(payload)
    print("ARCHIVED_FAILURE_AND_SUCCESS_FILES="+str(len(inventory)))
    print("ARCHIVE_NO_JRA_HTTP_NO_PRODUCTION_CHANGE")

if __name__=="__main__":main()
