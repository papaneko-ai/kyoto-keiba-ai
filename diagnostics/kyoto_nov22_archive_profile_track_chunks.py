"""Durably retain Nov22 profile 185 and track AES originals with chunk hashes.

Only ciphertext and safe receipts. 512 KiB parts allow GitHub Contents API
read-back verification, even when an encrypted bundle exceeds 1 MiB.
Append-only; never overwrite divergent existing evidence.
"""
import base64,hashlib,json,os,subprocess
from pathlib import Path
REPO=os.environ["GITHUB_REPOSITORY"]
BRANCH="archive/kyoto-ai-encrypted-original-evidence"
PREFIX="evidence/2026-11-21_22/nov22"
PART=512*1024
ITEMS={
 "profile/horse_profiles.tar.gz.aesgcm":"horse_profiles/horse_profiles.tar.gz.aesgcm",
 "profile/ciphertext_sha256.txt":"horse_profiles/ciphertext_sha256.txt",
 "profile/safe_profile_receipt.json":"horse_profiles/safe_profile_receipt.json",
 "track/ground_original.tar.gz.aesgcm":"track/ground_original.tar.gz.aesgcm",
 "track/source_sha256.txt":"track/source_sha256.txt",
 "track/safe_track_receipt.json":"track/safe_track_receipt.json",
}
def api(method,path,body=None):
    cmd=["gh","api","-X",method,f"repos/{REPO}/contents/{path}"]
    if body is not None:cmd+=["--input","-"]
    p=subprocess.run(cmd,input=json.dumps(body) if body is not None else None,
                     text=True,capture_output=True)
    if p.returncode:
        if method=="GET" and "404" in p.stderr:return None
        raise RuntimeError("EVIDENCE_API_ERROR:"+p.stderr[:250])
    return json.loads(p.stdout)
def append(target,blob):
    sha=hashlib.sha256(blob).hexdigest()
    existing=api("GET",target+"?ref="+BRANCH)
    if existing is None:
        api("PUT",target,{"branch":BRANCH,
            "message":"append-only Nov22 official ciphertext or exact evidence receipt",
            "content":base64.b64encode(blob).decode()})
        existing=api("GET",target+"?ref="+BRANCH)
    if existing is None or hashlib.sha256(base64.b64decode(existing["content"])).hexdigest()!=sha:
        raise ValueError("ARCHIVE_READBACK_MISMATCH_OR_COLLISION")
    return sha
def main():
    files=[]
    root=Path("to_archive")
    for source,dest in ITEMS.items():
        raw=(root/source).read_bytes()
        if len(raw)==0 or len(raw)>50_000_000:raise ValueError("INVALID_ARCHIVE_BYTE_SIZE")
        if source.endswith(".json"):json.loads(raw.decode("utf8"))
        if source.endswith(".txt") and not raw.decode("ascii").strip():
            raise ValueError("EMPTY_SHA_RECEIPT")
        base=PREFIX+"/"+dest
        parts=[raw[x:x+PART] for x in range(0,len(raw),PART)]
        chunklist=[]
        for i,fragment in enumerate(parts):
            path=f"{base}.chunk{i:03d}"
            sha=append(path,fragment)
            chunklist.append({"path":path,"sha256":sha,"size":len(fragment)})
        files.append({"file":base,"original_size":len(raw),
                      "original_sha256":hashlib.sha256(raw).hexdigest(),
                      "chunks":chunklist})
    for family,body,digest in (("profile","horse_profiles.tar.gz.aesgcm","ciphertext_sha256.txt"),
                               ("track","ground_original.tar.gz.aesgcm","source_sha256.txt")):
        raw=(root/family/body).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==(root/family/digest).read_text().strip()
    manifest={"schema":"kyoto_nov22_profile_track_recoverable_chunks.v1",
              "day":"20261122","profile_run":44984067104,"track_run":44984408658,
              "files":files,"ciphertext_only":True,
              "profile_count_claim_source_only":185,
              "horse_history_fields_verified":False,
              "track_fields_verified":False}
    data=(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    append(PREFIX+"/PROFILE_TRACK_APPEND_ONLY_MANIFEST.json",data)
    print("APPEND_ONLY_VERIFIED_PROFILE_TRACK_FILES="+str(len(files)))
    print("APPEND_ONLY_VERIFIED_CHUNKS="+str(sum(len(x["chunks"]) for x in files)))
    print("RECONSTRUCTION_ORIGINAL_SHA256_RECORDED")
if __name__=="__main__":main()
