"""Factual G06 coordination receipt: configuration alone never proves remote arbitration."""
from __future__ import annotations

def summarize_claims(records, *, day, slot):
    if not isinstance(records,list):
        raise ValueError("claim_records_invalid")
    items=[]
    for entry in records:
        if not isinstance(entry,dict) or type(entry.get("race")) is not int:
            raise ValueError("claim_record_invalid")
        state=entry.get("claim_state")
        if state is None:
            continue
        items.append({"race":entry["race"], "claim_state":state,
                      "claim_commit_state":entry.get("claim_commit_state"),
                      "fetch_verified":entry.get("both_markets_verified") is True})
    counts={"attempted":len(items),
            "acquired":sum(e["claim_state"]=="ACQUIRED" for e in items),
            "skipped":sum(e["claim_state"] in ("ACTIVE_LEASE","DONE_REUSE_EXISTING","LEASE_CHANGED_RECONCILE") for e in items),
            "committed":sum(e["claim_commit_state"]=="COMMITTED" for e in items),
            "unconfirmed":sum(e["claim_state"]=="COORDINATOR_UNCONFIRMED" or e["claim_commit_state"] in ("COORDINATOR_COMMIT_UNCONFIRMED","RELEASE_UNCONFIRMED_LEASE_EXPIRES") for e in items)}
    return {"schema":"kyoto_g06_claim_evidence.v1","day":day,"slot":slot,
            "status":"G06_CLAIM_CALL_RESULTS_RECORDED" if items else "NO_G06_REMOTE_CLAIM_EVIDENCE",
            "independent_remote_db_verified":False,"production_claim_certified":False,
            "counts":counts,"races":items}
