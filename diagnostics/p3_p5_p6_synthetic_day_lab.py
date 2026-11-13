"""Research-only P3/P5/P6 whole-day bounded synthetic portfolio.

Reuse the per-race P3 forecast, synthetic price guard, P5 conservative
spending, and P6 immutable fixture freeze. No real JRA market or wager.
"""
from __future__ import annotations
from datetime import timezone
from math import fsum
from diagnostics.p3_p5_p6_synthetic_pipeline_lab import (
    freeze_lab_market_scenario,LabBridgeRejected)
from diagnostics.p3_offline_model_tournament import _hash,_utc,predict

def freeze_lab_day(rows,*,daily_budget_yen,model_id="PL_BASE",
                   ticket_type="QUINELLA",max_races=3,max_tickets=2,
                   uncertainty_fraction=.20):
    if (type(rows) is not list or not 1<=len(rows)<=12 or
        type(daily_budget_yen) is not int or
        not 0<=daily_budget_yen<=1_000_000 or daily_budget_yen%100 or
        type(max_races) is not int or not 1<=max_races<=4 or
        type(max_tickets) is not int or not 1<=max_tickets<=3):
        raise LabBridgeRejected("daily_policy_invalid")
    seen=set();date=None;ranked=[]
    for row in rows:
        if type(row) is not dict or set(row)!={"snapshot","synthetic_market","observed_utc","frozen_utc"}:
            raise LabBridgeRejected("day_row_schema_invalid")
        s=row["snapshot"]
        if type(s) is not dict or type(s.get("race_id")) is not str:
            raise LabBridgeRejected("day_race_identity_invalid")
        rid=s["race_id"];start=_utc(s["race_start_utc"])
        if rid in seen:raise LabBridgeRejected("day_duplicate_race")
        seen.add(rid)
        on_date=start.astimezone(timezone.utc).date()
        if date is not None and date!=on_date:raise LabBridgeRejected("day_mixed_utc_dates")
        date=on_date
        # All market and chronology checks are reused before selection.
        check=freeze_lab_market_scenario(
            s,model_id=model_id,synthetic_market=row["synthetic_market"],
            observed_utc=row["observed_utc"],frozen_utc=row["frozen_utc"],
            daily_budget_yen=daily_budget_yen,ticket_type=ticket_type,
            max_tickets=max_tickets,uncertainty_fraction=uncertainty_fraction)
        forecast=predict(s,model_id)
        probs={tuple(x["pair"]):x["probability"] for x in
               forecast["quinella" if ticket_type=="QUINELLA" else "bracket"]}
        best=max((probs[tuple(x["pair"])]*x["decimal_odds"]*(1-uncertainty_fraction)-1
                  for x in row["synthetic_market"]["prices"]),default=-1)
        ranked.append((best,rid,row,check))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    # Reserve a fixed per-race slice before any freeze; not all budget is at risk.
    allocation=(daily_budget_yen//max_races//100)*100
    selected=[];skipped=[];spent=0
    for score,rid,row,_ in ranked:
        if score<=0 or len(selected)>=max_races:
            skipped.append({"race_id":rid,"reason":"NO_POSITIVE_EDGE_OR_RACE_CAP"})
            continue
        attempt=freeze_lab_market_scenario(
            row["snapshot"],model_id=model_id,
            synthetic_market=row["synthetic_market"],
            observed_utc=row["observed_utc"],frozen_utc=row["frozen_utc"],
            daily_budget_yen=allocation,ticket_type=ticket_type,
            max_tickets=max_tickets,uncertainty_fraction=uncertainty_fraction)
        if not attempt["frozen"]:
            skipped.append({"race_id":rid,"reason":"ROUNDING_OR_RISK_GUARD"})
            continue
        cost=attempt["receipt"]["spent_yen"]
        spent+=cost
        selected.append({"rank":len(selected)+1,"race_id":rid,
            "budget_slice_yen":allocation,"stake_yen":cost,
            "forecast_source_sha256":row["snapshot"]["feature_source_sha256"],
            "pipeline":attempt})
    if spent>daily_budget_yen or spent>(daily_budget_yen*35//10000)*100:
        raise LabBridgeRejected("day_risk_cap_broken")
    body={"schema":"kyoto_p3_p5_p6_daily_synthetic.v1",
          "source_scope":"LAB_SYNTHETIC_ODDS_ONLY",
          "day_utc":date.isoformat(),"model_id":model_id,
          "ticket_type":ticket_type,"daily_budget_yen":daily_budget_yen,
          "max_races":max_races,"max_tickets_per_race":max_tickets,
          "selected":selected,"skipped":skipped,"spent_yen":spent,
          "unspent_yen":daily_budget_yen-spent,
          "zero_spend_allowed":True,"official_jra_authenticated":False,
          "real_paper_trade_recorded":False,"real_purchase_authorized":False}
    return {**body,"day_sha256":_hash(body)}
