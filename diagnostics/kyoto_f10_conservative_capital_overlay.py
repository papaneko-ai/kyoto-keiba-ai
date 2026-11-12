"""P5/F10 conservative OFFLINE LAB capital risk overlay.

Never claims live JRA authenticity, calibrated probabilities, or real orders.
Takes an immutable F11->F12 budget-plan receipt and per-pair *lab* quotes with
explicit timestamps. Assesses quote age, takeout accounting, odds drift,
probability uncertainty, worst-case loss and shared horse/frame exposure.

Totalizator published decimal payout odds already embed takeout: do not
discount them by takeout a second time. The separate takeout_rate is audit
metadata; model-vs-market profitability must be established elsewhere.
"""
from __future__ import annotations
import hashlib
import json
import math
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

class RiskRejected(ValueError):pass
_SHA256 = set("0123456789abcdef")
def _digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,
      sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()
def _valid_hash(value):
    return type(value) is str and len(value)==64 and set(value)<=_SHA256
def _ts(value):
    if type(value) is not str or not value.endswith("Z"):
        raise RiskRejected("utc_z_required")
    try: d=datetime.fromisoformat(value[:-1]+"+00:00")
    except ValueError as exc:raise RiskRejected("invalid_utc") from exc
    return d
def _bounded(value,name,upper=1.0):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=upper:
        raise RiskRejected(name+"_invalid")
    return float(value)
def _money(value,name,positive=False):
    if type(value) is not int or value%100 or value < (100 if positive else 0):
        raise RiskRejected(name+"_invalid")
    return value
def _positive_odds(value):
    if type(value) not in (float,int) or not math.isfinite(value) or not 1 < value < 10000:
        raise RiskRejected("quoted_odds_invalid")
    return Decimal(str(value))
def _bounds(fraction,budget):
    return int((Decimal(budget)*Decimal(str(fraction))/100).to_integral_value(rounding=ROUND_FLOOR))*100

