"""Reuse the pinned independent SP and cushion replayers for day closure.
No source HTTP, no model/market/roster credit, no production writes.
"""
import json, os, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO="papaneko-ai/kyoto-keiba-ai"
DAYS=("20261128","20261129")
CUSHION_READER_SHA="301916719e5bc0e3a8e392368434f952c16c05db"
MAX_ARCHIVES=16

def inventory(metadata,lane):
    rows=metadata["runs"]
    ids=[r["id"] for r in rows]
    if any(type(i) is not int or i<=0 for i in ids) or len(set(ids))!=len(ids):
        raise ValueError("supplemental_run_identity")
    return [{"run_id":r["id"],"event":r["event"],"status":r["status"],
             "artifact_state":r.get("artifacts",{}).get(lane,{}).get("state","ARTIFACT_NOT_INDEXED")}
            for r in sorted(rows,key=lambda r:r["id"])]

def review_sp(day,metadata,*,invoke=None,aggregate=None,clock=time.monotonic):
    if day not in DAYS:raise ValueError("supplemental_day")
    if invoke is None:
        from diagnostics.kyoto_impl31_handoff_budget import _invoke as invoke
    if aggregate is None:
        from diagnostics.kyoto_impl32_sp_handoff import aggregate
    inv=inventory(metadata,"sp")
    candidates=[r for r in inv if r["status"]=="completed" and r["artifact_state"]=="PRESENT" and r["event"] in ("schedule","workflow_dispatch")]
    end=clock()+90
    def one(r):
        try:return invoke(("lane",day,REPO,r["run_id"],"SP"),end)
        except Exception as e:return {"error_class":type(e).__name__}
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(one,candidates[:MAX_ARCHIVES]))
    by={r["run_id"]:v for r,v in zip(candidates,results)}
    entries=[{"run":{"id":r["run_id"],"event":r["event"],"status":r["status"]},
              "source_assessment":{"SP":by.get(r["run_id"],{})}} for r in inv]
    result=aggregate(day,entries)
    if (result.get("schema")!="kyoto_impl32_sp_handoff.v1" or result.get("day")!=day or
        result.get("race_denominator")!=12 or any(result.get(k) is not False for k in
            ("pc_denominator_modified","prestart_certified","market_verified","live_acquisition_certified"))):
        raise ValueError("sp_ledger_identity")
    result.update(source_run_index_complete=metadata["index_complete"] is True,
                  source_inventory=inv,source_http_requests=0,
                  archive_bound_exceeded=len(candidates)>MAX_ARCHIVES,
                  replay_errors=[{"run_id":r["run_id"],"error_class":str(v.get("error_class","SP_ORIGINAL_NOT_VERIFIED"))}
                    for r,v in zip(candidates,results) if v.get("source_original_sha_utc_checked") is not True])
    return result

def replay_cushions(day,coverage,archives,read,combine):
    """Only use independently authenticated originals; reuse exact combine."""
    if day not in DAYS:raise ValueError("supplemental_day")
    ids=[rid for rid,_ in archives]
    if any(type(i) is not int or i<=0 for i in ids) or len(ids)!=len(set(ids)) or len(ids)>MAX_ARCHIVES:
        raise ValueError("cushion_archive_identity")
    observations=[];errors=[]
    for rid,path in archives:
        try:
            v=read(rid,Path(path))
            if not isinstance(v,dict) or v.get("day")!=day:
                raise ValueError("cushion_original_not_verified")
            observations.append((rid,v))
        except Exception as e:errors.append({"run_id":rid,"error_class":type(e).__name__})
    result=combine(day,coverage,observations)
    if (result.get("schema")!="kyoto_impl36_cushion_day.v1" or result.get("day")!=day or
        result.get("race_denominator")!=12 or set(result.get("races",{}))!={str(n) for n in range(1,13)} or
        result.get("prediction_ready") is not False or result.get("full_data_acquisition_certified") is not False):
        raise ValueError("cushion_ledger_identity")
    result.update(source_http_requests=0,authenticated_observations=[{"run_id":str(rid),"observation":v} for rid,v in observations],replay_errors=errors)
    return result

def review_cushion(day,metadata,coverage,key,reader):
    inv=inventory(metadata,"cushion")
    candidates=[r for r in inv if r["status"]=="completed" and r["artifact_state"]=="PRESENT"]
    reader=Path(reader).resolve()
    if subprocess.check_output(["git","rev-parse","HEAD"],cwd=reader,text=True,stderr=subprocess.DEVNULL,timeout=5).strip()!=CUSHION_READER_SHA:
        raise ValueError("cushion_reader_revision")
    errors=[];archives=[];end=time.monotonic()+75
    with tempfile.TemporaryDirectory(prefix="kyoto_closure_cushion_") as tmp:
        root=Path(tmp)
        for r in candidates[:MAX_ARCHIVES]:
            rid=r["run_id"]
            try:
                left=end-time.monotonic()
                if left<=0:raise TimeoutError()
                target=root/str(rid);target.mkdir()
                subprocess.run(["gh","run","download",str(rid),"--repo",REPO,"--name",f"kyoto-cushion-{rid}-{day}","--dir",str(target)],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=min(20,left),check=True)
                archives.append([rid,str(target)])
            except Exception as e:errors.append({"run_id":rid,"error_class":type(e).__name__})
        config=root/"config.json";config.write_text(json.dumps({"day":day,"coverage":coverage,"archives":archives}),encoding="utf8")
        env={"PATH":os.environ.get("PATH",""),"PYTHONPATH":str(reader),"PYTHONUTF8":"1","ARCHIVE_KEY":key,"KYOTO_TARGET_DAY":day}
        raw=subprocess.check_output([sys.executable,str(Path(__file__).resolve()),str(config)],cwd=reader,env=env,stderr=subprocess.DEVNULL,timeout=75)
        if len(raw)>5_000_000:raise ValueError("cushion_replay_size")
        result=json.loads(raw)
    if (result.get("day")!=day or result.get("schema")!="kyoto_impl36_cushion_day.v1" or
        result.get("source_http_requests")!=0 or result.get("prediction_ready") is not False or
        result.get("full_data_acquisition_certified") is not False):
        raise ValueError("cushion_replay_identity")
    result["replay_errors"]+=errors
    result.update(reader_sha=CUSHION_READER_SHA,source_inventory=inv,source_run_index_complete=metadata["index_complete"] is True,
                  archive_bound_exceeded=len(candidates)>MAX_ARCHIVES,
                  all_present_archives_replayed=not result["replay_errors"] and len(candidates)==len(archives))
    return result

def main():
    from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
    from diagnostics.kyoto_impl36_cushion_capture import replay
    from diagnostics.kyoto_impl36_cushion_day import combine
    c=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
    day=c["day"];key=os.environ["ARCHIVE_KEY"]
    if os.environ.get("KYOTO_TARGET_DAY")!=day:raise ValueError("cushion_target_day")
    def read(rid,cipher):
        with tempfile.TemporaryDirectory(prefix="kyoto_closure_cushion_raw_") as d:
            raw=Path(d)/"raw"
            decrypt_evidence(cipher,raw,key_hex=key,repo=REPO,run_id=str(rid))
            return replay(raw,day)
    print(json.dumps(replay_cushions(day,c["coverage"],c["archives"],read,combine),sort_keys=True,allow_nan=False))
if __name__=="__main__":main()
