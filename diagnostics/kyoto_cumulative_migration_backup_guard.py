"""Fail-closed cumulative Kyoto AI migration backup validator.

A complete handoff must embed the *exact* previous complete archive, add a
new source/history archive and instructions, and pass nested integrity checks.
The verifier never trusts a claimed completeness flag or a file size alone.
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

LEGACY_NAME = "00_PREVIOUS_COMPLETE_21MB_IMPLEMENTATION18.zip"
CURRENT_NAME = "01_LATEST_IMPLEMENTATION19_SOURCE_AND_HISTORY.zip"
INSTRUCTIONS_NAME = "02_IMPLEMENTATION19_MIGRATION_INSTRUCTIONS.md"
PREVIOUS_SHA256 = "3a382d878b21e58ffd6ddfd87689b6f841fdf51d7eb33ebb3aef0b6a7690d1a4"
PREVIOUS_BYTES = 21979816

def sha(data):
    return hashlib.sha256(data).hexdigest()

def safe_zip(data, title):
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        bad = z.testzip()
        if bad:
            raise ValueError(f"{title}: corrupt member {bad}")
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError(f"{title}: duplicate member paths")
        return z
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{title}: invalid ZIP") from exc

def verify(path: Path, expected_previous_sha: str = PREVIOUS_SHA256):
    if not path.is_file():
        raise ValueError("ARCHIVE_MISSING")
    with safe_zip(path.read_bytes(), "outer") as outer:
        names=set(outer.namelist())
        required={"SHA256_MANIFEST.json", "START_HERE.md",LEGACY_NAME,CURRENT_NAME,INSTRUCTIONS_NAME}
        missing=required-names
        if missing:
            raise ValueError(f"CUMULATIVE_CONTENT_MISSING: {sorted(missing)}")
        actual_previous=outer.read(LEGACY_NAME)
        if sha(actual_previous)!=expected_previous_sha:
            raise ValueError("PREVIOUS_COMPLETE_BACKUP_SHA_MISMATCH")
        if len(actual_previous)!=PREVIOUS_BYTES:
            raise ValueError("PREVIOUS_COMPLETE_BACKUP_SIZE_MISMATCH")
        manifest=json.loads(outer.read("SHA256_MANIFEST.json"))
        files=manifest.get("contents")
        if not isinstance(files,dict):
            raise ValueError("CONTENT_MANIFEST_MISSING")
        for name in (LEGACY_NAME,CURRENT_NAME,INSTRUCTIONS_NAME):
            m=files.get(name)
            data=outer.read(name)
            if not isinstance(m,dict) or m.get("sha256")!=sha(data) or m.get("bytes")!=len(data):
                raise ValueError("CONTENT_MANIFEST_MISMATCH:"+name)
        with safe_zip(actual_previous,"previous") as prev:
            pm=json.loads(prev.read("SHA256_MANIFEST.json"))
            for name,digest in pm.items():
                if not isinstance(digest,str) or name not in prev.namelist() or sha(prev.read(name))!=digest:
                    raise ValueError("PREVIOUS_NESTED_MANIFEST_MISMATCH:"+name)
            nested=[name for name in prev.namelist() if name.lower().endswith(".zip")]
            if not nested:
                raise ValueError("PREVIOUS_HISTORICAL_ZIPS_MISSING")
            for name in nested:
                with safe_zip(prev.read(name),name):
                    pass
        with safe_zip(outer.read(CURRENT_NAME),"current") as current:
            required_current={
                "migration19/MANIFEST.json",
                "migration19/START_HERE_MIGRATION_INSTRUCTIONS.md",
                "migration19/source/history/repository-all-refs.bundle",
                "migration19/source/main/app.py",
                "migration19/source/main/docs/KYOTO_AI_20261121_22_FULL_DATA_12_GATE_EXECUTION_TRACKER.md",
                "migration19/source/development/"
            }
            missing_current=[x for x in required_current if
                  (not any(y.startswith(x) for y in current.namelist()) if x.endswith("/")
                   else x not in current.namelist())]
            if missing_current:
                raise ValueError("LATEST_SOURCE_OR_REQUIREMENTS_MISSING:"+str(missing_current))
            cm=json.loads(current.read("migration19/MANIFEST.json"))
            for rel,attrs in cm.get("files",{}).items():
                key="migration19/"+rel
                if key not in current.namelist() or sha(current.read(key))!=attrs.get("sha256"):
                    raise ValueError("LATEST_SOURCE_MANIFEST_MISMATCH:"+key)
            if not cm.get("git_bundle_verified"):
                raise ValueError("GIT_BUNDLE_NOT_VERIFIED")
        text=outer.read(INSTRUCTIONS_NAME).decode("utf-8")
        if "G03" not in text or "G12" not in text or "2/12" not in text:
            raise ValueError("HANDOFF_INSTRUCTIONS_INCOMPLETE")
    return {"status":"PASS","archive":path.name,"sha256":sha(path.read_bytes()),
            "previous_sha256":expected_previous_sha,
            "previous_bytes":PREVIOUS_BYTES,
            "historical_nested_zip_count":len(nested),
            "content_verified":True,"source_bundle_present":True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--previous-sha256",default=PREVIOUS_SHA256)
    p.add_argument("--receipt",type=Path)
    a=p.parse_args()
    try:
        result=verify(a.archive,a.previous_sha256)
    except Exception as exc:
        print("CUMULATIVE_MIGRATION_BACKUP_GATE=FAIL",str(exc),file=sys.stderr)
        raise SystemExit(1)
    if a.receipt:
        a.receipt.parent.mkdir(parents=True,exist_ok=True)
        a.receipt.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("CUMULATIVE_MIGRATION_BACKUP_GATE=PASS")
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
