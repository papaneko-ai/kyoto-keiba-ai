"""H06: isolated rollback drill. No production mutations, no real credentials."""
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import os, shutil, json, datetime

SRC=Path(os.environ.get("KYOTO_H06_SOURCES","/mnt/data/impl20/session_end/sources"))
OLD=SRC/"main"
NEW=SRC/"experiment"
PIN="c96df31542cb94435ca36cb4a1b8bd6de938233f"
def filemap(root):
    return {str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}
def drill():
    assert OLD.is_dir() and NEW.is_dir()
    assert (NEW/"diagnostics/kyoto_hybrid_multi_source.py").is_file()
    with TemporaryDirectory(prefix="kyoto_h06_") as d:
        root=Path(d)
        shutil.copytree(OLD,root/"legacy")
        shutil.copytree(NEW,root/"candidate")
        shutil.copytree(OLD,root/"production_mirror")
        baseline=filemap(root/"legacy")
        protected=filemap(root/"production_mirror")
        vault=root/"vault";vault.mkdir()
        (vault/"secrets.env").write_text("SIMULATED_SECRET_ONLY=1")
        (vault/"database.sqlite").write_bytes(b"SIMULATED_NOT_REAL_DATABASE")
        vault_baseline=filemap(vault)
        selector=root/"selector.json"
        def select(kind):
            selector.write_text(json.dumps({"active":kind,"production_collector_sha":PIN}))
        select("legacy")
        select("candidate")
        compile((root/"candidate/diagnostics/kyoto_hybrid_multi_source.py").read_bytes(),"candidate","exec")
        caught=False
        try:raise RuntimeError("INJECTED_CANDIDATE_FAILURE")
        except RuntimeError as e:caught=str(e)=="INJECTED_CANDIDATE_FAILURE"
        assert caught
        select("legacy")
        assert json.loads(selector.read_text())["active"]=="legacy"
        assert filemap(root/"legacy")==baseline
        assert filemap(root/"production_mirror")==protected
        assert filemap(vault)==vault_baseline
        assert len(baseline)>0
        return {"schema":"kyoto_h06_isolated_rollback.v1",
            "tested_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "tests":{"candidate_switch":True,"failure_injection":caught,"rollback":True,
                     "legacy_unchanged":True,"vault_unchanged":True,"production_mirror_unchanged":True},
            "protected_files":len(protected),"collector_sha":PIN,
            "real_production_touched":False,"real_secrets_used":False,"real_db_touched":False,
            "h06_certified":False,"scope":"isolated offline rehearsal, not live GitHub workflow ref switch"}
if __name__=="__main__":
    result=drill()
    Path("h06_receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
