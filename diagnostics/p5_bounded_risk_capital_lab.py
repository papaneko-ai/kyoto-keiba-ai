"""P5-03 bounded risk allocation against the existing P5-02 ranking.

Deterministic, conservative LAB capital-control heuristic. It intentionally
avoids Kelly claims from uncalibrated probabilities. This is not a live
capital recommendation, racing profitability estimate, or bet order.
"""
from __future__ import annotations
import hashlib
import json
import math
from decimal import Decimal

class CapitalRiskRejected(ValueError): pass

def _digest(v):
    return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()

def research_capital_control(ranking, *, exposure_fraction=0.35,
                             max_race_fraction=0.20,
                             max_pair_fraction=0.12,
                             max_pair_stake_yen=2000,
                             downside_guard=0.10):
    """Allocate in 100-yen increments by descending stress EV, under strict caps.

    An edge-based cap is a planning heuristic (not a statistical Kelly bet):
    permitted position fraction <= min(max_pair_fraction, edge/(1+edge)/4).
    Never increase exposure when caps are tightened.
    """
    if type(ranking) is not dict or ranking.get("schema")!="kyoto_p5_source_bound_research_ranking.v1":
        raise CapitalRiskRejected("P5_ranked_receipt_required")
    expected=ranking.get("ranking_sha256")
    if type(expected) is not str or expected!=_digest({k:v for k,v in ranking.items() if k!="ranking_sha256"}):
        raise CapitalRiskRejected("P5_receipt_sha_mismatch")
    if (ranking.get("scope")!="P4_LAB_RECEIPTS_ONLY_NOT_REAL_RACING"
        or ranking.get("actual_purchase_authorized") is not False
        or ranking.get("real_paper_trade_recorded") is not False
        or ranking.get("independent_live_predictions_verified") is not False):
        raise CapitalRiskRejected("research_only_required")
    for k,v in (("exposure_fraction",exposure_fraction),("max_race_fraction",max_race_fraction),
                ("max_pair_fraction",max_pair_fraction),("downside_guard",downside_guard)):
        if type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=1:
            raise CapitalRiskRejected("invalid_fraction:"+k)
    if not 0<max_race_fraction<=exposure_fraction or not 0<max_pair_fraction<=max_race_fraction:
        raise CapitalRiskRejected("unordered_exposure_caps")
    if type(max_pair_stake_yen) is not int or max_pair_stake_yen<100 or max_pair_stake_yen%100:
        raise CapitalRiskRejected("max_pair_stake_invalid")
    budget=ranking.get("daily_budget_ceiling_yen")
    if type(budget) is not int or not 0<=budget<=1_000_000 or budget%100:
        raise CapitalRiskRejected("daily_budget_invalid")
    selected=ranking.get("selected")
    if type(selected) is not list or len(selected)>ranking.get("max_races",0):
        raise CapitalRiskRejected("selection_invalid")
    if (ranking.get("research_spent_yen")!=sum(
            t.get("stake_yen",0) for row in selected for t in row.get("tickets",[]))):
        raise CapitalRiskRejected("P5_budget_reconciliation_failed")
    if (ranking["research_spent_yen"]+ranking.get("unspent_yen",-1)!=budget):
        raise CapitalRiskRejected("P5_ceiling_not_balanced")
    if len({(x.get("race_date"),x.get("race")) for x in selected})!=len(selected):
        raise CapitalRiskRejected("duplicate_selected_race")
    cap_total=min(budget, int(budget*exposure_fraction//100)*100)
    cap_race=int(budget*max_race_fraction//100)*100
    cap_pair=min(max_pair_stake_yen,int(budget*max_pair_fraction//100)*100)
    spent=0
    rows=[]
    for index, row in enumerate(selected,1):
        if row.get("rank")!=index or not 1<=row.get("race",0)<=12:
            raise CapitalRiskRejected("rank_order_invalid")
        tickets=row.get("tickets")
        if type(tickets) is not list or not 1<=len(tickets)<=ranking.get("max_tickets_per_race",0):
            raise CapitalRiskRejected("ticket_count_invalid")
        race_total=0
        proposals=[]
        seen=set()
        for t in tickets:
            pair=t.get("pair")
            edge=t.get("stressed_net_lower")
            expected_ev=t.get("model_expected_net")
            if (type(pair) is not list or len(pair)!=2
                or any(type(n) is not int or n<1 for n in pair)
                or pair[0]>pair[1] or tuple(pair) in seen
                or type(edge) not in (int,float) or not math.isfinite(edge)
                or type(expected_ev) not in (int,float) or not math.isfinite(expected_ev)
                or type(t.get("stake_yen")) is not int or t["stake_yen"]<100 or t["stake_yen"]%100):
                raise CapitalRiskRejected("risk_ticket_invalid")
            seen.add(tuple(pair))
            if edge<=downside_guard:
                amount=0
            else:
                edge_fraction=min(float(max_pair_fraction),float(edge)/(1.0+float(edge))/4.0)
                amount=min(cap_pair,int(budget*edge_fraction//100)*100,
                           max(0,cap_total-spent),max(0,cap_race-race_total))
            spent+=amount
            race_total+=amount
            proposals.append({"pair":pair,"stressed_ev_lower_per_1":edge,
                              "heuristic_stake_yen":amount,
                              "skip_reason":"STRESS_TOO_LOW" if edge<=downside_guard else
                                  ("CAP_OR_ROUNDING" if amount==0 else None)})
        if any(x["heuristic_stake_yen"]>0 for x in proposals):
            rows.append({"race_date":row["race_date"],"race":row["race"],
                         "rank":index,"source_p4_sha256":row["p4_comparison_sha256"],
                         "race_exposure_yen":race_total,"tickets":proposals})
    output={"schema":"kyoto_p5_bounded_lab_capital_v1",
      "scope":"UNCALIBRATED_MODEL_CAPITAL_HEURISTIC_NOT_FINANCIAL_ADVICE",
      "source_p5_ranking_sha256":expected,
      "ticket_type":ranking["ticket_type"],
      "daily_budget_ceiling_yen":budget,
      "max_total_exposure_yen":cap_total,
      "max_race_exposure_yen":cap_race,
      "max_pair_exposure_yen":cap_pair,
      "downside_guard":downside_guard,
      "selected":rows,"research_spent_yen":spent,
      "unused_yen":budget-spent,
      "zero_spend_allowed":True,
      "real_model_calibrated":False,
      "official_market_verified":False,
      "real_paper_trade_recorded":False,
      "actual_purchase_authorized":False}
    return {**output,"capital_sha256":_digest(output)}
