"""Manual, isolated GitHub-held lease for a distinct Streamlit Cloud contender.

Creates a synthetic LEASED claim only in the explicitly allowlisted lab DB.
Does not touch JRA, live production tables, or production application.
"""
from __future__ import annotations
import os
import time
from diagnostics.kyoto_turso_claim_manual_crossrunner import client,synthetic_key,ManualProofRejected

def create_hold() -> dict:
    svc=client()  # checks exact lab host and manual approval
    k=synthetic_key()  # per-workflow GitHub run ID
    svc.prepare_schema()
    owner="lab_"+os.environ["GITHUB_RUN_ID"]+"_streamlit_hold"
    result=svc.claim(claim_key=k,owner=owner,now_epoch=int(time.time()),lease_seconds=600)
    if result["state"]!="ACQUIRED" or result["must_fetch"] is not True:
        raise ManualProofRejected("github_hold_not_acquired")
    observed=svc.observe(k)
    if (not observed or observed["state"]!="LEASED"
        or observed["owner"]!=owner
        or observed["generation"]!=result["generation"]
        or observed["expires_at"]<=int(time.time())):
        raise ManualProofRejected("github_hold_not_persisted")
    print("LAB_STREAMLIT_GITHUB_LEASE_READY=TRUE")
    print("LAB_GITHUB_RUN_ID="+os.environ["GITHUB_RUN_ID"])
    print("LAB_LEASE_SECONDS=600")
    print("PRODUCTION_TABLE_MUTATED=FALSE")
    return {"state":"LEASED","generation":result["generation"]}

if __name__=="__main__":
    create_hold()
