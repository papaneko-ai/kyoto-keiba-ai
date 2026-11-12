"""F12 independent-input ticket type / amount planner; NO actual tickets or bet API.

Deterministic and explicit: daily budget is an upper limit, never forced spend.
"manual" allocations only for selected races, arbitrary cap per race, at most
3 ticket pairs per race; "auto" prioritizes earlier rank through per-race
weighted allocation. Calls existing 100yen allocator for fixed-target weights,
then validates all pair identity and 100yen caps after user overrides.

No JRA source authenticity or expected-value profitability assertion.
"""
from __future__ import annotations
import hashlib
import json
from diagnostics.p5_manual_allocation import allocate

class F12Rejected(ValueError): pass
TYPES={"QUINELLA","BRACKET"}
def _amount(v,label):
    if type(v) is not int or not 0<=v<=1_000_000 or v%100:
        raise F12Rejected(label+"_invalid")
def _pair(v,market):
    if type(v) is not list or len(v)!=2 or any(type(x) is not int for x in v):
        raise F12Rejected("pair_invalid")
    a,b=v
    limit=18 if market=="QUINELLA" else 8
    if not 1<=a<=limit or not 1<=b<=limit or a>b or (market=="QUINELLA" and a==b):
        raise F12Rejected("pair_unavailable")
    return a,b
def _digest(r):
    return hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()

def plan_f12(*,day_budget_yen,exposure_target_yen,market,mode,candidates,
             selected_races,manual_race_amounts=None,concentrate=True):
    _amount(day_budget_yen,"budget")
    _amount(exposure_target_yen,"exposure")
    if exposure_target_yen>day_budget_yen:
        raise F12Rejected("exposure_above_budget")
    if market not in TYPES or mode not in ("AUTO","MANUAL") or type(concentrate) is not bool:
        raise F12Rejected("mode_market_invalid")
    if type(candidates) is not list or len(candidates)>12:
        raise F12Rejected("candidates_invalid")
    if type(selected_races) is not list or len(selected_races)>4 or any(
         type(r) is not int or not 1<=r<=12 for r in selected_races):
        raise F12Rejected("selected_races_invalid")
    if len(set(selected_races))!=len(selected_races):
        raise F12Rejected("selected_duplicate")
    by_race={}
    for c in candidates:
        if type(c) is not dict or set(c)!={"race","priority","tickets","eligible","ticket_type"}:
            raise F12Rejected("candidate_schema_invalid")
        race,priority=c["race"],c["priority"]
        if c["ticket_type"]!=market:
            raise F12Rejected("candidate_ticket_type_mismatch")
        if type(race) is not int or not 1<=race<=12 or race in by_race:
            raise F12Rejected("race_invalid")
        if type(priority) is not int or not 1<=priority<=12:
            raise F12Rejected("priority_invalid")
        if type(c["eligible"]) is not bool or type(c["tickets"]) is not list:
            raise F12Rejected("eligibility_invalid")
        if not 1<=len(c["tickets"])<=3:
            raise F12Rejected("ticket_count_invalid")
        pairs=[]
        for ticket in c["tickets"]:
            if type(ticket) is not dict or set(ticket)!={"pair","weight"}:
                raise F12Rejected("ticket_schema_invalid")
            pair=_pair(ticket["pair"],market)
            if type(ticket["weight"]) is not int or not 0<=ticket["weight"]<=100:
                raise F12Rejected("weight_invalid")
            if pair in pairs:
                raise F12Rejected("duplicate_ticket")
            pairs.append(pair)
        by_race[race]=c
    if len({x["priority"] for x in candidates})!=len(candidates):
        raise F12Rejected("duplicate_rank")
    if any(r not in by_race or not by_race[r]["eligible"] for r in selected_races):
        raise F12Rejected("unavailable_race_selected")
    ordered=sorted(selected_races,key=lambda r:(by_race[r]["priority"],r))
    if mode=="MANUAL":
        if type(manual_race_amounts) is not dict or set(manual_race_amounts)!=set(ordered):
            raise F12Rejected("manual_race_amounts_invalid")
        for key,v in manual_race_amounts.items():
            _amount(v,"manual_amount")
        total_target=sum(manual_race_amounts.values())
        if total_target>exposure_target_yen:
            raise F12Rejected("manual_amount_exceeds_target")
        race_amounts={r:manual_race_amounts[r] for r in ordered}
    else:
        if manual_race_amounts not in (None,{}):
            raise F12Rejected("auto_manual_conflict")
        if not ordered:
            race_amounts={}
        else:
            race_weights=[max(1,(5-i)**2) if concentrate else 1 for i,_ in enumerate(ordered)]
            amounts=allocate(exposure_target_yen,race_weights)
            race_amounts=dict(zip(ordered,amounts))
    result=[]
    for r in ordered:
        cand=by_race[r]
        weights=[t["weight"] for t in cand["tickets"]]
        if sum(weights)==0 and race_amounts[r]>0:
            raise F12Rejected("nonzero_amount_without_weights")
        amounts=allocate(race_amounts[r],weights) if sum(weights)>0 else [0]*len(weights)
        result.append({"race":r,"priority":cand["priority"],"stake_yen":sum(amounts),
         "tickets":[{"pair":t["pair"],"stake_yen":a,
                     "allocation_percent":round(100*a/max(1,sum(amounts)),2)}
                   for t,a in zip(cand["tickets"],amounts) if a>0]})
    spent=sum(x["stake_yen"] for x in result)
    if spent>exposure_target_yen or spent>day_budget_yen:
        raise F12Rejected("budget_overspent")
    out={"schema":"kyoto_F12_independent_budget_plan.v1",
      "scope":"OFFLINE_MANUAL_OR_AUTO_PLANNING_NOT_A_BET",
      "mode":mode,"ticket_type":market,"day_budget_ceiling_yen":day_budget_yen,
      "exposure_target_yen":exposure_target_yen,"spent_yen":spent,
      "unspent_yen":day_budget_yen-spent,"selected":result,
      "selected_race_count":len(ordered),"user_selected_races":selected_races,
      "max_races":4,"max_ticket_per_race":3,
      "manual_adjustment_supported":True,"real_source_verified":False,
      "model_calibrated":False,"real_purchase_authorized":False}
    return {**out,"plan_sha256":_digest(out)}
