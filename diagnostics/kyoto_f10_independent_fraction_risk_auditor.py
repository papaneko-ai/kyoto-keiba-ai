"""Independent F10 witness auditor using exact rational arithmetic.

No import of the risk allocator or F12 application code. Only tests a
previously captured OFFLINE LAB witness from a pinned successful Actions run.
Exact amount replay, SHA and negative checks do not certify JRA origin,
odds availability, calibration, expected real return or live application.
"""
from __future__ import annotations
import hashlib,json,math
from datetime import datetime
from fractions import Fraction

class F10AuditRejected(ValueError):pass
FIRST_RUN="43136221923"
FIRST_HEAD="b34c2d8005e93cc75475dcd05a715cc22dc0ee60"
RUBRIC="92bae5c1d61d6ac00a5380dd8d5e08beb59f96c898b03c05a3c8bf8721ced632"
def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()
def money_floor(total,portion):
    return (Fraction(total)*portion//100)*100
def _check(condition,reason):
    if not condition:raise F10AuditRejected(reason)
def verify(source,rubric):
    _check(hashlib.sha256(rubric).hexdigest()==RUBRIC,"rubric_changed")
    criteria=json.loads(rubric)["criteria"]
    f10=next(r for r in criteria if r["id"]=="F10")
    _check(f10["title"]=="市場鮮度と損失リスク制御" and f10["points"]==5,"F10_rubric_changed")
    _check(source.get("schema")=="kyoto_F10_offline_risk_witness.v1"
           and source.get("ci_run_id")==FIRST_RUN
           and source.get("ci_head_sha")==FIRST_HEAD,"source_ci_invalid")
    _check(source.get("real_market_authenticated") is False and
           source.get("production_paper_trade_authorized") is False,"false_live_claim")
    hand=source.get("lab_source_f11_f12_handoff")
    quote=source.get("lab_quotes")
    report=source.get("decision")
    _check(type(hand) is dict and type(quote) is list and type(report) is dict,"witness_shape_invalid")
    _check(hand.get("scope")=="LAB_RANKING_TO_BUDGET_ONLY_NO_LIVE_FREEZE" and
           hand.get("virtual_trade_frozen") is False and
           hand.get("actual_purchase_authorized") is False,"invalid_handoff_scope")
    p=hand.get("f12_plan")
    _check(type(p) is dict and
           p.get("plan_sha256")==digest({k:v for k,v in p.items() if k!="plan_sha256"}),
           "source_plan_sha_mismatch")
    _check(report.get("risk_sha256")==digest({k:v for k,v in report.items() if k!="risk_sha256"}),
           "risk_sha_mismatch")
    for key in ("live_source_authenticated","probabilities_calibrated","live_paper_trades_written","real_purchase_authorized"):
        _check(report.get(key) is False,"false_paper_trade_status")
    _check(report.get("scope")=="RESEARCH_ONLY_UNCALIBRATED_PRICES_NO_BETS"
           and report.get("source_f12_sha256")==p["plan_sha256"]
           and report.get("source_f11_sha256")==hand["f11_source_sha256"],
           "source_binding")
    _check(p.get("day_budget_ceiling_yen")==10000
           and p.get("exposure_target_yen")==3500
           and p.get("spent_yen")==3500
           and report.get("f12_planned_spent_yen")==3500
           and report.get("day_budget_yen")==10000,
           "budget_fixture_changed")
    _check(report.get("ticket_type")=="QUINELLA"
           and report.get("decision_utc")=="2026-11-14T03:05:00Z"
           and report.get("maximum_quote_age_seconds")==600,
           "market_or_age_changed")
    _check(report.get("probability_error_bound")==.05
           and report.get("odds_drift_fraction")==.08
           and report.get("takeout_rate_recorded")==.25
           and report.get("takeout_embedded_in_published_odds") is True,
           "assumption_changed")
    _check(report.get("max_total_stake_yen")==3500
           and report.get("max_race_stake_yen")==2000
           and report.get("max_pair_stake_yen")==1200
           and report.get("max_horse_or_frame_stake_yen")==2200
           and report.get("max_worst_case_loss_yen")==3500,
           "exposure_caps_wrong")
    planned={}
    for r in p["selected"]:
        for t in r["tickets"]:
            k=(r["race"],tuple(t["pair"]))
            _check(k not in planned,"duplicate_plan")
            planned[k]={"priority":r["priority"],"planned_stake_yen":t["stake_yen"]}
    quotes={}
    for q in quote:
        k=(q["race"],tuple(q["pair"]))
        _check(k in planned and k not in quotes,"quote_unbound")
        _check(q["market"]=="QUINELLA" and q["source_scope"]=="UNAUTHENTICATED_OFFLINE_LAB_MARKET",
               "invalid_quote_scope")
        _check(q["source_sha256"]==("a" if q["race"]==1 else "b")*64,"incorrect_quote_source")
        _check(q["odds"]==8.0 and q["probability"]==.35,"fixture_quote_changed")
        quotes[k]=q
    _check(set(quotes)==set(planned),"quote_coverage")
    positions=sorted(planned,key=lambda k:(planned[k]["priority"],k[0],k[1]))
    _check(len(positions)==6 and len(report.get("decisions",[]))==6,"position_count")
    race_used,entity_used,used={}, {},0
    for key,decision in zip(positions,report["decisions"]):
        race,pair=key
        q=quotes[key]
        _check(decision["race"]==race and tuple(decision["pair"])==pair
               and decision["priority"]==planned[key]["priority"],"decision_rank_wrong")
        age=(datetime.fromisoformat(report["decision_utc"].replace("Z","+00:00"))-
             datetime.fromisoformat(q["observed_utc"].replace("Z","+00:00"))).total_seconds()
        _check(age==300 and decision["quote_age_seconds"]==age,"source_age_wrong")
        prob_lower=max(Fraction(0),Fraction(str(q["probability"]))-Fraction("0.05"))
        stressed_ev=prob_lower*Fraction(str(q["odds"]))*(1-Fraction("0.08"))-1
        _check(math.isclose(decision["probability_lower_bound"],float(prob_lower),abs_tol=1e-14,rel_tol=0) and
               math.isclose(decision["stressed_net_per_yen"],float(stressed_ev),abs_tol=1e-14,rel_tol=0),
               "risk_ev_wrong")
        edge_fraction=min(Fraction("0.12"),max(Fraction(0),stressed_ev)/
                          (4*(1+max(Fraction(0),stressed_ev))))
        edge_cap=money_floor(10000,edge_fraction)
        entity_capacity=min(2200-entity_used.get((race,k),0) for k in set(pair))
        expected=min(planned[key]["planned_stake_yen"],3500-used,
                     2000-race_used.get(race,0),1200,edge_cap,entity_capacity)
        expected=max(0,expected//100*100)
        _check(decision["accepted_stake_yen"]==expected,
               "independently_recalculated_stake_mismatch")
        _check(decision["planned_stake_yen"]==planned[key]["planned_stake_yen"],"wrong_original_stake")
        _check(decision["quote_sha256"]==q["source_sha256"]
               and decision["takeout_applied_to_published_odds_again"] is False,"invalid_quote_metadata")
        used+=expected
        race_used[race]=race_used.get(race,0)+expected
        for entity in set(pair):
            entity_used[(race,entity)]=entity_used.get((race,entity),0)+expected
    _check(report.get("risk_accepted_spent_yen")==used
           and report.get("unspent_yen")==10000-used
           and report.get("maximum_loss_upper_bound_yen")==used
           and report.get("all_skip") is (used==0),"risk_balance_wrong")
    return {
        "schema":"kyoto_F10_second_independent_acceptance.v1",
        "gate":"F10","accepted_points":5,
        "scope":"OFFLINE_FRESHNESS_UNCERTAINTY_DRAWDOWN_OVERLAP_CONTROLS_ONLY",
        "source_run_id":int(FIRST_RUN),"source_ci_head_sha":FIRST_HEAD,
        "original_risk_sha256":report["risk_sha256"],
        "independently_checked_pairs":len(positions),
        "risk_accepted_spent_yen":used,
        "worst_case_loss_bound_yen":used,
        "method":"Fraction exact conservative EV, independent integer stake caps",
        "actual_live_jra_quote_verified":False,
        "actual_paper_trade_verified":False,
        "calibrated_probabilities_verified":False,
        "real_bet_authorized":False,
    }
