"""Observe planned external dispatch slots without claiming provider identity or source success."""
from datetime import datetime,timezone,timedelta
PLAN={"20261128":("00:17","01:17","02:07","02:52"),
      "20261129":("00:17","01:17","02:12","02:57")}
AUX=("03:32","04:32","05:32","06:32")

def observe(day,entries,*,complete,family="morning",aux_ids=(),legacy_pc=None):
    if day not in PLAN or family not in ("morning","afternoon"):raise ValueError("slot_plan")
    out={"schema":"kyoto_external_dispatch_observations.v1","day":day,"family":family,"index_complete":complete is True,"provider_proved":False,"slots":[]}
    ids=[e.get("run",{}).get("id") for e in entries]
    if any(type(i) is not int or i<=0 for i in ids) or len(set(ids))!=len(ids):out["index_complete"]=False
    iso=f"{day[:4]}-{day[4:6]}-{day[6:]}"
    for hm in (PLAN[day] if family=="morning" else AUX):
        start=datetime.fromisoformat(iso+"T"+hm+":00+00:00")
        matches=[]
        for e in entries:
            r=e.get("run",{})
            if r.get("event")!="workflow_dispatch" or r.get("head_branch")!="main":continue
            try:
                t=datetime.fromisoformat(r["created_at"].replace("Z","+00:00"))
                if t.utcoffset()!=timedelta(0) or not start<=t<start+timedelta(minutes=5):continue
            except (KeyError,ValueError,TypeError,AttributeError):continue
            matches.append(e)
        s={"planned_utc":start.isoformat(),"matching_run_ids":[e["run"]["id"] for e in matches],"state":"AMBIGUOUS" if len(matches)>1 else "NOT_OBSERVED","pc_authenticated":False,"sp_authenticated":False}
        if len(matches)==1:
            e=matches[0];r=e["run"];rid=r["id"]
            s["run_id"]=rid;s["state"]="COMPLETED" if r.get("status")=="completed" else "NOT_COMPLETED"
            if s["state"]=="COMPLETED":
                def verified(c):
                    x=e.get("source_assessment",{}).get(c,{})
                    return x.get("ciphertext_authenticated") is True and x.get("source_original_sha_utc_checked") is True
                if family=="morning":
                    s["pc_authenticated"]=((legacy_pc or {}).get(rid) is True if legacy_pc is not None else verified("PC"))
                    s["sp_authenticated"]=verified("SP")
                else:s["pc_authenticated"]=rid in aux_ids
        out["slots"].append(s)
    out["all_slots_observed"]=out["index_complete"] and all(s["state"]=="COMPLETED" for s in out["slots"])
    out["all_pc_authenticated"]=out["all_slots_observed"] and all(s["pc_authenticated"] for s in out["slots"])
    out["all_lanes_authenticated"]=out["all_pc_authenticated"] and all(s["sp_authenticated"] for s in out["slots"])
    return out

def bound_ids(ledger,day,*,both):
    if not isinstance(ledger,dict) or ledger.get("schema")!="kyoto_external_dispatch_observations.v1" or ledger.get("day")!=day or ledger.get("family")!="morning" or ledger.get("index_complete") is not True:return set()
    slots=ledger.get("slots",[])
    iso=f"{day[:4]}-{day[4:6]}-{day[6:]}"
    expected=[datetime.fromisoformat(iso+"T"+hm+":00+00:00").isoformat() for hm in PLAN[day]]
    if len(slots)!=4 or [s.get("planned_utc") for s in slots]!=expected:return set()
    ids=set()
    for s in slots:
        rid=s.get("run_id")
        if type(rid) is not int or rid<=0 or rid in ids or s.get("matching_run_ids")!=[rid] or s.get("state")!="COMPLETED" or s.get("pc_authenticated") is not True or (both and s.get("sp_authenticated") is not True):return set()
        ids.add(rid)
    return ids
