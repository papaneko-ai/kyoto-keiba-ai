"""EOD backup: GitHub artifact archives only; never contacts JRA."""
from pathlib import Path
import hashlib,json,os,subprocess,tarfile,zipfile
manifest=json.loads(Path("diagnostics/eod_20261106_original_artifacts_manifest.json").read_text())
root=Path("eod_backup")
root.mkdir(exist_ok=False)
source=root/"available_originals"
source.mkdir()
receipts=[]
for x in manifest["groups"]:
    folder=source/("%02d"%x["index"])
    folder.mkdir()
    cmd=["gh","run","download",str(x["run_id"]),"--name",x["name"],
         "--repo","papaneko-ai/kyoto-keiba-ai","--dir",str(folder)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    files=list(folder.rglob("*"))
    count=sum(p.is_file() for p in files)
    receipts.append({"index":x["index"],"run_id":x["run_id"],
        "name":x["name"],"file_count":count,"download_ok":result.returncode==0,
        "error":result.stderr[-250:] if result.returncode else ""})
    if result.returncode!=0 or count==0:
        Path("eod_backup_failures.json").write_text(json.dumps(receipts,indent=2))
        raise SystemExit("Missing evidence artifact: "+x["name"])
snapshot=root/"git_snapshot.zip"
with snapshot.open("wb") as out:
    subprocess.run(["git","archive","--format=zip","HEAD"],check=True,stdout=out)
sources=root/"source_originals.tar.gz"
with tarfile.open(sources,"w:gz") as tar:
    tar.add(source,arcname="official_originals")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record={"schema":"kyoto_eod_final_bundle.v1","snapshot_sha":manifest["snapshot_commit"],
        "archive_git_sha256":sha(snapshot),"archive_sources_sha256":sha(sources),
        "artifact_groups":receipts,"artifact_groups_downloaded":len(receipts),
        "actual_jra_http_requests":0,
        "original_sources_completeness":"ONLY_AVAILABLE_PREVIOUSLY_CAPTURED_ARTIFACTS",
        "prediction_ready":False,"training_ready":False}
(root/"integrity_manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
with zipfile.ZipFile(root/"kyoto_ai_20261106_eod_complete_bundle.zip","w",compression=zipfile.ZIP_DEFLATED) as z:
    for item in (snapshot,sources,root/"integrity_manifest.json"):
        z.write(item,arcname=item.name)
print(json.dumps({"backup_zip":str(root/"kyoto_ai_20261106_eod_complete_bundle.zip"),
   "artifact_groups":len(receipts),"source_archive_sha":record["archive_sources_sha256"]}))
