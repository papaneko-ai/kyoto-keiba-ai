"""Read-only, independent replay of authenticated workout original snapshots.
Called in the pinned workout reader, from already bound official race rosters.
No new source HTTP, no names/clocks/URLs in the output, no model promotion.
"""
import hashlib,json,os,re,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

READER_SHA="bd800bc30db60919e274eadac419016c963e77de"
REPO="papaneko-ai/kyoto-keiba-ai"

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def replay(day,rosters,archives,key):
    from diagnostics.kyoto_impl33_workout_runtime import read_snapshot,combine_primary,secondary_record,utc
    from diagnostics.kyoto_impl33_hybrid_workout import recover
    if day not in ("20261128","20261129") or len(key)!=32:
        raise ValueError("day_or_key")
    items={};errors=[];authenticated=0;size=0;seen_runs=set()
    for rid,folder in sorted(archives,key=lambda x:int(x[0]),reverse=True):
        rid=int(rid)
        if rid in seen_runs or rid<=0:raise ValueError("duplicate_run")
        seen_runs.add(rid)
        try:
            p=Path(folder);rp=p/"receipt.json"
            if p.is_symlink() or rp.is_symlink() or not 0<rp.stat().st_size<=4_000_000:raise ValueError("receipt_size")
            d=json.loads(rp.read_text(encoding="utf8"))
            if d.get("day")!=day or d.get("run_id")!=rid or not isinstance(d.get("snapshots"),list) or len(d["snapshots"])>300:
                raise ValueError("receipt_identity")
            for i,m in enumerate(d["snapshots"]):
                try:
                    q=p/f"source_{i:03d}.aesgcm"
                    if q.is_symlink() or not q.is_file() or not 0<q.stat().st_size<=4_000_032:raise ValueError("cipher_size")
                    aad=f"kyoto-workout-runtime-v1|{REPO}|{rid}|{day}|{i}".encode()
                    raw=read_snapshot(q.read_bytes(),m,key,aad)
                    authenticated+=1
                    if m["kind"] not in ("PRIMARY","SECONDARY") or type(m["race"]) is not int or not 1<=m["race"]<=12:continue
                    if str(m["race"]) not in rosters:continue
                    start=utc(rosters[str(m["race"])]["start"])
                    stamp=utc(m["captured_utc"])
                    if not start-timedelta(days=31)<=stamp<start:continue
                    ident=(m["kind"],m["race"],m["url"],m["source_sha256"],stamp.isoformat())
                    if ident in items:continue
                    if size+len(raw)>120_000_000:raise OverflowError("replay_memory_bound")
                    size+=len(raw)
                    items[ident]={"raw":raw,"stamp":stamp.isoformat(),"url":m["url"],"kind":m["kind"],"race":m["race"],"sha":m["source_sha256"],"run_id":str(rid)}
                except Exception as exc:errors.append({"run_id":str(rid),"snapshot":i,"error_class":type(exc).__name__})
        except Exception as exc:errors.append({"run_id":str(rid),"error_class":type(exc).__name__})
    result={}
    for n,o in sorted(rosters.items(),key=lambda x:int(x[0])):
        n=int(n)
        try:
            names={int(k):v for k,v in o["roster"].items()}
            if not 2<=len(names)<=18 or len(set(names.values()))!=len(names):raise ValueError("roster_identity")
            official={"roster":names,"start":o["start"]}
            rows=sorted((x for x in items.values() if x["race"]==n),key=lambda x:(x["stamp"],x["sha"],x["url"],x["run_id"]))
            primary,proofs,_=combine_primary(day,n,rows,official)
            missing=[k for k in names if not primary[k]]
            obs={k:[] for k in missing};secondary={}
            for x in rows:
                if x["kind"]!="SECONDARY":continue
                for k in missing:
                    rec=secondary_record(x,names[k],day,o["start"])
                    if rec:
                        provider=urlsplit(x["url"]).hostname
                        obs[k].append({"provider":provider,"record":rec})
                        secondary.setdefault(k,[]).append((rec,x))
            merged,_=recover(primary,names,obs)
            index={(x["sha"],x["stamp"],x["url"]):x for x in rows}
            out={"named_roster_digest":o["named_roster_digest"],"start":o["start"],"horses":{},"canonical_records":0}
            for k in sorted(names):
                if not merged[k]:continue
                if primary[k]:
                    matched=[index[(p["source_sha256"],p["captured_utc"],p["url"])] for p in proofs[k]]
                    mode="PRIMARY"
                else:
                    matched=[x for rec,x in secondary.get(k,[]) if rec==merged[k][0]]
                    if len({urlsplit(x["url"]).hostname for x in matched})<2:continue
                    mode="SECONDARY_CORROBORATED"
                evidence=sorted({(x["run_id"],x["sha"],x["stamp"],urlsplit(x["url"]).hostname) for x in matched})
                if not evidence:continue
                out["horses"][str(k)]={"state":"INDEPENDENT_WORKOUT_SOURCE_REPLAYED","mode":mode,
                    "value_digest":digest(merged[k]),"record_count":len(merged[k]),
                    "source_proofs":[{"run_id":a,"sha256":b,"utc":c,"provider":d} for a,b,c,d in evidence]}
                out["canonical_records"]+=len(merged[k])
            result[str(n)]=out
        except Exception as exc:errors.append({"race":n,"error_class":type(exc).__name__})
    return {"schema":"kyoto_independent_workout_day_replay.v1","day":day,"races":result,"authenticated_snapshots":authenticated,
            "unique_eligible_snapshots":len(items),"errors":errors,"source_http_requests":0,"production_coverage_authorized":False}

def main():
    if len(sys.argv)!=2:raise SystemExit(2)
    cfg=json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
    def denied(*a,**kw):raise AssertionError("source_network_forbidden")
    with patch("socket.socket.connect",side_effect=denied),patch("socket.create_connection",side_effect=denied):
        out=replay(cfg["day"],cfg["rosters"],cfg["archives"],bytes.fromhex(os.environ["ARCHIVE_KEY"]))
    print(json.dumps(out,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False))
if __name__=="__main__":main()
