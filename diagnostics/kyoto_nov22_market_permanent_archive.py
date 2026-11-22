"""Append-only archive of actual Nov22 JRA market originals and verified receipts."""
import base64,hashlib,json,os,subprocess
from pathlib import Path
REPO=os.environ["GITHUB_REPOSITORY"]
BRANCH="archive/kyoto-ai-encrypted-original-evidence"
FILES={
 "market/market_followup.tar.gz.aesgcm":"actual/market_followup.tar.gz.aesgcm",
 "market/encrypted_sha256.txt":"actual/encrypted_sha256.txt",
 "market/safe_market_receipt.json":"actual/safe_market_receipt.json",
 "independent/market_original_independent_receipt.json":"verification/market_original_independent_receipt.json",
 "numeric/market_numeric_replay.json":"verification/market_numeric_replay.json"
}
def gh(op,path,body=None):
    cmd=["gh","api","-X",op,f"repos/{REPO}/contents/{path}"]
    if body is not None:cmd+=["--input","-"]
    p=subprocess.run(cmd,input=json.dumps(body) if body is not None else None,
                     text=True,capture_output=True)
    if p.returncode:
        if op=="GET" and "404" in p.stderr:return None
        raise RuntimeError("GITHUB_ARCHIVE_API_ERROR:"+p.stderr[:200])
    return json.loads(p.stdout)
def main():
    result=[]
    for src,dest in FILES.items():
        raw=Path("market_to_archive")/src
        if not raw.is_file() or raw.is_symlink():raise ValueError("REQUIRED_MARKET_EVIDENCE_MISSING:"+src)
        data=raw.read_bytes()
        if not 0<len(data)<1500000:raise ValueError("MARKET_EVIDENCE_BAD_SIZE")
        if src.endswith(".json"):json.loads(data.decode("utf8"))
        sha=hashlib.sha256(data).hexdigest()
        target=f"evidence/2026-11-21_22/nov22/paired_markets/{dest}"
        old=gh("GET",target+"?ref="+BRANCH)
        if old is not None:
            existing=base64.b64decode(old["content"].replace("\n",""))
            if hashlib.sha256(existing).hexdigest()!=sha:raise ValueError("IMMUTABLE_ARCHIVE_CONFLICT")
        else:
            gh("PUT",target,{"branch":BRANCH,"message":"preserve independently verified JRA market original evidence "+src,
                             "content":base64.b64encode(data).decode()})
            readback=gh("GET",target+"?ref="+BRANCH)
            if hashlib.sha256(base64.b64decode(readback["content"].replace("\n",""))).hexdigest()!=sha:
                raise ValueError("READBACK_SHA_DIFFERENCE")
        result.append({"path":target,"sha256":sha,"size":len(data)})
    print("DURABLY_ARCHIVED_ACTUAL_MARKET_FILES="+str(len(result)))
    print("NO_MARKET_NUMERIC_FALSE_CERTIFICATION")
if __name__=="__main__":main()
