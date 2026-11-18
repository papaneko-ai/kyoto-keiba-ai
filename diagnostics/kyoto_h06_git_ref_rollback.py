"""Verify bidirectional Git ref switching using an isolated Git repo (no production writes)."""
import subprocess,tempfile,json,hashlib,os,datetime
from pathlib import Path
def git(*args,cwd=None):
    p=subprocess.run(["git",*args],cwd=cwd,check=False,text=True,capture_output=True)
    if p.returncode:
        where=subprocess.run(["git","show-ref"],cwd=cwd,check=False,text=True,capture_output=True)
        raise RuntimeError(f"git command failed {args} cwd={cwd} stdout={p.stdout!r} stderr={p.stderr!r} refs={where.stdout!r} referr={where.stderr!r}")
    return p.stdout.strip()
def hashes(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file() and ".git" not in p.parts}
def run():
    root=Path(os.environ["KYOTO_H06_SOURCES"]).resolve()
    old=root/"main";new=root/"experiment"
    assert (old/".git").exists() and (new/".git").exists()
    old_files=hashes(old);new_files=hashes(new)
    with tempfile.TemporaryDirectory(prefix="kyoto_h06_git_") as d:
        work=Path(d)/"sandbox"
        git("init","-q",str(work))
        git("fetch","-q",str(old),"HEAD:refs/heads/h06-old",cwd=work)
        old_sha=git("rev-parse","refs/heads/h06-old",cwd=work)
        git("fetch","-q",str(new),"HEAD:refs/heads/h06-new",cwd=work)
        new_sha=git("rev-parse","refs/heads/h06-new",cwd=work)
        assert old_sha!=new_sha
        ref="refs/heads/isolated-selected-collector"
        git("update-ref",ref,old_sha,cwd=work)
        assert git("rev-parse",ref,cwd=work)==old_sha
        git("update-ref",ref,new_sha,old_sha,cwd=work)
        assert git("rev-parse",ref,cwd=work)==new_sha
        failed=False
        try:raise RuntimeError("INJECTED_CANDIDATE_FAILURE")
        except RuntimeError as exc:failed=(str(exc)=="INJECTED_CANDIDATE_FAILURE")
        assert failed
        git("update-ref",ref,old_sha,new_sha,cwd=work)
        assert git("rev-parse",ref,cwd=work)==old_sha
        assert hashes(old)==old_files and hashes(new)==new_files
        return {"schema":"kyoto_h06_git_ref_switch_drill.v1","old_sha":old_sha,"new_sha":new_sha,
                "switch_to_new":True,"fault_detected":True,"rollback_to_old":True,
                "old_source_unchanged":True,"new_source_unchanged":True,
                "real_github_ref_changed":False,"turso_touched":False,"secrets_touched":False,
                "h06_production_cutover_certified":False,
                "tested_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
if __name__=="__main__":
    receipt=run()
    Path("h06_ref_rollback_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,ensure_ascii=False))
