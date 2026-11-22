"""Archive only encrypted source and safe receipts, append-only in GitHub evidence branch.

No source-site HTTP. Never commit plaintext HTML, tokens, or AES keys.
"""
import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path

EVIDENCE_BRANCH="archive/kyoto-ai-encrypted-original-evidence"
REPO=os.environ["GITHUB_REPOSITORY"]
ROOT=Path("evidence_intake")
ALLOWED_EXT=(".aesgcm",".json",".txt")
MAX_FILE=2_000_000

def gh(*args,input=None):
    result=subprocess.run(["gh","api",*args],input=input,
                          capture_output=True,text=True,check=False)
    if result.returncode!=0:
        raise RuntimeError("github_archive_api_failure:"+result.stderr[:200])
    return json.loads(result.stdout) if result.stdout else {}

def classify(name):
    if name.endswith(".aesgcm"):return "ENCRYPTED_SOURCE"
    if name.endswith(".json"):return "SAFE_RECEIPT"
    if name.endswith(".txt"):return "DIGEST_TEXT"
    raise ValueError("unapproved_archive_extension")

def main():
    inventory=[]
    for area in ("nov21_failure_evidence","nov22_real_all12",
                 "nov22_g03","nov22_family_ledger"):
        folder=ROOT/area
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("missing_evidence_bundle:"+area)
        files=sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink())
        if not files:raise ValueError("empty_evidence_bundle:"+area)
        for file in files:
            kind=classify(file.name)
            if area=="nov22_real_all12" and file.name=="originals_all12.tar.gz.aesgcm":
                pass
            elif kind=="ENCRYPTED_SOURCE":
                pass
            elif kind=="SAFE_RECEIPT" and file.stat().st_size<=MAX_FILE:
                obj=json.loads(file.read_text(encoding="utf8"))
                if not isinstance(obj,(dict,list)):
                    raise ValueError("unsafe_receipt_shape")
            elif kind=="DIGEST_TEXT" and file.stat().st_size<=MAX_FILE:
                raw=file.read_text(encoding="utf8")
                if not raw.strip() or len(raw)>1500:
                    raise ValueError("invalid_digest_receipt")
            else:
                raise ValueError("file_not_approved")
            data=file.read_bytes()
            if not 0<len(data)<=MAX_FILE:
                raise ValueError("file_size_outside_limit")
            sha=hashlib.sha256(data).hexdigest()
            path=f"evidence/2026-11-21_22/{area}/{file.name}"
            # No 'sha' parameter: server must reject overwrites (409/422).
            gh("-X","PUT",f"repos/{REPO}/contents/{path}",
               "-f","message=archive encrypted 2026-11-21_22 evidence "+area,
               "-f","branch="+EVIDENCE_BRANCH,
               "-f","content="+base64.b64encode(data).decode("ascii"))
            inventory.append({"path":path,"kind":kind,"size":len(data),"sha256":sha})
            print("APPEND_ONLY_ARCHIVE_PASS",area,file.name,sha)
    manifest={"schema":"kyoto_archived_protected_originals.v1",
              "day_range":["20261121","20261122"],
              "immutable_source_run":44966013490,
              "failure_source_runs":[44848944302,44854931835,44857934629,44861934823],
              "g03_source_run":44966654858,
              "ledger_source_run":44983258092,
              "files":inventory,
              "no_plaintext_html_committed":True,
              "no_jra_http":True,
              "audit_required_for_key_restoration":True}
    content=json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2).encode()+b"\n"
    gh("-X","PUT",f"repos/{REPO}/contents/evidence/2026-11-21_22/ARCHIVE_MANIFEST.json",
       "-f","message=fix archive manifest and immutable SHA256 for Nov21 failures and Nov22 source success",
       "-f","branch="+EVIDENCE_BRANCH,
       "-f","content="+base64.b64encode(content).decode("ascii"))
    Path("evidence_archive_receipt").mkdir(exist_ok=True)
    Path("evidence_archive_receipt/manifest.json").write_bytes(content)
    print("ARCHIVED_EVIDENCE_FILES",len(inventory))
    print("ARCHIVED_SOURCE_ONLY_UNVERIFIED_MARKETS")

if __name__=="__main__":main()