def overlay_lab_risk(*,f11_handoff,lab_quotes,decision_utc,
                     max_quote_age_seconds=600,probability_error_bound=0.05,
                     odds_drift_fraction=0.08,takeout_rate=0.25,
                     max_daily_fraction=0.35,max_race_fraction=0.20,
                     max_pair_fraction=0.12,max_entity_fraction=0.22,
                     max_loss_yen=3500,minimum_stressed_ev=0.0):
    if type(f11_handoff) is not dict or set(f11_handoff)!={
        "f11_source_sha256","f12_plan","scope","actual_purchase_authorized","virtual_trade_frozen"}:
        raise RiskRejected("f11_f12_handoff_schema_invalid")
    if (f11_handoff["scope"]!="LAB_RANKING_TO_BUDGET_ONLY_NO_LIVE_FREEZE"
        or f11_handoff["actual_purchase_authorized"] is not False
        or f11_handoff["virtual_trade_frozen"] is not False
        or not _valid_hash(f11_handoff["f11_source_sha256"])):
        raise RiskRejected("invalid_research_handoff")
    plan=f11_handoff["f12_plan"]
    if type(plan) is not dict or plan.get("schema")!="kyoto_F12_independent_budget_plan.v1":
        raise RiskRejected("f12_plan_required")
    if (plan.get("plan_sha256")!=_digest({k:v for k,v in plan.items() if k!="plan_sha256"})
        or plan.get("scope")!="OFFLINE_MANUAL_OR_AUTO_PLANNING_NOT_A_BET"
        or plan.get("real_source_verified") is not False
        or plan.get("model_calibrated") is not False
        or plan.get("real_purchase_authorized") is not False):
        raise RiskRejected("f12_plan_integrity_or_scope_invalid")
    budget=_money(plan.get("day_budget_ceiling_yen"),"budget")
    target=_money(plan.get("exposure_target_yen"),"exposure")
    spent=_money(plan.get("spent_yen"),"planned_spent")
    if not spent<=target<=budget or plan.get("unspent_yen")!=budget-spent:
        raise RiskRejected("f12_budget_reconciliation_failed")
    market=plan.get("ticket_type")
    if market not in ("QUINELLA","BRACKET"):
        raise RiskRejected("market_invalid")
    if type(max_quote_age_seconds) is not int or not 0<=max_quote_age_seconds<=3600:
        raise RiskRejected("max_quote_age_invalid")
    err=_bounded(probability_error_bound,"probability_error")
    drift=_bounded(odds_drift_fraction,"odds_drift")
    takeout=_bounded(takeout_rate,"takeout",0.40)
    daily=_bounded(max_daily_fraction,"daily_fraction")
    race_cap_frac=_bounded(max_race_fraction,"race_fraction")
    pair_cap_frac=_bounded(max_pair_fraction,"pair_fraction")
    entity_cap_frac=_bounded(max_entity_fraction,"entity_fraction")
    min_ev=_bounded(minimum_stressed_ev,"min_ev",10000)
    if not (0<pair_cap_frac<=race_cap_frac<=daily and 0<entity_cap_frac<=daily):
        raise RiskRejected("inconsistent_risk_limits")
    max_loss=_money(max_loss_yen,"max_loss")
    now=_ts(decision_utc)
    if type(lab_quotes) is not list or len(lab_quotes)>48:
        raise RiskRejected("quotes_list_invalid")
    expected={}
    selected=plan.get("selected")
    if type(selected) is not list or len(selected)>4:
        raise RiskRejected("selected_invalid")
    total=0
    race_priorities=set()
    for rr in selected:
        if type(rr) is not dict or set(rr)!={"race","priority","stake_yen","tickets"}:
            raise RiskRejected("f12_race_schema_invalid")
        race=rr["race"]
        if type(race) is not int or not 1<=race<=12 or type(rr["priority"]) is not int or rr["priority"] in race_priorities:
            raise RiskRejected("race_or_rank_invalid")
        race_priorities.add(rr["priority"])
        if type(rr["tickets"]) is not list or len(rr["tickets"])>3:
            raise RiskRejected("tickets_invalid")
        cost=0
        for t in rr["tickets"]:
            if type(t) is not dict or set(t)!={"pair","stake_yen","allocation_percent"}:
                raise RiskRejected("ticket_schema_invalid")
            pair=t["pair"]
            limit=18 if market=="QUINELLA" else 8
            if (type(pair) is not list or len(pair)!=2 or any(type(x) is not int for x in pair)
                or not 1<=pair[0]<=limit or not 1<=pair[1]<=limit or
                pair[0]>pair[1] or (market=="QUINELLA" and pair[0]==pair[1])):
                raise RiskRejected("pair_invalid")
            stake=_money(t["stake_yen"],"planned_ticket_stake",positive=True)
            key=(race,tuple(pair))
            if key in expected:raise RiskRejected("duplicate_planned_pair")
            expected[key]={"planned_stake_yen":stake,"priority":rr["priority"]}
            cost+=stake
        if cost!=rr["stake_yen"]:
            raise RiskRejected("race_stake_reconciliation_failed")
        total+=cost
    if total!=spent:
        raise RiskRejected("planned_stake_reconciliation_failed")
    quotes={}
    for q in lab_quotes:
        if type(q) is not dict or set(q)!={
            "race","pair","market","odds","probability","observed_utc","source_sha256","source_scope"}:
            raise RiskRejected("quote_schema_invalid")
        if q["source_scope"]!="UNAUTHENTICATED_OFFLINE_LAB_MARKET" or q["market"]!=market:
            raise RiskRejected("unverified_or_other_market")
        if not _valid_hash(q["source_sha256"]):
            raise RiskRejected("quote_source_sha_invalid")
        pair=q["pair"]
        if type(pair) is not list or len(pair)!=2 or any(type(n) is not int for n in pair):
            raise RiskRejected("quote_pair_invalid")
        key=(q["race"],tuple(pair))
        if key not in expected or key in quotes:
            raise RiskRejected("quote_missing_foreign_or_duplicate")
        _positive_odds(q["odds"])
        _bounded(q["probability"],"probability")
        quotes[key]=q
    if set(quotes)!=set(expected):
        raise RiskRejected("quotes_not_complete")
    daily_cap=min(spent,_bounds(daily,budget),max_loss)
    race_cap=_bounds(race_cap_frac,budget)
    pair_cap=_bounds(pair_cap_frac,budget)
    entity_cap=_bounds(entity_cap_frac,budget)
    per_race={}
    per_entity={}
    used=0
    ordered=sorted(expected,key=lambda k:(
        expected[k]["priority"],k[0],k[1]))
    # A deterministic priority order makes rules auditable. Never invent
    # weights or deploy Kelly on uncalibrated probabilities.
    decisions=[]
    for key in ordered:
        race,pair=key
        q=quotes[key]
        age=(now-_ts(q["observed_utc"])).total_seconds()
        p_lower=max(0.0,q["probability"]-err)
        # Published payout odds already reflect totalisator takeout.
        stressed_odds=_positive_odds(q["odds"])*(Decimal("1")-Decimal(str(drift)))
        expected_net=float(Decimal(str(p_lower))*stressed_odds-1)
        reason=None
        amount=0
        if age<0:reason="FUTURE_QUOTE"
        elif age>max_quote_age_seconds:reason="STALE_QUOTE"
        elif expected_net<=min_ev:reason="NO_POSITIVE_STRESSED_EDGE"
        else:
            # Conservative heuristic sizing, not a Kelly stake or an
            # estimated profitable real strategy. Higher error/drift reduces
            # both stressed EV and the permitted per-pair capital.
            edge_fraction=min(pair_cap_frac,
                max(0.0,expected_net)/(4.0*(1.0+max(0.0,expected_net))))
            edge_cap=_bounds(edge_fraction,budget)
            available=min(
                expected[key]["planned_stake_yen"],
                max(0,daily_cap-used),
                max(0,race_cap-per_race.get(race,0)),
                pair_cap,
                edge_cap,
                *(max(0,entity_cap-per_entity.get((race,e),0)) for e in set(pair)),
            )
            amount=(available//100)*100
            if not amount:reason="EXPOSURE_OR_LOSS_CAP"
        decisions.append({
            "race":race,"priority":expected[key]["priority"],"pair":list(pair),
            "planned_stake_yen":expected[key]["planned_stake_yen"],
            "accepted_stake_yen":amount,"skip_reason":reason,
            "quote_age_seconds":age,"market_odds":q["odds"],
            "quote_sha256":q["source_sha256"],"model_probability_lab":q["probability"],
            "probability_lower_bound":p_lower,"stressed_net_per_yen":expected_net,
            "takeout_applied_to_published_odds_again":False})
        used+=amount
        per_race[race]=per_race.get(race,0)+amount
        for e in set(pair):
            per_entity[(race,e)]=per_entity.get((race,e),0)+amount
    output={
        "schema":"kyoto_P5_F10_lab_risk_overlay.v1",
        "scope":"RESEARCH_ONLY_UNCALIBRATED_PRICES_NO_BETS",
        "source_f11_sha256":f11_handoff["f11_source_sha256"],
        "source_f12_sha256":plan["plan_sha256"],
        "decision_utc":decision_utc,"ticket_type":market,
        "day_budget_yen":budget,"f12_planned_spent_yen":spent,
        "max_total_stake_yen":daily_cap,"max_race_stake_yen":race_cap,
        "max_pair_stake_yen":pair_cap,"max_horse_or_frame_stake_yen":entity_cap,
        "max_worst_case_loss_yen":max_loss,
        "maximum_quote_age_seconds":max_quote_age_seconds,
        "takeout_rate_recorded":takeout,
        "takeout_embedded_in_published_odds":True,
        "odds_drift_fraction":drift,"probability_error_bound":err,
        "risk_accepted_spent_yen":used,"unspent_yen":budget-used,
        "all_skip":used==0,"decisions":decisions,
        "maximum_loss_upper_bound_yen":used,
        "live_source_authenticated":False,"probabilities_calibrated":False,
        "live_paper_trades_written":False,"real_purchase_authorized":False,
    }
    if used>daily_cap or used>max_loss or used>spent:
        raise RiskRejected("global_cap_invariant")
    return {**output,"risk_sha256":_digest(output)}
