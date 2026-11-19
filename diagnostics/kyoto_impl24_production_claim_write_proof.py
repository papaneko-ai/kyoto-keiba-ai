"""Manual-only production Turso synthetic claim proof.

Uses exact reviewed SQL of the existing shared reservation implementation,
but never forms a race-date/market key. No JRA HTTP and no lab DB access.
"""
import concurrent.futures
import hashlib
import json
import os
import re
import time

from diagnostics.kyoto_turso_capture_claims import (
    CLAIM, READ, COMPLETE, TABLE, TursoCaptureClaims
)
from diagnostics.kyoto_turso_isolated_virtual_store import EXPECTED_HOST
from diagnostics.kyoto_weekend_remote_claim_runtime import UrllibTransport

def run():
    host=os.environ.get("KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST","")
    url=os.environ.get("KYOTO_SHARED_CLAIM_TURSO_URL","")
    token=os.environ.get("KYOTO_SHARED_CLAIM_TURSO_TOKEN","")
    run_id=os.environ.get("GITHUB_RUN_ID","")
    confirmation=os.environ.get("KYOTO_IMPL24_PROOF_CONFIRMATION","")
    if confirmation!="IMPL24-PROVE-PRODUCTION-CLAIMS-ONLY":
        raise SystemExit("PROOF_CONFIRMATION_REQUIRED_NO_DB_IO")
    if (not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.turso\.io",host)
        or host==EXPECTED_HOST or "test" in host or "lab" in host):
        raise SystemExit("UNAPPROVED_PRODUCTION_HOST_NO_DB_IO")
    if url not in ("libsql://"+host,"https://"+host):
        raise SystemExit("PRODUCTION_URL_HOST_MISMATCH_NO_DB_IO")
    if len(token)<16 or any(ch.isspace() for ch in token):
        raise SystemExit("PRODUCTION_TOKEN_MISSING_NO_DB_IO")
    if not re.fullmatch(r"[0-9]{6,16}",run_id):
        raise SystemExit("RUN_ID_REQUIRED_NO_DB_IO")
    # Distinct synthetic namespace; can never be produced by actual G06.
    synthetic="__impl24_prod_claim_proof__:"+run_id
    assert not re.fullmatch(r"2026112[12]:.*",synthetic)
    owner_a="impl24_probe_"+run_id+"_A"
    owner_b="impl24_probe_"+run_id+"_B"
    expiry=int(time.time())+600
    digest=hashlib.sha256(synthetic.encode("utf8")).hexdigest()

    def client():
        return TursoCaptureClaims(url=url,token=token,transport=UrllibTransport())

    primary=client()
    # Read-only collision guard. Never touch an existing claim key.
    if primary.observe(synthetic) is not None:
        raise SystemExit("SYNTHETIC_KEY_ALREADY_EXISTS_REFUSE_TO_MUTATE")
    sql_delete=f"DELETE FROM {TABLE} WHERE claim_key=? RETURNING claim_key"
    mutated=False
    removed=False
    try:
        # Same atomic production SQL as actual G06, with a non-race synthetic
        # key: no need to loosen the live claim() input validator.
        def contender(owner):
            c=client()
            rows=c._single(CLAIM,synthetic,owner,expiry,int(time.time()))
            return (owner,rows)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(contender,v) for v in (owner_a,owner_b)]
            results=[f.result(timeout=40) for f in futures]
        mutated=True
        winners=[(o,rows[0]) for o,rows in results if len(rows)==1]
        if len(winners)!=1 or any(len(rows)>1 for _,rows in results):
            raise RuntimeError("ATOMIC_SINGLE_WINNER_UNCONFIRMED")
        winner,returned=winners[0]
        if returned[0]!=winner or returned[3]!="LEASED":
            raise RuntimeError("CLAIM_RETURNING_MISMATCH")
        observation=primary.observe(synthetic)
        if not observation or observation["owner"]!=winner or observation["state"]!="LEASED":
            raise RuntimeError("REMOTE_LEASE_NOT_OBSERVED")
        generation=observation["generation"]
        if generation!=1:
            raise RuntimeError("UNEXPECTED_GENERATION")
        other=owner_b if winner==owner_a else owner_a
        loser_rows=primary._single(CLAIM,synthetic,other,expiry,int(time.time()))
        if loser_rows:
            raise RuntimeError("DUPLICATE_ACTIVE_LEASE_ACCEPTED")
        result=primary.complete(claim_key=synthetic,owner=winner,generation=generation,sha256=digest)
        if not result.get("committed"):
            raise RuntimeError("COMPLETION_NOT_COMMITTED")
        done=primary.observe(synthetic)
        if not done or done["state"]!="DONE" or done["receipt_sha256"]!=digest:
            raise RuntimeError("DONE_RECEIPT_NOT_CONFIRMED")
        print("IMPL24_PRODUCTION_SYNTHETIC_ATOMIC_SINGLE_OWNER_CONFIRMED")
        print("IMPL24_PRODUCTION_SYNTHETIC_DONE_RECEIPT_CONFIRMED")
    finally:
        # A transport error may have committed without a reply. Use the
        # isolated namespace to recover; never delete a real G06 race key.
        # A failed cleanup causes a hard failure and a persistent forensic key.
        if mutated or primary.observe(synthetic) is not None:
            removed_rows=primary._single(sql_delete,synthetic)
            removed=(len(removed_rows)==1 and removed_rows[0][0]==synthetic)
            if not removed or primary.observe(synthetic) is not None:
                raise RuntimeError("SYNTHETIC_KEY_CLEANUP_NOT_CONFIRMED")
            print("IMPL24_SYNTHETIC_KEY_CLEANUP_VERIFIED")
    print(json.dumps({
        "schema":"kyoto_impl24_production_claim_write_proof.v1",
        "status":"PRODUCTION_SYNTHETIC_CLAIM_WRITE_AND_EXCLUSION_VERIFIED",
        "table":TABLE,
        "synthetic_cleanup_verified":removed,
        "actual_live_race_claim_verified":False,
        "collector_activation":False,
        "lab_database_touched":False
    },sort_keys=True))

if __name__=="__main__":
    run()
