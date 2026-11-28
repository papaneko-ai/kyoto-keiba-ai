"""Bounded same-day profile reuse from authenticated prior acquisition slots.

Never reuse a prior-day page, infer a link from a name, or trust a PASS flag
without binding it to the independently verified registered runner and bytes.
No JRA HTTP here. API or archive failures must not block the current slot.
"""
import json,re,subprocess,tempfile,time
from pathlib import Path
from hashlib import sha256
from diagnostics.kyoto_g03_independent_partial import verify_partial
from diagnostics.jra_pending_profile_plan import trusted_url
from diagnostics.kyoto_g04_all_horse_profiles import _utc,MAX_PROFILE,MAX_HORSES
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.kyoto_impl25_c12_all_runs_handoff import WEEKENDS,_date,run_name_matches

def candidates(root,day,run_id):
    root=Path(root)
    verified=set(verify_partial(root,expected_day=day)["verified_race_numbers"])
    g03=json.loads((root/"g03_receipt.json").read_text(encoding="utf8"))
    g04=json.loads((root/"g04_receipt.json").read_text(encoding="utf8"))
    if g04.get("day")!=day or g04.get("schema")!="kyoto_g04_all_horses.v1":
        raise ValueError("prior_profile_day_or_schema")
    rows=g04["profiles"]
    if not isinstance(rows,list) or len(rows)>MAX_HORSES:raise ValueError("prior_profile_count")
    roster={(r,h["number"]):h for r in verified for h in g03["races"][str(r)]["runners"]}
    found={}
    seen=set()
    for row in rows:
        try:
            race,n=row["race"],row["horse_number"]
            if type(race) is not int or type(n) is not int or not 1<=race<=12 or not 1<=n<=18:continue
            k=(race,n)
            if k in seen:raise ValueError("duplicate_prior_profile_identity")
            seen.add(k)
            h=roster.get(k)
            if not h or row.get("profile_verified") is not True:continue
            url=trusted_url(h["profile_navigation"],parent_host="www.jra.go.jp" if day in ("20261128","20261129") and g03["races"][str(race)].get("source_url","").startswith("https://www.jra.go.jp/") else "jra.jp")
            if row.get("horse_name")!=h["name"] or row.get("source_url")!=url:continue
            name=f"g04_profile_r{race:02d}_h{n:02d}.html"
            if row.get("raw_original_file")!=name:continue
            p=root/name
            if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=MAX_PROFILE:continue
            raw=p.read_bytes()
            if len(raw)!=row.get("source_bytes") or sha256(raw).hexdigest()!=row.get("source_sha256"):continue
            stamp=_utc(row["captured_at_utc"])
            if stamp.strftime("%Y%m%d")!=day or stamp>=_utc(row["race_cutoff_utc"]):continue
            found[k]={"day":day,"name":h["name"],"url":url,"raw":raw,"sha256":row["source_sha256"],
                      "captured_at_utc":row["captured_at_utc"],"run_id":str(run_id)}
        except (KeyError,TypeError,OSError) as exc:
            continue
    return found

def recover(day,repo,key,run_id,*,deadline,monotonic=time.monotonic):
    """Spend at most the remaining bounded resume window on GitHub, not JRA."""
    if day not in ("20261128","20261129") or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo) or not str(run_id).isdigit():
        raise ValueError("resume_identity")
    workflow,file,_=WEEKENDS[day]
    def timeout(cap):
        remaining=deadline-monotonic()
        if remaining<=0:raise TimeoutError("resume_budget_exhausted")
        return min(cap,remaining)
    def api(path):
        return json.loads(subprocess.check_output(["gh","api",path],stderr=subprocess.DEVNULL,text=True,timeout=timeout(8)))
    found={};errors=[]
    try:
        index=api(f"repos/{repo}/actions/workflows/{file}/runs?created={_date(day)}&per_page=100")
        runs=index["workflow_runs"]
        if index["total_count"]!=len(runs) or len(runs)>100 or len({r["id"] for r in runs})!=len(runs):
            raise ValueError("resume_run_index_incomplete")
        for run in sorted(runs,key=lambda r:r["id"],reverse=True):
            rid=run["id"]
            if monotonic()>=deadline:break
            if not run_name_matches(run,workflow,file,day) or run["created_at"][:10]!=_date(day):raise ValueError("resume_wrong_workflow")
            if str(rid)==str(run_id) or run["status"]!="completed" or run["event"] not in ("schedule","workflow_dispatch"):continue
            try:
                listing=api(f"repos/{repo}/actions/runs/{rid}/artifacts?per_page=100")
                arts=listing["artifacts"]
                if listing["total_count"]!=len(arts):raise ValueError("resume_artifact_index_incomplete")
                name=f"kyoto-pc-{rid}-{day}"
                matches=[a for a in arts if a["name"]==name and a["expired"] is False]
                if len(matches)!=1:continue
                with tempfile.TemporaryDirectory(prefix="kyoto_profile_resume_") as d:
                    cipher=Path(d)/"cipher";cipher.mkdir();raw=Path(d)/"raw"
                    subprocess.run(["gh","run","download",str(rid),"--repo",repo,"--name",name,"--dir",str(cipher)],
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=timeout(20))
                    decrypt_evidence(cipher,raw,key_hex=key,repo=repo,run_id=str(rid))
                    for k,item in candidates(raw,day,rid).items():
                        if k not in found:found[k]=item
            except Exception as exc:errors.append({"run_id":str(rid),"error_class":type(exc).__name__})
    except Exception as exc:errors.append({"error_class":type(exc).__name__})
    return found,{"cached_candidates":len(found),"errors":errors}
