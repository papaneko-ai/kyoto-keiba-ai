"""F11 source-bound LAB recommendation receipt and F12 handoff, never a live bet.

Uses existing independently-tested P4->P5 ranking. Adds a strict explanation,
freshness and confidence gate, including no-bet, max-4, original P4 receipt
reconciliation and exact F12 ranked candidate IDs.
"""
from __future__ import annotations
import hashlib,json,math
from datetime import datetime,timezone
from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races
from diagnostics.kyoto_f12_ticket_budget_planner import plan_f12

class F11Rejected(ValueError):pass
def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()
def utc(s):
    if type(s) is not str or not s.endswith("Z"):
        raise F11Rejected("utc_required")
    try:d=datetime.fromisoformat(s[:-1]+"+00:00")
    except ValueError as e:raise F11Rejected("invalid_utc") from e
    if d.utcoffset().total_seconds()!=0:raise F11Rejected("utc_invalid")
    return d

def rank_f11(*,comparisons,day_budget_yen,ticket_type,observed_utc,
             cutoff_utc,confidence_by_race,max_races=3,
             max_tickets_per_race=2,min_confidence=0.0,
             max_source_age_seconds=900,minimum_stressed_ev=0.0):
    if type(comparisons) is not list or not 1<=len(comparisons)<=12:
        raise F11Rejected("comparison_input_invalid")
    if type(confidence_by_race) is not dict:
        raise F11Rejected("confidence_evidence_required")
    if type(max_source_age_seconds) is not int or not 0<=max_source_age_seconds<=3600:
        raise F11Rejected("max_age_invalid")
    if type(min_confidence) not in (int,float) or not math.isfinite(min_confidence) or not 0<=min_confidence<=1:
        raise F11Rejected("min_confidence_invalid")
    now,old=utc(cutoff_utc),utc(observed_utc)
    age=(now-old).total_seconds()
    if age<0 or age>max_source_age_seconds:
        raise F11Rejected("stale_or_future_market_observation")
    comparison_keys=set()
    for c in comparisons:
        if type(c) is not dict:
            raise F11Rejected("comparison_invalid")
        key=c.get("race")
        if type(key) is not int or key in comparison_keys:
            raise F11Rejected("comparison_id_invalid")
        comparison_keys.add(key)
    if set(confidence_by_race)!=comparison_keys:
        raise F11Rejected("confidence_coverage_mismatch")
    for k,v in confidence_by_race.items():
        if type(k) is not int or type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1:
            raise F11Rejected("confidence_invalid")

    ranking=rank_lab_research_races(comparisons,daily_budget_yen=day_budget_yen,
         ticket_type=ticket_type,max_races=max_races,
         max_tickets_per_race=max_tickets_per_race,
         minimum_stressed_ev=minimum_stressed_ev)
    admitted=[]
    for r in ranking["selected"]:
        if confidence_by_race[r["race"]] < min_confidence:
            continue
        if not r["tickets"]:
            raise F11Rejected("empty_recommendation")
        admitted.append(r)
    # Confidence is a hard acceptance rule, not merely an explanation badge.
    if len(admitted)>max_races:
        raise F11Rejected("race_limit")
    explained=[]
    for position,r in enumerate(admitted,1):
        explained.append({
            "rank":position,"race_date":r["race_date"],"race":r["race"],
            "ticket_type":ticket_type,"source_p4_sha256":r["p4_comparison_sha256"],
            "best_conservative_ev":r["best_stressed_ev"],
            "confidence":confidence_by_race[r["race"]],
            "source_age_seconds":age,
            "source_observed_utc":observed_utc,
            "explanation":{
                "expectation":"conservative expected net per unit (LAB estimate)",
                "confidence":"externally supplied LAB confidence, not calibrated",
                "freshness":"seconds from snapshot to decision cutoff"},
            "tickets":[{"pair":t["pair"],"weight":max(1,int(100*(t["stressed_net_lower"]+1)))}
                       for t in r["tickets"]]
        })
    body={
      "schema":"kyoto_F11_ranked_lab_with_explanations.v1",
      "scope":"LAB_SOURCE_BOUND_P4_AND_SYNTHETIC_MODELS_NOT_JRA_AUTHENTICATED",
      "p5_ranking_sha256":ranking["ranking_sha256"],"ticket_type":ticket_type,
      "daily_budget_ceiling_yen":day_budget_yen,
      "source_observed_utc":observed_utc,"decision_cutoff_utc":cutoff_utc,
      "source_age_seconds":age,"max_races":max_races,
      "max_tickets_per_race":max_tickets_per_race,
      "selected":explained,"eligible_after_confidence":len(explained),
      "all_skip":not bool(explained),
      "manual_selectable":True,
      "source_jra_authenticated":False,"confidence_calibrated":False,
      "virtual_bets_frozen":False,"real_purchase_authorized":False}
    return {**body,"f11_sha256":digest(body)}

def handoff_f11_to_f12(*,ranking,exposure_target_yen,mode="AUTO",
                        selected_races=None,manual_race_amounts=None,
                        concentrate=True):
    if type(ranking) is not dict or ranking.get("schema")!="kyoto_F11_ranked_lab_with_explanations.v1":
        raise F11Rejected("f11_ranked_receipt_required")
    if ranking.get("f11_sha256")!=digest({k:v for k,v in ranking.items() if k!="f11_sha256"}):
        raise F11Rejected("f11_receipt_modified")
    if ranking["scope"]!="LAB_SOURCE_BOUND_P4_AND_SYNTHETIC_MODELS_NOT_JRA_AUTHENTICATED":
        raise F11Rejected("live_scope_not_permitted")
    for k in ("source_jra_authenticated","confidence_calibrated","virtual_bets_frozen","real_purchase_authorized"):
        if ranking.get(k) is not False:raise F11Rejected("false_live_certification")
    rs=ranking["selected"]
    if type(rs) is not list or len(rs)>4:
        raise F11Rejected("selected_invalid")
    candidates=[]
    for row in rs:
        if row["ticket_type"]!=ranking["ticket_type"]:
            raise F11Rejected("market_type_mismatch")
        candidates.append({"race":row["race"],"priority":row["rank"],
            "ticket_type":row["ticket_type"],"eligible":True,
            "tickets":row["tickets"]})
    if selected_races is None:selected_races=[r["race"] for r in rs]
    out=plan_f12(day_budget_yen=ranking["daily_budget_ceiling_yen"],
         exposure_target_yen=exposure_target_yen,market=ranking["ticket_type"],
         mode=mode,candidates=candidates,selected_races=selected_races,
         manual_race_amounts=manual_race_amounts,concentrate=concentrate)
    return {"f11_source_sha256":ranking["f11_sha256"],"f12_plan":out,
            "scope":"LAB_RANKING_TO_BUDGET_ONLY_NO_LIVE_FREEZE",
            "actual_purchase_authorized":False,"virtual_trade_frozen":False}
