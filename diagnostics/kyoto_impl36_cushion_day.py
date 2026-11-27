"""Independent day coverage sidecar: replay authenticated cushion originals.
No source HTTP, no alteration of the original handoff or next-day policy.
"""
import argparse,hashlib,json,os,re,subprocess,tempfile,time
from pathlib import Path
from diagnostics.kyoto_impl36_cushion_capture import replay,DAYS,utc,REPO
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence,DAY

NAME="Kyoto Nov28-29 independent official cushion source"
WORKFLOW=".github/workflows/kyoto-20261128-29-cushion-source.yml"

def combine(day,coverage,observations):
    if day not in DAYS or coverage.get("day")!=day or coverage.get("race_denominator")!=12:
        raise ValueError("coverage_identity")
    if set(coverage["races"])!={str(i) for i in range(1,13)}:
        raise ValueError("race_denominator")
    result={"day":day,"schema":"kyoto_impl36_cushion_day.v1","race_denominator":12,"races":{},
            "prestart_verified_races":0,"prediction_ready":False,"full_data_acquisition_certified":False}
    for n,r in coverage["races"].items():
        row={"state":"ROSTER_OR_START_UNVERIFIED"}
        result["races"][n]=row
        if r.get("state")!="ROSTER_VERIFIED":continue
        try: cutoff=utc(r["start_utc"])
        except (ValueError,TypeError,KeyError):continue
        valid=[(rid,v) for rid,v in observations if v["day"]==day and utc(v["captured_at_utc"])<cutoff]
        if not valid:
            row["state"]="NO_PRESTART_ORIGINAL";continue
        latest=max(utc(v["captured_at_utc"]) for _,v in valid)
        same=[(rid,v) for rid,v in valid if utc(v["captured_at_utc"])==latest]
        if len({(v["cushion_value"],v["measurement_utc"]) for _,v in same})!=1:
            row["state"]="SAME_TIMESTAMP_CONFLICT";continue
        rid,v=max(same,key=lambda x:int(x[0]))
        row.update(state="SOURCE_VERIFIED_PRESTART",run_id=str(rid),start_utc=cutoff.isoformat(),
                   observation=v)
        result["prestart_verified_races"]+=1
    return result

def collect(day,repo,key,api,download,*,budget=90,clock=time.monotonic):
    end=clock()+budget;errors=[];obs=[]
    def remaining():
        r=end-clock()
        if r<=0:raise TimeoutError("sidecar_budget")
        return r
    try:
        idx=api(f"repos/{repo}/actions/workflows/{WORKFLOW.rsplit('/',1)[1]}/runs?created={day[:4]}-{day[4:6]}-{day[6:]}&per_page=100",remaining())
        rows=idx["workflow_runs"]
        if idx["total_count"]!=len(rows) or len({r["id"] for r in rows})!=len(rows):
            raise ValueError("incomplete_or_duplicate_index")
    except Exception as exc:return [],[{"error_class":type(exc).__name__}],False
    complete=True
    for r in sorted(rows,key=lambda x:x["id"]):
        rid=r["id"]
        try:
            if (r.get("name")!=NAME or r.get("path")!=WORKFLOW or r.get("head_branch")!="main" or
                r.get("head_repository",{}).get("full_name")!=repo or
                r.get("created_at","")[:10]!=f"{day[:4]}-{day[4:6]}-{day[6:]}" or
                r.get("event") not in ("workflow_run","workflow_dispatch")):
                raise ValueError("run_identity")
            if r.get("status")!="completed":raise ValueError("run_not_completed")
            arts=api(f"repos/{repo}/actions/runs/{rid}/artifacts?per_page=100",remaining())
            name=f"kyoto-cushion-{rid}-{day}"
            candidates=[a for a in arts["artifacts"] if a["name"]==name and not a["expired"]]
            if arts["total_count"]!=len(arts["artifacts"]) or len(candidates)!=1:raise ValueError("artifact_identity")
            with tempfile.TemporaryDirectory(prefix="kyoto_cushion_day_") as d:
                p=Path(d);cipher=p/"cipher";cipher.mkdir()
                download(rid,name,cipher,remaining())
                raw=p/"raw"
                decrypt_evidence(cipher,raw,key_hex=key,repo=repo,run_id=str(rid))
                item=replay(raw,day)
                if item is None:raise ValueError("original_replay_unverified")
                obs.append((rid,item))
        except Exception as exc:
            complete=False;errors.append({"run_id":rid,"error_class":type(exc).__name__})
            if clock()>=end:break
    return obs,errors,complete

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--day",required=True,choices=DAYS);p.add_argument("--report",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args();repo=os.environ.get("GITHUB_REPOSITORY");key=os.environ.get("ARCHIVE_KEY","")
    if repo!=REPO or DAY!=a.day or not re.fullmatch(r"[a-fA-F0-9]{64}",key):raise ValueError("sidecar_environment")
    data=a.report.read_bytes()
    report=json.loads(data)
    def api(path,timeout):
        return json.loads(subprocess.check_output(["gh","api",path],timeout=min(15,timeout),stderr=subprocess.DEVNULL))
    def download(rid,name,path,timeout):
        subprocess.run(["gh","run","download",str(rid),"--repo",repo,"--name",name,"--dir",str(path)],check=True,timeout=min(20,timeout),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    obs,errors,complete=collect(a.day,repo,key,api,download)
    coverage=report.get("day_source_coverage")
    if not isinstance(coverage,dict):
        out={"schema":"kyoto_impl36_cushion_day.v1","day":a.day,"state":"HANDOFF_COVERAGE_MISSING","prediction_ready":False,"full_data_acquisition_certified":False}
    else:out=combine(a.day,coverage,obs)
    out.update(handoff_sha256=hashlib.sha256(data).hexdigest(),source_index_complete=complete,source_errors=errors,
               authenticated_observations=[{"run_id":str(rid),"observation":v} for rid,v in obs])
    with a.out.open("x",encoding="utf8") as f:json.dump(out,f,ensure_ascii=False,sort_keys=True,indent=2)
if __name__=="__main__":main()
