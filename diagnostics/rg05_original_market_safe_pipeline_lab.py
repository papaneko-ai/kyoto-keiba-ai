"""RG-05B: strict offline P1 originals -> P4 risk -> P3 prediction -> P6 LAB freeze.

All input validation happens BEFORE a journal is created or amended.
This is a LAB-only transition rehearsal; verifying HTML byte binding is NOT
independent JRA origin, sales, or withdrawal authentication. No network.
"""
from __future__ import annotations
from pathlib import Path
from diagnostics.p1_operator_original_handoff import assess_originals
from diagnostics.p3_p6_research_no_bet import quinella_from_strength, bracket_from_quinella
from diagnostics.p4_research_market_risk import audit_market_risk
from diagnostics.rg01_prediction_freeze_settlement_lab import (
    freeze_research_prediction, settle_research_result, verify_research_restart
)

class SafePipelineRejected(ValueError): pass

def guarded_lab_freeze(journal_path, *, bundle, snapshot, observed_utc,
                       channel, strengths, scenario_id, frozen_utc,
                       probability_error_bound=0.0, odds_drift_fraction=0.0):
    """Strict preflight, no writes until three original bytes & markets match.

    Strengths are synthetic LAB model inputs; they MUST NOT be characterized
    as predicted from the original racecard or an operational model.
    """
    if type(bundle) is not bytes or type(snapshot) is not dict:
        raise SafePipelineRejected("original_bundle_and_snapshot_required")
    if type(strengths) is not dict or type(scenario_id) is not str or not scenario_id.startswith("LAB-"):
        raise SafePipelineRejected("lab_only_strengths_and_identity_required")
    path=Path(journal_path)
    if path.is_symlink() or path.exists():
        raise SafePipelineRejected("immutable_journal_target_required")
    if channel not in ("PC","SP"):
        raise SafePipelineRejected("pc_sp_channel_required")
    receipt=assess_originals(bundle,snapshot,observed_utc=observed_utc,channel=channel)
    if (receipt["source_content_verified"] is not True or
            receipt["official_origin_authenticated"] is not False or
            receipt["prediction_ready"] is not False or
            receipt["official_sales_state_authenticated"] is not False):
        raise SafePipelineRejected("incorrect_offline_authorization_state")
    runners=snapshot["runners"]
    if any(r["status"]!="ACTIVE" for r in runners):
        raise SafePipelineRejected("withdrawn_or_excluded_horse_requires_new_originals")
    roster={r["number"]:r["bracket"] for r in runners}
    if type(strengths) is not dict or set(strengths)!=set(roster):
        raise SafePipelineRejected("prediction_roster_mismatch")
    if any(state["sales"]!="OPEN" for state in snapshot["market_states"].values()):
        raise SafePipelineRejected("sales_not_open")
    qs=quinella_from_strength(strengths)
    bs=bracket_from_quinella(qs,roster)
    def matrix(name, probs):
        rows=snapshot[name]
        market={(min(r["first"],r["second"]),max(r["first"],r["second"])):r["decimal"] for r in rows}
        if set(market)!=set(probs) or len(market)!=len(rows):
            raise SafePipelineRejected("complete_unique_market_required:"+name)
        return market
    quinella=matrix("odds",qs)
    bracket=matrix("bracket_odds",bs)
    # Preflight BOTH bet types before allowing a write for EITHER.
    qa=audit_market_risk(qs,quinella,
        probability_error_bound=probability_error_bound,
        odds_drift_fraction=odds_drift_fraction)
    ba=audit_market_risk(bs,bracket,
        probability_error_bound=probability_error_bound,
        odds_drift_fraction=odds_drift_fraction)
    # The research journal records a LAB evaluation of P1-derived price bytes.
    # It is never an operational race prediction or an actual bet.
    ticket_type="QUINELLA"
    if qa["stress_survivors"]==0 and ba["stress_survivors"]>0:
        ticket_type="BRACKET"
    result=freeze_research_prediction(path,scenario_id=scenario_id,
        ticket_type=ticket_type,strengths=strengths,frames=roster,
        market=quinella if ticket_type=="QUINELLA" else bracket,
        observed_utc=observed_utc,frozen_utc=frozen_utc,
        cutoff_utc=snapshot["prediction_cutoff_utc"])
    return {
        "schema":"kyoto_rg05_offline_safe_lab.v1",
        "source_binding_receipt":receipt["bundle_sha256"],
        "source_snapshot_receipt":receipt["snapshot_sha256"],
        "risk_audit_quinella_sha256":qa["sha256"],
        "risk_audit_bracket_sha256":ba["sha256"],
        "lab_freeze":result,
        "journal_written":result["journal_written"],
        "strict_original_bytes_verified":True,
        "independent_official_origin_authenticated":False,
        "real_model_calibrated":False,
        "real_paper_trade":False,
        "actual_bet_authorized":False,
        "network_requests":0
    }

def guarded_lab_settlement(journal_path, *, frozen_report, expected_head,
                            payout_per_100, refunded_pairs, event_utc, version=1):
    if (type(frozen_report) is not dict or
            frozen_report.get("schema")!="kyoto_rg05_offline_safe_lab.v1" or
            frozen_report.get("journal_written") is not True or
            frozen_report.get("strict_original_bytes_verified") is not True or
            frozen_report.get("independent_official_origin_authenticated") is not False or
            frozen_report.get("lab_freeze",{}).get("journal_head_sha256")!=expected_head):
        raise SafePipelineRejected("original_research_freeze_anchor_required")
    checked=verify_research_restart(journal_path,expected_head=expected_head)
    if checked["outcome"]["status"]!="UNSETTLED":
        raise SafePipelineRejected("settlement_requires_initial_unsettled_state")
    return settle_research_result(journal_path,expected_head=expected_head,
        version=version,payout_per_100=payout_per_100,
        refunded_pairs=refunded_pairs,event_utc=event_utc)
