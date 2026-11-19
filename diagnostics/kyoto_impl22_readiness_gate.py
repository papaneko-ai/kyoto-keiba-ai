"""Proof-based pre-event readiness assessment; never promote skipped CI results."""
from __future__ import annotations
REQUIRED=("remote_isolated_db_readonly_verified","two_independent_github_runners_atomic_claim_verified","lease_fence_and_reacquire_verified","github_streamlit_cross_environment_verified")
def assess_step7(evidence:dict)->dict:
    if not isinstance(evidence,dict):raise ValueError("evidence_object_required")
    confirmed=[k for k in REQUIRED if evidence.get(k) is True]
    missing=[k for k in REQUIRED if evidence.get(k) is not True]
    return {"criterion":"weekend_pre_event_step7","complete":not missing,"confirmed":confirmed,"missing":missing,"weekend_pre_event_numerator":10 if not missing else 9,"weekend_pre_event_denominator":10,"production_turso_modified":False,"no_live_network_access":True}
