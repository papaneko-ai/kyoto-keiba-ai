"""Explicit manual-only isolated Turso cross-runner acquisition-claim proof.

Never imports JRA clients, touches production tables, changes secrets or makes
real bets. Only github.event.inputs.confirm_isolated_test_db_only == exact YES
may invoke this script from the workflow. Test DB host is checked byte-for-byte.
"""
from __future__ import annotations
import argparse,hashlib,json,os,time
from pathlib import Path
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims,LAB_TABLE
from diagnostics.kyoto_turso_isolated_virtual_store import endpoint
from diagnostics.kyoto_shared_capture_reservation import key
class ManualProofRejected(ValueError):pass

def client():
    if os.getenv("KYOTO_TURSO_LAB_CONFIRM")!="YES-ISOLATED-CLAIMS-ONLY":
        raise ManualProofRejected("manual_test_db_approval_absent")
    url=os.getenv("TURSO_DATABASE_URL","")
    endpoint(url)  # exact designated nonproduction host only
    token=os.getenv("TURSO_AUTH_TOKEN","")
    if len(token)<16 or any(x.isspace() for x in token):
        raise ManualProofRejected("test_db_credential_unavailable")
    import requests
    return TursoCaptureClaims(url=url,token=token,transport=requests,namespace="ISOLATED_LAB")

def synthetic_key():
    run=os.getenv("GITHUB_RUN_ID","")
    if not run.isdecimal() or not 8<=len(run)<=20:
        raise ManualProofRejected("run_id_invalid")
    return "lab:"+run+":"+key(day="20261121",slot=0,race=1,
                              channel="PC",market="racecard")

def record_output(*,claim=None,state=None):
    output=os.getenv("GITHUB_OUTPUT")
    if not output:raise ManualProofRejected("github_output_missing")
    with open(output,"a",encoding="utf8") as f:
        if claim is not None:
            f.write("must_fetch="+("true" if claim["must_fetch"] else "false")+"\n")
            f.write("generation="+str(claim.get("generation",0))+"\n")
        if state is not None:f.write("state="+state+"\n")

def main(action):
    service=client()
    if action=="setup":
        result=service.prepare_schema()
        if result["schema"]!=LAB_TABLE:
            raise ManualProofRejected("unexpected_remote_table")
        print("TURSO_LAB_CLAIM_TABLE_INITIALIZED_NO_PRODUCTION_WRITES=TRUE")
        return
    k=synthetic_key()
    if action.startswith("contender-"):
        name="lab_"+os.getenv("GITHUB_RUN_ID")+"_"+action.replace("-","_")
        claim=service.claim(claim_key=k,owner=name,now_epoch=int(time.time()),
                            lease_seconds=600)
        record_output(claim=claim,state=claim["state"])
        print("ISOLATED_TURSO_REMOTE_CLAIM_OBSERVED="+claim["state"])
        return
    if action=="verify":
        states=(os.environ["FIRST_STATE"],os.environ["SECOND_STATE"])
        if sorted(states)!=["ACQUIRED","ACTIVE_LEASE"]:
            raise ManualProofRejected("cross_runner_one_owner_not_proven")
        found=service.observe(k)
        if not found or found["state"]!="LEASED":
            raise ManualProofRejected("remote_owner_not_persisted")
        owner=found["owner"]
        valid_owners={"lab_"+os.getenv("GITHUB_RUN_ID")+"_"+x
                      for x in ("contender_first","contender_second")}
        if owner not in valid_owners:
            raise ManualProofRejected("unexpected_owner")
        sha=hashlib.sha256(("SYNTHETIC_NO_JRA:"+k).encode()).hexdigest()
        done=service.complete(claim_key=k,owner=owner,
                 generation=found["generation"],sha256=sha)
        if not done["committed"]:raise ManualProofRejected("remote_fence_rejected")
        replay=service.claim(claim_key=k,owner="lab_replay_no_http",
                 now_epoch=int(time.time()))
        if replay["state"]!="DONE_REUSE_EXISTING" or replay["must_fetch"]:
            raise ManualProofRejected("done_reuse_not_proven")
        print("ACTUAL_ISOLATED_TURSO_CROSS_RUNNER_ATOMIC_CLAIM=PASS")
        print("ACTUAL_STREAMLIT_REMOTE_VERIFIED=FALSE")
        print("PRODUCTION_TABLE_MUTATED=FALSE")
        return
    raise ManualProofRejected("unsupported_operation")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("setup","contender-first","contender-second","verify"))
    args=p.parse_args()
    main(args.action)
