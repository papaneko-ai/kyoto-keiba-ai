"""Pack G06 nested PC/SP saved originals as one bounded, verifiable payload.

The existing production AES-GCM seals only allowlisted flat source files.
This adapter produces one flat, explicitly named archival payload, then
removes the nested tree only after its bytes and manifest have been checked.
It does NOT authenticate JRA origin; per-race source receipts still do that.
"""
import io,json,hashlib,re,tarfile,shutil
from pathlib import Path

NAME="g06_source_bundle.tar.gz"
MAX_TOTAL=75_000_000
MAX_FILES=600
class BundleError(ValueError):pass
def _accepted(name):
    if not isinstance(name,str) or not re.fullmatch(r"[a-zA-Z0-9_./-]{1,180}",name):
        return False
    parts=name.split("/")
    if ".." in parts or "" in parts or len(parts)>5:return False
    if parts[0]=="next_stage_inboxes":
        return len(parts)==2
    if re.fullmatch(r"r(0[1-9]|1[0-2])",parts[0]):
        return 2<=len(parts)<=5
    return len(parts)==1 and name in ("g06_batch_receipt.json","g06_downstream_input_receipt.json","g06_shared_claim_evidence.json")
def bundle_g06(source,target):
    source,target=Path(source),Path(target)
    if not source.is_dir() or source.is_symlink() or target.exists() or target.is_symlink() or not target.parent.is_dir():
        raise BundleError("source_or_destination_not_fresh")
    entries=sorted(source.rglob("*"))
    if not entries or len(entries)>MAX_FILES+100:raise BundleError("unbounded_source_entries")
    files={};total=0
    for p in entries:
        if p.is_symlink():raise BundleError("symlink_refused")
        if p.is_dir():continue
        if not p.is_file():raise BundleError("nonregular_source")
        name=p.relative_to(source).as_posix()
        if not _accepted(name):raise BundleError("unexpected_original_path")
        raw=p.read_bytes()
        total+=len(raw)
        if len(raw)>1_500_000 or total>MAX_TOTAL:raise BundleError("source_size_limit")
        files[name]=raw
    if "g06_batch_receipt.json" not in files:
        raise BundleError("batch_receipt_missing")
    if len(files)>MAX_FILES:raise BundleError("too_many_originals")
    manifest={"schema":"kyoto_g06_nested_bundle.v1","source_kind":"OFFICIAL_OR_SYNTHETIC_AS_RECEIPTS_PROVE",
        "files":{name:{"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
                 for name,raw in files.items()},"source_file_count":len(files),
        "prediction_ready":False}
    files["g06_bundle_manifest.json"]=(json.dumps(manifest,ensure_ascii=False,sort_keys=True)+"\n").encode()
    with target.open("xb") as output:
        with tarfile.open(fileobj=output,mode="w:gz") as archive:
            for name,raw in sorted(files.items()):
                entry=tarfile.TarInfo(name)
                entry.size=len(raw)
                entry.mtime=0
                archive.addfile(entry,io.BytesIO(raw))
    if target.stat().st_size>MAX_TOTAL:
        target.unlink()
        raise BundleError("compressed_source_size_limit")
    verify_bundle(target)
    shutil.rmtree(source)
    return {"state":"G06_BUNDLE_STAGED_FOR_EXISTING_AES_GCM",
            "source_file_count":len(manifest["files"]),
            "bundle_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
            "plaintext_uploaded":False}
def verify_bundle(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_TOTAL:
        raise BundleError("invalid_bundle")
    data={}
    extracted_total=0
    with tarfile.open(path,mode="r:gz") as tar:
        members=tar.getmembers()
        if len(members)>MAX_FILES+1:raise BundleError("unbounded_tar_members")
        for m in members:
            if not m.isfile() or not _accepted(m.name) and m.name!="g06_bundle_manifest.json":
                raise BundleError("unsafe_member")
            if m.size < 0 or m.size > 1_500_000:
                raise BundleError("oversized_member")
            # The producer enforces 75 MB total. The verifier must enforce
            # the same bound on extracted bytes, not just compressed bytes.
            extracted_total+=m.size
            if extracted_total>MAX_TOTAL+1_500_000:
                raise BundleError("unbounded_extracted_total")
            raw=tar.extractfile(m).read(1_500_001)
            if len(raw)!=m.size or len(raw)>1_500_000:
                raise BundleError("member_size_mismatch")
            if m.name in data:raise BundleError("duplicate_member")
            data[m.name]=raw
    try:manifest=json.loads(data.pop("g06_bundle_manifest.json"))
    except (KeyError,ValueError) as exc:raise BundleError("missing_bundle_manifest") from exc
    if sum(len(raw) for raw in data.values())>MAX_TOTAL:
        raise BundleError("unbounded_original_total")
    if manifest.get("schema")!="kyoto_g06_nested_bundle.v1" or set(manifest.get("files",{}))!=set(data):
        raise BundleError("bundle_file_set_mismatch")
    for name,raw in data.items():
        proof=manifest["files"][name]
        if len(raw)!=proof["bytes"] or hashlib.sha256(raw).hexdigest()!=proof["sha256"]:
            raise BundleError("bundle_original_tampered")
    return {"verified_file_count":len(data),"bundle_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}

def bundle_interrupted_g06(source,target):
    """Seal partial G06 originals after an interrupted batch, without success claims.

    Only the absence of the final batch receipt is repairable here. Other
    bundle/integrity failures remain fail-closed. The synthetic *failure*
    receipt has no markets, does not certify an individual race, and is
    carried within the existing AES-GCM encrypted G06 bundle.
    """
    source=Path(source)
    if source.is_symlink() or not source.is_dir():
        raise BundleError("unsafe_interrupted_source")
    if (source/"g06_batch_receipt.json").exists():
        raise BundleError("not_an_interrupted_batch")
    files=[p for p in source.rglob("*") if p.is_file()]
    if not files:
        raise BundleError("no_partial_originals")
    for p in source.rglob("*"):
        if p.is_symlink() or (not p.is_file() and not p.is_dir()):
            raise BundleError("unsafe_interrupted_entry")
        if p.is_file() and not _accepted(p.relative_to(source).as_posix()):
            raise BundleError("unexpected_partial_original")
    failure={
        "schema":"kyoto_g06_interrupted_batch_failure.v1",
        "state":"INTERRUPTED_BATCH_PARTIAL_ORIGINALS_ONLY",
        "total_races":12,
        "verified_dual_market_races":0,
        "all_twelve_source_originals_verified":False,
        "per_race_verification_not_completed":True,
        "prediction_ready":False,
        "actual_wager_authorized":False,
        "records":[],
    }
    path=source/"g06_batch_receipt.json"
    with path.open("x",encoding="utf8") as out:
        json.dump(failure,out,sort_keys=True,ensure_ascii=False)
        out.write("\n")
    try:
        result=bundle_g06(source,target)
    except Exception:
        # Keep saved source files on failure; never silently discard the only
        # partial originals. The sealing step must fail closed.
        raise
    result["state"]="G06_INTERRUPTED_ORIGINALS_BUNDLED_UNVERIFIED"
    result["verified_dual_market_races"]=0
    return result
