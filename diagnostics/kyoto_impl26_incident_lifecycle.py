"""Proof-gated, idempotent technical-incident lifecycle; no auto promotion."""
from __future__ import annotations
import copy
import hashlib
import json
import re

STAGES = [
    "DETECTED", "EVIDENCE_LOCKED", "ROOT_CAUSE_CANDIDATE", "ROOT_CAUSE_PROVED",
    "CANDIDATE_PATCH", "OFFLINE_REGRESSION_PASSED", "APPROVED_FOR_PRODUCTION",
    "LIVE_RECHECK", "CLOSED"
]
PROOF_KEYS = {
    "EVIDENCE_LOCKED": ("source_hash", "run_id"),
    "ROOT_CAUSE_CANDIDATE": ("hypothesis", "same_cause_search"),
    "ROOT_CAUSE_PROVED": ("reproducer", "counterexample", "root_cause"),
    "CANDIDATE_PATCH": ("branch", "commit_sha", "protected_diff"),
    "OFFLINE_REGRESSION_PASSED": ("ci_run_id", "reproducer_pass", "negative_test_pass"),
    "APPROVED_FOR_PRODUCTION": ("approved_commit_sha", "approver_evidence", "rollback_sha"),
    "LIVE_RECHECK": ("actual_run_id", "observed_evidence"),
    "CLOSED": ("closure_evidence", "regression_added"),
}
SHA40 = re.compile(r"^[a-f0-9]{40}$")

def _proof_digest(proof):
    return hashlib.sha256(json.dumps(proof,sort_keys=True,ensure_ascii=False,
                                     separators=(",",":")).encode()).hexdigest()

def advance(incident, next_stage, proof):
    if not isinstance(incident,dict) or incident.get("status") not in STAGES:
        raise ValueError("invalid_incident_state")
    if not isinstance(proof,dict) or not proof:
        raise ValueError("transition_evidence_required")
    old = incident["status"]
    existing=incident.get("transitions",[])
    target_digest=_proof_digest(proof)
    if old==next_stage:
        if existing and existing[-1].get("to")==next_stage and existing[-1].get("proof_sha256")==target_digest:
            return copy.deepcopy(incident)
        raise ValueError("non_idempotent_duplicate_transition")
    if STAGES.index(next_stage)!=STAGES.index(old)+1:
        raise ValueError("state_jump_forbidden")
    for key in PROOF_KEYS.get(next_stage,()):
        if not proof.get(key):
            raise ValueError("required_proof_missing:"+key)
    for key in ("commit_sha","approved_commit_sha","rollback_sha"):
        if key in proof and not SHA40.fullmatch(str(proof[key])):
            raise ValueError("invalid_commit_sha:"+key)
    if next_stage=="APPROVED_FOR_PRODUCTION":
        commits=[row["proof"].get("commit_sha") for row in existing
                 if row.get("to")=="CANDIDATE_PATCH"]
        if proof["approved_commit_sha"] not in commits:
            raise ValueError("approved_sha_mismatch")
    result=copy.deepcopy(incident)
    result.setdefault("transitions",[]).append({
        "from":old, "to":next_stage,"proof":copy.deepcopy(proof),
        "proof_sha256":target_digest})
    result["status"]=next_stage
    return result

def same_cause_candidates(incident, history):
    """Surface possible recurrences only; never claim root-cause proof by similarity."""
    def feature(i):
        return (str(i.get("failure_stage") or "UNKNOWN"),
                str(i.get("error_class") or ""),
                tuple(sorted(str(x) for x in i.get("risk_ids",[]))))
    key=feature(incident)
    return sorted([
        {"incident_id":other.get("incident_id"),"confidence":"CANDIDATE_NOT_PROVED"}
        for other in history if other.get("incident_id")!=incident.get("incident_id")
        and feature(other)==key and other.get("incident_id")
    ],key=lambda x:x["incident_id"])
