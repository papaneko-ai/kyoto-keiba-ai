"""Isolate a bad source member and recover independently readable original bytes.

The strict archive path remains unchanged. Recovery never reads unknown files
or follows symlinks, never overwrites an original, never assigns source credit.
Only a fresh, encrypted, independently round-tripped archive is published.
"""
import hashlib,json,os,re,stat,tempfile,shutil
from pathlib import Path

class SalvageRejected(ValueError):pass

def _sha(b):return hashlib.sha256(b).hexdigest()
def _read_regular(path,cap):
    # No symlink traversal at the final component, no unbounded reads.
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        with os.fdopen(fd,"rb") as f:
            fd=None
            a=os.fstat(f.fileno())
            if not stat.S_ISREG(a.st_mode) or not 0<=a.st_size<=cap:
                raise SalvageRejected("unsafe_or_oversize_member")
            raw=f.read(cap+1)
            b=os.fstat(f.fileno())
            if len(raw)!=a.st_size or len(raw)>cap or (a.st_size,a.st_mtime_ns)!=(b.st_size,b.st_mtime_ns):
                raise SalvageRejected("member_changed_during_read")
            return raw
    finally:
        if fd is not None:os.close(fd)

def salvage(source,destination,*,day,key,repo,run_id,strict_error):
    from diagnostics.kyoto_nov15_encrypted_evidence import FILES,_file_cap,encrypt_evidence,decrypt_evidence
    from diagnostics.kyoto_g06_nested_bundle import verify_bundle,bundle_g06,bundle_interrupted_g06,_accepted
    src,dst=Path(source),Path(destination)
    if day not in ("20261128","20261129") or not src.is_dir() or src.is_symlink() or dst.exists() or dst.is_symlink():
        raise SalvageRejected("invalid_salvage_boundary")
    candidates={};rejected=[];g06_entries=[]
    def reject(p,reason):
        relative=p.relative_to(src).as_posix()
        rejected.append({"path_sha256":_sha(relative.encode()),"reason":reason})
    def add(p,name):
        if p.is_symlink() or not p.is_file():reject(p,"NONREGULAR");return
        if name not in FILES or name=="archive_pre_salvage_receipt.json":
            reject(p,"UNRECOGNIZED");return
        candidates.setdefault(name,[]).append(p)
    for p in sorted(src.iterdir()):
        if p.is_symlink():reject(p,"SYMLINK");continue
        if p.is_file():add(p,p.name);continue
        if not p.is_dir():reject(p,"NONREGULAR");continue
        if p.name=="g06_unsealed":
            for parent,dirs,files in os.walk(p,followlinks=False):
                parent=Path(parent)
                for name in list(dirs):
                    child=parent/name
                    if child.is_symlink():reject(child,"SYMLINK");dirs.remove(name)
                for name in sorted(files):
                    child=parent/name
                    relative=child.relative_to(p).as_posix()
                    if child.is_symlink() or not child.is_file() or not _accepted(relative):reject(child,"UNSAFE_G06_MEMBER")
                    else:g06_entries.append((relative,child))
                if len(g06_entries)+len(rejected)>900:raise SalvageRejected("source_entry_limit")
            continue
        stage=re.fullmatch(r"sp_stage_(0[1-9]|1[0-2])",p.name)
        if p.name not in ("pc_originals","sp_discovery") and not stage:
            reject(p,"UNKNOWN_STAGE");continue
        for item in sorted(p.iterdir()):
            if p.name=="pc_originals":name="observer_partial_receipt.json" if item.name=="receipt.json" else item.name
            elif p.name=="sp_discovery":
                name=item.name
                if not re.fullmatch(r"official_sp_discovery_[1-6]\.html|sp_discovery_receipt\.json",name):
                    reject(item,"UNRECOGNIZED_DISCOVERY");continue
            else:name=f"r{stage.group(1)}_{item.name}"
            add(item,name)
    if sum(map(len,candidates.values()))+len(rejected)>900:raise SalvageRejected("source_entry_limit")
    with tempfile.TemporaryDirectory(prefix="kyoto_salvage_",dir=dst.parent) as tmp:
        tmp=Path(tmp);stage=tmp/"stage";stage.mkdir();saved={};total=0
        for name,paths in sorted(candidates.items()):
            if len(paths)!=1:
                for p in paths:reject(p,"COLLISION")
                continue
            p=paths[0]
            try:raw=_read_regular(p,_file_cap(name))
            except (OSError,SalvageRejected):reject(p,"UNREADABLE_OR_OVERSIZE");continue
            total+=len(raw)
            if total>180_000_000:raise SalvageRejected("source_byte_limit")
            dest="archive_pre_salvage_receipt.json" if name=="receipt.json" else name
            (stage/dest).write_bytes(raw)
            if name=="g06_source_bundle.tar.gz":
                try:verify_bundle(stage/dest)
                except Exception:
                    (stage/dest).unlink();reject(p,"INVALID_G06_BUNDLE");continue
            saved[dest]={"sha256":_sha(raw),"bytes":len(raw)}
        if g06_entries:
            if "g06_source_bundle.tar.gz" in saved:
                for _,p in g06_entries:reject(p,"G06_DUPLICATE_STAGE")
            else:
                g06=tmp/"g06";g06.mkdir()
                for relative,p in sorted(g06_entries):
                    try:raw=_read_regular(p,1_500_000)
                    except (OSError,SalvageRejected):reject(p,"UNREADABLE_G06_MEMBER");continue
                    total+=len(raw)
                    if total>180_000_000:raise SalvageRejected("source_byte_limit")
                    target=g06/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
                target=stage/"g06_source_bundle.tar.gz"
                if any(p.is_file() for p in g06.rglob("*")):
                    try:
                        if (g06/"g06_batch_receipt.json").is_file():bundle_g06(g06,target)
                        else:bundle_interrupted_g06(g06,target)
                        verify_bundle(target)
                        raw=target.read_bytes();saved[target.name]={"sha256":_sha(raw),"bytes":len(raw)}
                    except Exception:
                        if target.exists():target.unlink()
                        for _,p in g06_entries:reject(p,"G06_BUNDLE_UNVERIFIED")
        if not saved:raise SalvageRejected("no_recoverable_originals")
        receipt={"schema":"kyoto_archive_salvage.v1","day":day,
                 "state":"PARTIAL_ARCHIVE_SALVAGED_NOT_SOURCE_VERIFIED",
                 "strict_error_class":strict_error,"actual_http_attempts":"UNKNOWN",
                 "source_verified":False,"both_markets_verified":False,"prediction_ready":False,
                 "saved_originals":saved,"rejected_members":sorted(rejected,key=lambda x:(x["path_sha256"],x["reason"])),
                 "original_tree_deleted":False}
        (stage/"receipt.json").write_text(json.dumps(receipt,sort_keys=True)+"\n",encoding="utf8")
        encrypted=tmp/"encrypted";restored=tmp/"restored"
        result=encrypt_evidence(stage,encrypted,key_hex=key,repo=repo,run_id=run_id)
        decrypt_evidence(encrypted,restored,key_hex=key,repo=repo,run_id=run_id)
        if {p.name:_sha(p.read_bytes()) for p in stage.iterdir()}!={p.name:_sha(p.read_bytes()) for p in restored.iterdir()}:
            raise SalvageRejected("independent_roundtrip_mismatch")
        if dst.exists() or dst.is_symlink():raise SalvageRejected("destination_collision")
        encrypted.rename(dst)
        result.update(salvage_receipt=receipt,roundtrip_verified=True)
        return result
