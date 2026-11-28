"""Bounded metadata recovery. No JRA HTTP, source mutation or code promotion."""
import json,re,subprocess,time
class PermanentFailure(ValueError):pass
class RetryableFailure(ValueError):pass
def page(path):
    if not re.fullmatch(r"actions/(?:workflows/kyoto-20261128-29-[a-z-]+\.yml/runs\?created=2026-11-(?:27|28|29)&|runs/[1-9][0-9]*/(?:jobs|artifacts)\?)per_page=(?:100|25)&page=[1-9][0-9]*",path):
        raise PermanentFailure("endpoint_not_allowed")
    try:p=subprocess.run(["gh","api","repos/papaneko-ai/kyoto-keiba-ai/"+path],capture_output=True,text=True,timeout=20)
    except subprocess.TimeoutExpired as e:raise RetryableFailure("api_timeout") from e
    if p.returncode:
        m=re.search(r"HTTP ([1-5][0-9]{2})",p.stderr)
        status=int(m[1]) if m else None
        if status in (401,403,404,429):raise PermanentFailure("http_"+str(status))
        if status is None or status in (408,500,502,503,504):raise RetryableFailure("api_transient")
        raise PermanentFailure("api_rejected")
    try:return json.loads(p.stdout)
    except ValueError as e:raise RetryableFailure("json_invalid") from e
def recover_collection(path,field,*,fetch=page,sleep=time.sleep,trace=None):
    if not path.endswith("per_page=100") or field not in ("workflow_runs","artifacts","jobs"):raise PermanentFailure("collection_scope")
    if trace is None:trace=[]
    for size in (100,25):
        try:
            out=[];ids=set();total=None
            for n in range(1,400//size+2):
                d=fetch(path[:-3]+str(size)+"&page="+str(n))
                if not isinstance(d,dict) or type(d.get("total_count")) is not int or not 0<=d["total_count"]<=400 or not isinstance(d.get(field),list):raise RetryableFailure("invalid_collection")
                if total is None:total=d["total_count"]
                if total!=d["total_count"]:raise RetryableFailure("unstable_total")
                if len(d[field])!=min(size,total-len(out)):raise RetryableFailure("incomplete_page")
                for r in d[field]:
                    rid=r.get("id") if isinstance(r,dict) else None
                    if type(rid) is not int or rid<=0 or rid in ids:raise RetryableFailure("duplicate_or_invalid_id")
                    ids.add(rid);out.append(r)
                if len(out)==total:
                    trace.append({"page_size":size,"state":"COMPLETE","count":total})
                    return {"total_count":total,field:out}
            raise RetryableFailure("page_bound")
        except RetryableFailure as e:
            trace.append({"page_size":size,"state":"REJECTED","reason":str(e)})
            if size==25:raise
            sleep(1)
        except PermanentFailure as e:
            trace.append({"page_size":size,"state":"STOPPED","reason":str(e)})
            raise
    raise PermanentFailure("unresolved")
