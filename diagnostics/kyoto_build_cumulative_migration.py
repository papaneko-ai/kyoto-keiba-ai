"""Build next cumulative migration ZIP from prior verified archive and latest source ZIP.

Examples:
  python -m diagnostics.kyoto_build_cumulative_migration \
    --previous previous_complete.zip --latest new_source.zip \
    --instructions HANDOFF.md --output NEXT_COMPLETE.zip

No file is considered COMPLETE unless the chain guard passes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from diagnostics.kyoto_backup_chain_guard import verify,check_zip,check_manifest

def sha(data):
    return hashlib.sha256(data).hexdigest()

def build(previous: Path, latest: Path, instructions: Path, output: Path):
    if output in (previous,latest,instructions):
        raise ValueError("OUTPUT_CANNOT_OVERWRITE_INPUT")
    pdata=previous.read_bytes()
    ldata=latest.read_bytes()
    guide=instructions.read_bytes()
    with check_zip(pdata,"previous") as z:
        check_manifest(z)
    with check_zip(ldata,"latest") as z:
        if not z.namelist():
            raise ValueError("NEW_ZIP_EMPTY")
    if not guide or len(guide)<60:
        raise ValueError("INSTRUCTIONS_MISSING_OR_TOO_SHORT")
    entries={
        "00_PREVIOUS_COMPLETE_BACKUP.zip":pdata,
        "01_LATEST_SOURCE_AND_EVIDENCE.zip":ldata,
        "02_NEW_MIGRATION_INSTRUCTIONS.md":guide,
        "START_HERE.md":(
            "# Kyoto AI cumulative migration\n\n"
            "Read 02_NEW_MIGRATION_INSTRUCTIONS.md first.\n"
            "The prior complete archive is embedded verbatim.\n"
            "Do not confuse external credentials/artifacts with included files.\n"
            ).encode(),
    }
    manifest={"schema":"kyoto_ai_cumulative_v2","previous_filename":previous.name,
        "previous_archive_sha256":sha(pdata),
        "source_filename":latest.name,
        "contents":{name:{"bytes":len(data),"sha256":sha(data)}
                    for name,data in entries.items()}}
    entries["SHA256_MANIFEST.json"]=(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    if output.exists():
        raise FileExistsError("OUTPUT_ALREADY_EXISTS")
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_name(output.name+".incomplete")
    try:
        with zipfile.ZipFile(temp,"w",zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for name,data in entries.items():
                z.writestr(name,data)
        # The verifier insists on the .zip suffix.
        staging=output.with_name(output.stem+".verify.zip")
        if staging.exists():
            raise FileExistsError("STAGING_ALREADY_EXISTS")
        temp.replace(staging)
        try:
            receipt=verify(staging,previous)
        except Exception:
            staging.unlink(missing_ok=True)
            raise
        staging.replace(output)
        receipt["output_name"]=output.name
        receipt_path=output.with_name(output.stem+"_VERIFICATION.json")
        receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
        return receipt
    finally:
        temp.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--previous",type=Path,required=True)
    p.add_argument("--latest",type=Path,required=True)
    p.add_argument("--instructions",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    r=build(a.previous,a.latest,a.instructions,a.output)
    print("CUMULATIVE_NEW_BACKUP_VERIFIED")
    print(json.dumps(r,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":
    main()
