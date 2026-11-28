"""Real archived November 29 preday source proof; no source HTTP."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone
from diagnostics.kyoto_impl33_workout_runtime import REPO,read_snapshot,source_record,repair_primary_links,collect_primary,PRIMARY_INDEX
RID=46140345524;DAY="20261129";AID=15261487912
def api(p):return json.loads(subprocess.check_output(["gh","api",f"repos/{REPO}/"+p],text=True,stderr=subprocess.DEVNULL,timeout=15))
def main():
    if os.environ.get("GITHUB_REPOSITORY")!=REPO:raise ValueError("repo")
    r=api(f"actions/runs/{RID}")
    if r["id"]!=RID or r["head_repository"]["full_name"]!=REPO or r["head_branch"]!="main" or r["status"]!="completed" or r["path"].split("@")[0]!=".github/workflows/kyoto-20261128-29-workout-source.yml":raise ValueError("run")
    a=api(f"actions/runs/{RID}/artifacts?per_page=100")
    name=f"kyoto-workout-{RID}-{DAY}"
    found=[x for x in a["artifacts"] if x["id"]==AID and x["name"]==name and x["expired"] is False]
    if a["total_count"]!=len(a["artifacts"]) or len(found)!=1:raise ValueError("artifact")
    key=bytes.fromhex(os.environ["ARCHIVE_KEY"])
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        subprocess.run(["gh","run","download",str(RID),"--repo",REPO,"--name",name,"--dir",td],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=40)
        d=json.loads((root/"receipt.json").read_bytes())
        if d["day"]!=DAY or d["run_id"]!=RID or len(d["snapshots"])!=8:raise ValueError("receipt")
        items=[]
        for i,m in enumerate(d["snapshots"]):
            aad=f"kyoto-workout-runtime-v1|{REPO}|{RID}|{DAY}|{i}".encode()
            raw=read_snapshot((root/f"source_{i:03d}.aesgcm").read_bytes(),m,key,aad)
            items.append(source_record(raw,m["captured_utc"],m["url"],m["kind"],m["race"]))
        observed=datetime(2026,11,28,12,0,tzinfo=timezone.utc)
        c=repair_primary_links(DAY,items,[],{}, {},observed)
        if set(c)!={9,10,11,12}:raise ValueError("actual_candidate_inventory")
        # Execute the production candidate selection path with a deliberately
        # unavailable index and a local archive-only transport, not HTTP.
        seen=[];proof=[]
        def local_fetch(url):
            seen.append(url)
            if url==PRIMARY_INDEX:raise TimeoutError("fixture_index_unavailable")
            return next(x["raw"] for x in items if x["url"]==url)
        collect_primary(DAY,list(items),{},local_fetch,lambda:observed,on_repair=proof.append)
        if {x["race"] for x in proof}!=set(c) or any(u!=PRIMARY_INDEX and u not in {x[0] for x in c.values()} for u in seen):raise ValueError("actual_repair_application")
        doc={"schema":"kyoto_actual_workout_link_repair.v1","source_run_id":RID,"artifact_id":AID,
            "source_artifact_digest":found[0]["digest"],"authenticated_originals":len(items),
            "candidate_races":sorted(c),"candidate_proofs":proof,"local_replay_fetches":len(seen)-1,
            "new_source_http_requests":0,"live_acquisition_certified":False}
        Path("actual-proof").mkdir(exist_ok=True);Path("actual-proof/report.json").write_text(json.dumps(doc,sort_keys=True))
        print("ACTUAL_LINK_REPAIR="+json.dumps({k:v for k,v in doc.items() if k!="candidate_proofs"},sort_keys=True))
if __name__=="__main__":main()
