"""RG-06B offline repeatable end-to-end LAB pipeline, for the existing P8 UI.

A deterministic replay binds historical STATUS *bytes* without treating
historical data as current race entries. Market, model and payouts are
synthetic. Two separate temporary journals are replayed and hash-compared;
no network, no production artifacts, no orders.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from diagnostics.p1_monitor_viewmodel import summarize
from diagnostics.rg02_dual_market_integrated_lab import integrate_research_market
from diagnostics.rg01_prediction_freeze_settlement_lab import (
    freeze_research_prediction, settle_research_result, verify_research_restart
)

class ReproducibilityRejected(ValueError):
    pass

def _sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
                       separators=(",",":"),allow_nan=False).encode("utf8")).hexdigest()

def _race():
    # Frozen LAB values; never current odds or official forecasts.
    strengths={"1":4.0,"2":3.0,"3":2.0}
    frames={"1":1,"2":1,"3":2}
    return {
        "date":"2026-11-10","race":1,"venue":"京都","provenance":"LAB_SYNTHETIC_ONLY",
        "strengths":strengths,"frames":frames,
        "odds":{"quinella":{"1-2":"30.0","1-3":"30.0","2-3":"30.0"},
                "bracket":{"1-1":"30.0","1-2":"30.0"}},
        "market_observed_utc":"2026-11-10T01:00:00Z",
        "scheduled_start_utc":"2026-11-10T02:00:00Z"
    }

def research_replay_once(*, budget_yen, ticket_type, historical_status_bytes):
    if type(historical_status_bytes) is not bytes or not historical_status_bytes:
        raise ReproducibilityRejected("historical_status_bytes_required")
    if ticket_type not in ("QUINELLA","BRACKET"):
        raise ReproducibilityRejected("ticket_type_invalid")
    try:
        history=json.loads(historical_status_bytes)
        checked=summarize(history)
    except (ValueError,TypeError,KeyError) as exc:
        raise ReproducibilityRejected("historical_status_failed_validation") from exc
    # Bind the original status bytes as a provenance label, not as race features.
    status_sha=hashlib.sha256(historical_status_bytes).hexdigest()
    race=_race()
    allocation=integrate_research_market([race],budget_yen=budget_yen)
    summary=next(x for x in allocation["market_summaries"]
                 if x["ticket_type"]==ticket_type)
    with TemporaryDirectory() as root:
        journal=Path(root)/"lab-journal.jsonl"
        q={tuple(map(int,k.split("-"))):v for k,v in race["odds"]["quinella"].items()}
        b={tuple(map(int,k.split("-"))):v for k,v in race["odds"]["bracket"].items()}
        weights={int(k):float(v) for k,v in race["strengths"].items()}
        frames={int(k):int(v) for k,v in race["frames"].items()}
        frozen=freeze_research_prediction(
            journal,scenario_id="LAB-UI-REPLAY-01",
            ticket_type=ticket_type,strengths=weights,frames=frames,
            market=q if ticket_type=="QUINELLA" else b,
            observed_utc=race["market_observed_utc"],
            frozen_utc="2026-11-10T01:30:00Z",
            cutoff_utc=race["scheduled_start_utc"])
        if not frozen["journal_written"]:
            raise ReproducibilityRejected("unexpected_lab_freeze_skip")
        reopened=verify_research_restart(journal,
                  expected_head=frozen["journal_head_sha256"])
        if reopened["entries"]!=1 or reopened["outcome"]["status"]!="UNSETTLED":
            raise ReproducibilityRejected("freeze_replay_not_unsettled")
        pair="-".join(map(str,frozen["chosen_pair"]))
        settlement=settle_research_result(
            journal,expected_head=frozen["journal_head_sha256"],version=1,
            payout_per_100={pair:500},refunded_pairs=[],
            event_utc="2026-11-10T03:00:00Z")
        replayed=verify_research_restart(journal,
                    expected_head=settlement["journal_head_sha256"])
        if replayed["outcome"]!=settlement["result"] or replayed["entries"]!=2:
            raise ReproducibilityRejected("settlement_replay_diverged")
        body={
            "schema":"kyoto_rg06_single_lab_replay.v1",
            "historical_status_source_sha256":status_sha,
            "historical_runner_count":checked["runner_count"],
            "historical_profile_verified":checked["verified"],
            "synthetic_market_receipt_sha256":allocation["receipt_sha256"],
            "selected_ticket_type":ticket_type,
            "synthetic_pairs_checked":summary["all_pairs_checked"],
            "synthetic_market_budget_yen":budget_yen,
            "synthetic_market_spent_yen":allocation["spent_yen"],
            "frozen_prediction_sha256":frozen["frozen_prediction_sha256"],
            "initial_journal_head_sha256":frozen["journal_head_sha256"],
            "settled_journal_head_sha256":settlement["journal_head_sha256"],
            "synthetic_result":settlement["result"],
            "historical_data_is_not_current":True,
            "official_market_authenticated":False,
            "operational_prediction_ready":False,
            "actual_purchase_authorized":False,
            "network_requests":0
        }
        return {**body,"replay_sha256":_sha(body)}

def repeatable_research_e2e(*, budget_yen, ticket_type, historical_status_bytes):
    """Run twice, with fresh journals, verifying entire deterministic receipts."""
    first=research_replay_once(budget_yen=budget_yen,ticket_type=ticket_type,
                               historical_status_bytes=historical_status_bytes)
    second=research_replay_once(budget_yen=budget_yen,ticket_type=ticket_type,
                                historical_status_bytes=historical_status_bytes)
    if first!=second:
        raise ReproducibilityRejected("repeatable_e2e_mismatch")
    return {"schema":"kyoto_rg06_repeated_e2e.v1",
            "same_input_same_output":True,"independent_replays":2,
            "receipt_sha256":first["replay_sha256"],
            "fixture_market_budget_yen":first["synthetic_market_budget_yen"],
            "fixture_market_spent_yen":first["synthetic_market_spent_yen"],
            "ticket_type":ticket_type,
            "historical_source_sha256":first["historical_status_source_sha256"],
            "offline_research_only":True,"live_racing_verified":False,
            "actual_bet_authorized":False,"network_requests":0}
