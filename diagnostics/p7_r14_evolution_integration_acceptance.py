"""R14 fixed research-only integration of existing EVO01-08, hybrid P3, and P7 guards.

This module performs no training, certification, promotion, network I/O,
production writes or authentic-JRA attestation. A signed production audit is
separate. Reuse existing frozen F17/F18 evidence and model/journal contracts.
"""
from __future__ import annotations
from diagnostics.kyoto_f17_evo_eight_integrated_research import integrate
from diagnostics.p7_hybrid_model_registry import read_registry,_hash
from diagnostics.p3_hybrid_prediction_contract import check_lab_prediction
from diagnostics.p7_guarded_research_rollback import monitor_research_decisions
from diagnostics.p7_approved_evo_capability_screen import EXPECTED

class R14IntegrationRejected(ValueError):pass
KINDS=("BASELINE","MODIFY","ADD","ENSEMBLE")

def audit_r14_lab(packet,*,f18_witness,rubric_bytes,registry_path,
                  snapshot,predictions,monitor_epochs):
    """Fail closed across all research-only boundaries and return a hash receipt."""
    if type(predictions) is not list or len(predictions)!=4:
        raise R14IntegrationRejected("four_model_predictions_required")
    registry_before=read_registry(registry_path)
    models=registry_before["models"]
    ids=[p.get("model_id") if type(p) is dict else None for p in predictions]
    if len(set(ids))!=4 or any(type(k) is not str or k not in models for k in ids):
        raise R14IntegrationRejected("distinct_registered_models_required")
    if tuple(models[k]["kind"] for k in ids)!=KINDS:
        raise R14IntegrationRejected("baseline_modify_add_ensemble_required")
    if not (models[ids[1]]["parents"]==[ids[0]]
            and models[ids[2]]["parents"]==[ids[0]]
            and set(models[ids[3]]["parents"])=={ids[1],ids[2]}):
        raise R14IntegrationRejected("candidate_lineage_mismatch")
    if any(models[k]["source_scope"]!="LAB_RESEARCH_ONLY" for k in ids):
        raise R14IntegrationRejected("research_registry_only")
    contracts=[]
    for p in predictions:
        contracts.append(check_lab_prediction(registry_path,snapshot,p))
    if len({x["source_sha256"] for x in contracts})!=1 or len({x["cutoff_utc"] for x in contracts})!=1:
        raise R14IntegrationRejected("model_source_or_cutoff_mismatch")
    if any(x["registry_head_sha256"]!=registry_before["head"] for x in contracts):
        raise R14IntegrationRejected("registry_anchor_drift")
    evo=integrate(packet,f18_witness=f18_witness,rubric_bytes=rubric_bytes)
    if (evo["evaluated_capabilities"]!=8
        or set(evo["EVO_results"])!=set(EXPECTED)
        or evo["real_JRA_EVO_certification"] is not False
        or evo["models_deployed"] is not False):
        raise R14IntegrationRejected("evo_scope_or_coverage_invalid")
    monitor=monitor_research_decisions(monitor_epochs)
    if len(monitor["epochs"])<2 or not any(
        e["decision"]=="ROLLBACK_TO_RETAINED_CHAMPION" for e in monitor["epochs"]):
        raise R14IntegrationRejected("forward_rollback_not_demonstrated")
    if (monitor["auto_deploy"] is not False or
        any(e["retained_champion"]!=ids[0] for e in monitor["epochs"])):
        raise R14IntegrationRejected("champion_unapproved_promotion")
    if read_registry(registry_path)["head"]!=registry_before["head"]:
        raise R14IntegrationRejected("registry_mutated_by_audit")
    body={"schema":"kyoto_r14_lab_8evo_hybrid_rollback_acceptance.v1",
        "scope":"LAB_SYNTHETIC_ONLY",
        "evo_receipt_sha256":evo["receipt_sha256"],
        "evo_capabilities":list(EXPECTED),
        "models":[{"model_id":k,"kind":models[k]["kind"],
                   "model_registry_head_sha256":registry_before["head"],
                   "shared_prediction_contract_sha256":c["contract_sha256"]}
                   for k,c in zip(ids,contracts)],
        "same_race_id":snapshot["race_id"],
        "same_source_sha256":contracts[0]["source_sha256"],
        "same_cutoff_utc":contracts[0]["cutoff_utc"],
        "monitor_decision_chain_head":monitor["decision_chain_head"],
        "forward_monitor_epochs":len(monitor["epochs"]),
        "rollback_demonstrated":True,
        "retained_champion":ids[0],
        "candidate_kinds_tested":["MODIFY","ADD","ENSEMBLE"],
        "independent_evo_real_world_certification":False,
        "shadow_candidates_production_adopted":False,
        "unapproved_alternative_promotion":False,
        "production_model_changed":False,"real_JRA_authenticated":False,
        "real_betting_authorized":False,"network_requests":0}
    return {**body,"receipt_sha256":_hash(body)}
