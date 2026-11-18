"""G07 full 12R/148H evidence-slot preflight; do not infer missing values.

Offline matrix uses archived frozen runner identities, not fresh JRA bytes.
A success is a schema/crypto/fault-handling readiness PASS, never a live
source completeness or full individual-originals PASS.
"""
from __future__ import annotations
import json
from diagnostics.jra_pc_sp_benchmark import frozen
from diagnostics.kyoto_hybrid_multi_source import FIELDS
from diagnostics.jra_p1_failover_offline import ChannelResult,choose
from datetime import datetime,timezone

MISSING="HISTORICAL_VALUE_NOT_IN_G07_TEST_INPUT"
def build_matrix():
    items=[];total=0
    for race in range(1,13):
        runners=frozen(race)["runners"]
        if not runners or len(runners)>18 or [h["horse_number"] for h in runners]!=list(range(1,len(runners)+1)):
            raise ValueError("runner_identity_invalid")
        for horse in runners:
            values={field:{"state":"MISSING","value":None,"reason":MISSING,
                           "original_sha256":None,"captured_utc":None}
                    for field in FIELDS}
            items.append({"race":race,"horse_number":horse["horse_number"],
                          "horse_name":horse["horse_name"],"fields":values})
            total+=1
    if total!=148 or len(items)!=148:raise ValueError("historical_roster_not_148")
    if sum(len(x["fields"]) for x in items)!=148*len(FIELDS):
        raise ValueError("incomplete_cell_matrix")
    return items

def failover_proof():
    cutoff=datetime(2026,11,7,5,tzinfo=timezone.utc)
    def item(channel,verified,normalized="b"*64):
        return ChannelResult(channel,verified,"a"*64,"OFFLINE_HORSE","2026-11-07T01:00:00Z",
                  "",1,1,"c"*64,normalized,True,True)
    a=choose(item("PC",False),item("SP",True),cutoff=cutoff)
    b=choose(item("SP",False),item("PC",True),cutoff=cutoff)
    c=choose(item("PC",False),item("SP",False),cutoff=cutoff)
    d=choose(item("PC",True),item("SP",True,"d"*64),cutoff=cutoff,compare=True)
    if (a[0],b[0],c[0],d[1])!=("SP","PC",None,"SOURCE_CONFLICT"):
        raise ValueError("failover_or_conflict_guard_failed")
    return {"pc_fault_sp_selected":True,"sp_fault_pc_selected":True,
            "both_failed_no_selection":True,"conflicting_sources_quarantined":True}

def audit():
    rows=build_matrix();failover=failover_proof()
    return {"schema":"kyoto_g07_12race_148horse_evidence_preflight.v1",
       "source_kind":"SAVED_STRUCTURED_HISTORICAL_ROSTER_NOT_HTML",
       "races":12,"runners":148,"fields_per_runner":len(FIELDS),
       "field_state_slots":sum(len(r["fields"]) for r in rows),
       "explicit_missing_state_slots":sum(
            v["state"]=="MISSING" and v["value"] is None
            for row in rows for v in row["fields"].values()),
       "fault_injection":failover,"network_requests":0,
       "all_real_originals_verified":False,"production_ready":False,
       "independent_h03_and_g06_pending":True}
if __name__=="__main__":print(json.dumps(audit(),ensure_ascii=False,sort_keys=True))
