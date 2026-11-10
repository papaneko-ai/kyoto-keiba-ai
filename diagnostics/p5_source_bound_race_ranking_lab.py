"""P5-02 research-only ranking and budget ceiling from P4-02 EV receipts.

No independent JRA origin, calibrated model, live odds, or betting.
The fixed research rule ranks by conservative per-unit EV, chooses at most
two pairs per race and normally at most three races (max four by override).
It never spends budget just to exhaust it. Receipt digest is replayable.
"""
from __future__ import annotations
import hashlib
import json
import math

class RankingRejected(ValueError):pass

def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()

def rank_lab_research_races(comparisons, *, daily_budget_yen,
                            ticket_type="QUINELLA", max_races=3,
                            max_tickets_per_race=2, stake_per_ticket_yen=100,
                            minimum_stressed_ev=0.0):
    if type(comparisons) is not list or not 1<=len(comparisons)<=12:
        raise RankingRejected("one_to_twelve_comparisons_required")
    if type(daily_budget_yen) is not int or not 0<=daily_budget_yen<=1_000_000 or daily_budget_yen%100:
        raise RankingRejected("budget_ceiling_invalid")
    if ticket_type not in ("QUINELLA","BRACKET"):
        raise RankingRejected("ticket_type_invalid")
    if type(max_races) is not int or not 1<=max_races<=4:
        raise RankingRejected("race_cap_invalid")
    if type(max_tickets_per_race) is not int or not 1<=max_tickets_per_race<=3:
        raise RankingRejected("ticket_cap_invalid")
    if (type(stake_per_ticket_yen) is not int or stake_per_ticket_yen<100
        or stake_per_ticket_yen%100):
        raise RankingRejected("stake_invalid")
    if (type(minimum_stressed_ev) not in (int,float) or
        not math.isfinite(minimum_stressed_ev) or minimum_stressed_ev<0):
        raise RankingRejected("stressed_ev_floor_invalid")
    seen=set()
    scored=[]
    for c in comparisons:
        if type(c) is not dict or c.get("schema")!="kyoto_p4_source_bound_model_market_comparison.v1":
            raise RankingRejected("p4_original_bound_receipt_required")
        proof=c.get("comparison_sha256")
        if type(proof) is not str or _hash({k:v for k,v in c.items() if k!="comparison_sha256"})!=proof:
            raise RankingRejected("p4_receipt_tampered")
        if (c.get("scope")!="STRICT_ORIGINAL_CONTENT_PLUS_SYNTHETIC_MODEL_ONLY" or
            c.get("source_official_origin_authenticated") is not False or
            c.get("model_externally_calibrated") is not False or
            c.get("real_race_prediction_ready") is not False or
            c.get("actual_purchase_authorized") is not False or
            c.get("real_paper_trades_written")!=0):
            raise RankingRejected("unauthorized_live_market_claim")
        day,race=c.get("race_date"),c.get("race")
        if (type(day) is not str or type(race) is not int or not 1<=race<=12
            or (day,race) in seen):
            raise RankingRejected("duplicate_or_invalid_race")
        seen.add((day,race))
        m=c.get("markets")
        if type(m) is not dict or set(m)!={"QUINELLA","BRACKET"}:
            raise RankingRejected("both_markets_required")
        for market in m.values():
            if type(market) is not dict or type(market.get("research_model_expected_net")) is not list:
                raise RankingRejected("market_report_invalid")
            if len(market["research_model_expected_net"])!=market.get("full_pair_count"):
                raise RankingRejected("market_report_count_mismatch")
        pairs=m[ticket_type]["research_model_expected_net"]
        accepted=[]
        unique=set()
        for t in pairs:
            if type(t) is not dict or set(t)!={"pair","expected_net_per_unit","stressed_net_lower"}:
                raise RankingRejected("pair_report_invalid")
            pair=t["pair"];v=t["stressed_net_lower"];ev=t["expected_net_per_unit"]
            if (type(pair) is not list or len(pair)!=2 or any(type(n) is not int for n in pair)
                or pair[0]>pair[1] or tuple(pair) in unique or
                type(v) not in (int,float) or not math.isfinite(v) or
                type(ev) not in (int,float) or not math.isfinite(ev)):
                raise RankingRejected("pair_report_not_finite_or_unique")
            unique.add(tuple(pair))
            if v>minimum_stressed_ev:
                accepted.append({"pair":pair,"stressed_net_lower":v,
                                 "model_expected_net":ev})
        accepted.sort(key=lambda x:(-x["stressed_net_lower"],x["pair"]))
        if accepted:
            scored.append({"race_date":day,"race":race,
               "p4_comparison_sha256":proof,
               "best_stressed_ev":accepted[0]["stressed_net_lower"],
               "tickets":accepted[:max_tickets_per_race]})
    scored.sort(key=lambda x:(-x["best_stressed_ev"],x["race_date"],x["race"]))
    selected=[];spent=0
    for row in scored:
        if len(selected)>=max_races:break
        tickets=[]
        for p in row["tickets"]:
            if spent+stake_per_ticket_yen>daily_budget_yen:break
            tickets.append({**p,"stake_yen":stake_per_ticket_yen})
            spent+=stake_per_ticket_yen
        if tickets:selected.append({"rank":len(selected)+1,**{k:v for k,v in row.items() if k!="tickets"},
                                    "tickets":tickets,
                                    "research_stake_yen":sum(t["stake_yen"] for t in tickets)})
    body={"schema":"kyoto_p5_source_bound_research_ranking.v1",
       "scope":"P4_LAB_RECEIPTS_ONLY_NOT_REAL_RACING",
       "ticket_type":ticket_type,"daily_budget_ceiling_yen":daily_budget_yen,
       "max_races":max_races,"max_tickets_per_race":max_tickets_per_race,
       "selected":selected,"available_positive_ev_races":len(scored),
       "research_spent_yen":spent,"unspent_yen":daily_budget_yen-spent,
       "no_forced_budget_spend":True,
       "independent_live_predictions_verified":False,
       "real_paper_trade_recorded":False,"actual_purchase_authorized":False}
    return {**body,"ranking_sha256":_hash(body)}
