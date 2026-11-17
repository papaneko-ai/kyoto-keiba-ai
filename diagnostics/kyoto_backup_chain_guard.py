"""General-purpose cumulative migration verifier: each new archive contains exact prior ZIP.

Usage: python -m diagnostics.kyoto_backup_chain_guard NEW.zip --previous PREVIOUS.zip
This must PASS before a migration ZIP is labeled COMPLETE or uploaded.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def check_zip(data: bytes, context: str):
    try:
        z=zipfile.ZipFile(io.BytesIO(data))
        if z.testzip() is not None:
            raise ValueError(context+": CRC_CHECK_FAILED")
        names=z.namelist()
        if len(names)!=len(set(names)):
            raise ValueError(context+": DUPLICATE_MEMBER")
        if any(n.startswith("/") or ".." in n.split("/") for n in names):
            raise ValueError(context+": UNSAFE_MEMBER_PATH")
        return z
    except zipfile.BadZipFile as exc:
        raise ValueError(context+": NOT_ZIP") from exc

def check_manifest(z):
    candidates=[n for n in z.namelist() if n.rsplit("/",1)[-1]=="SHA256_MANIFEST.json"]
    if not candidates:
        raise ValueError("SHA256_MANIFEST_MISSING")
    raw=json.loads(z.read(candidates[0]))
    mapping=raw.get("contents",raw)
    if not isinstance(mapping,dict) or not mapping:
        raise ValueError("MANIFEST_EMPTY")
    for name,record in mapping.items():
        if name not in z.namelist():
            raise ValueError("MANIFEST_MEMBER_MISSING:"+name)
        data=z.read(name)
        expected=record.get("sha256") if isinstance(record,dict) else record
        if digest(data)!=expected:
            raise ValueError("MANIFEST_SHA_MISMATCH:"+name)
        if isinstance(record,dict) and record.get("bytes")!=len(data):
            raise ValueError("MANIFEST_LENGTH_MISMATCH:"+name)
    return raw

def verify(child_path: Path, previous_path: Path):
    previous=previous_path.read_bytes()
    child=child_path.read_bytes()
    with check_zip(previous,"previous") as pz:
        check_manifest(pz)
    with check_zip(child,"child") as cz:
        manifest=check_manifest(cz)
        matches=[n for n in cz.namelist() if n.endswith(".zip") and
                 digest(cz.read(n))==digest(previous) and len(cz.read(n))==len(previous)]
        if len(matches)!=1:
            raise ValueError("PREVIOUS_ZIP_MISSING_OR_ALTERED")
        new_zips=[n for n in cz.namelist() if n.endswith(".zip") and n not in matches]
        if not new_zips:
            raise ValueError("NEW_SOURCE_OR_WORK_ZIP_MISSING")
        for n in new_zips:
            with check_zip(cz.read(n),"new:"+n) as nested:
                if not nested.namelist():
                    raise ValueError("NEW_ZIP_EMPTY")
        if not any(n.lower().endswith((".md",".txt")) for n in cz.namelist()):
            raise ValueError("HANDOFF_INSTRUCTIONS_MISSING")
        if not any("START_HERE" in n.upper() for n in cz.namelist()):
            raise ValueError("ENTRYPOINT_MISSING")
        if not child_path.name.endswith(".zip"):
            raise ValueError("NOT_ZIP_SUFFIX")
        return {"result":"PASS","new_sha256":digest(child),
                "previous_sha256":digest(previous),
                "previous_embedded_as":matches[0],
                "new_zip_count":len(new_zips),
                "new_bytes":len(child),"previous_bytes":len(previous),
                "all_manifest_entries_verified":True,
                "crc_integrity":True}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("new",type=Path)
    ap.add_argument("--previous",type=Path,required=True)
    ap.add_argument("--receipt",type=Path)
    a=ap.parse_args()
    try:
        result=verify(a.new,a.previous)
        if a.receipt:
            a.receipt.parent.mkdir(parents=True,exist_ok=True)
            a.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
        print("CUMULATIVE_BACKUP_CHAIN_PASS")
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    except Exception as exc:
        print("CUMULATIVE_BACKUP_CHAIN_FAIL: "+str(exc),file=sys.stderr)
        raise SystemExit(1)

if __name__=="__main__":
    main()
