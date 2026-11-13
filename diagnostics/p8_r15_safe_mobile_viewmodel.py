"""R15 mobile UI fail-closed view model. No Streamlit dependency or external IO.

The current application is a preview. Unauthenticated inputs NEVER become
predictions, virtual trades, profit, or promoted models.
"""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import json

class MobileStateRejected(ValueError):pass
MARKETS=("馬連","枠連")
SAFE_REASONS=("PRERACE_ORIGINAL_UNVERIFIED","ODDS_NOT_FROZEN","PAPER_LEDGER_NOT_CONNECTED",
              "INDEPENDENT_EVOLUTION_NOT_CERTIFIED")
def _digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
          separators=(",",":"),allow_nan=False).encode()).hexdigest()

def build_mobile_state(*,meeting_date,market,budget_yen,requested_races=3,
                       requested_tickets=2,source_authenticated=False,
                       quotes_frozen=False,paper_ledger_connected=False,
                       evolution_certified=False):
    if type(meeting_date) is not str:
        raise MobileStateRejected("meeting_date_invalid")
    try: parsed=date.fromisoformat(meeting_date)
    except ValueError as exc:raise MobileStateRejected("meeting_date_invalid") from exc
    if parsed.isoformat()!=meeting_date:
        raise MobileStateRejected("meeting_date_invalid")
    if market not in MARKETS or type(market) is not str:
        raise MobileStateRejected("market_invalid")
    if type(budget_yen) is not int or not 0<=budget_yen<=1_000_000 or budget_yen%100:
        raise MobileStateRejected("budget_invalid")
    if type(requested_races) is not int or not 0<=requested_races<=4:
        raise MobileStateRejected("race_count_invalid")
    if type(requested_tickets) is not int or not 0<=requested_tickets<=3:
        raise MobileStateRejected("ticket_count_invalid")
    flags=(source_authenticated,quotes_frozen,paper_ledger_connected,evolution_certified)
    if any(type(x) is not bool for x in flags):
        raise MobileStateRejected("attestation_boolean_required")
    # This preview cannot authenticate user-supplied true flags. No privilege
    # escalation by passing purported successful receipts.
    if any(flags):
        raise MobileStateRejected("signed_upstream_evidence_required")
    body={"schema":"kyoto_r15_mobile_safe_state.v1",
        "meeting_date":meeting_date,"ticket_market":market,
        "daily_budget_ceiling_yen":budget_yen,"maximum_races":4,
        "requested_races":requested_races,"requested_tickets_per_race":requested_tickets,
        "budget_is_ceiling_not_spending_instruction":True,
        "state":"HALTED_UNVERIFIED_PRERACE",
        "reasons":list(SAFE_REASONS),
        "recommendations":[],"rankings":[],"frozen_tickets":[],
        "paper_trades":[],"cumulative_profit_yen":None,
        "hit_rate":None,"return_rate":None,"model_version":None,
        "evolution_decision":None,"evolution_history":[],
        "data_origin":"UNVERIFIED_PREVIEW_ONLY",
        "historical_data_never_current":True,
        "simulation_write_enabled":False,"betting_enabled":False,
        "network_requests":0}
    return {**body,"receipt_sha256":_digest(body)}
