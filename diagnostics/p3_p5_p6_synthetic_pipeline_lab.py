"""P3->P5->P6 isolated offline paper-investment LAB adapter.

Only explicit synthetic market prices. The strict real-market path remains
blocked until independently authenticated pre-race JRA odds and a certified
model exist. This module has no HTTP, production ledger, or purchase access.
"""
from __future__ import annotations
from math import isfinite
from diagnostics.p3_offline_model_tournament import predict,_hash,_utc,TournamentRejected
from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture,settle_fixture

class LabBridgeRejected(ValueError):pass

def _money(value):
    return type(value) in (float,int) and isfinite(value) and 1<value<100000

def freeze_lab_market_scenario(snapshot,*,model_id,synthetic_market,
                               observed_utc,frozen_utc,daily_budget_yen,
                               ticket_type="QUINELLA",max_tickets=2,
                               uncertainty_fraction=.20):
    if (ticket_type not in ("QUINELLA","BRACKET") or
        type(daily_budget_yen) is not int or not 0<=daily_budget_yen<=1_000_000 or
        daily_budget_yen%100 or type(max_tickets) is not int or
        not 1<=max_tickets<=3 or type(uncertainty_fraction) not in (int,float)
        or not isfinite(uncertainty_fraction) or not 0<=uncertainty_fraction<1):
        raise LabBridgeRejected("market_or_budget_policy_invalid")
    if (type(synthetic_market) is not dict or
        set(synthetic_market)!={"race_id","market_type","scope","prices"} or
        synthetic_market.get("scope")!="LAB_SYNTHETIC_ODDS_ONLY" or
        synthetic_market.get("race_id")!=snapshot.get("race_id") or
        synthetic_market.get("market_type")!=ticket_type):
        raise LabBridgeRejected("synthetic_market_identity_invalid")
    if (not _utc(snapshot["feature_cutoff_utc"])<=_utc(observed_utc)
        or not _utc(observed_utc)<=_utc(frozen_utc)
        or not _utc(frozen_utc)<_utc(snapshot["race_start_utc"])):
        raise LabBridgeRejected("market_not_observed_before_freeze")
    forecast=predict(snapshot,model_id)
    market=forecast["quinella"] if ticket_type=="QUINELLA" else forecast["bracket"]
    raw=synthetic_market["prices"]
    if type(raw) is not list or len(raw)!=len(market):
        raise LabBridgeRejected("market_incomplete")
    expected={tuple(row["pair"]):row["probability"] for row in market}
    prices={}
    for row in raw:
        if type(row) is not dict or set(row)!={"pair","decimal_odds"}:
            raise LabBridgeRejected("price_row_invalid")
        pair=row["pair"]
        if (type(pair) is not list or len(pair)!=2 or
            any(type(x) is not int for x in pair) or pair!=sorted(pair)
            or (pair[0]==pair[1] and ticket_type=="QUINELLA") or
            tuple(pair) not in expected or tuple(pair) in prices or
            not _money(row["decimal_odds"])):
            raise LabBridgeRejected("price_duplicate_or_invalid")
        prices[tuple(pair)]=float(row["decimal_odds"])
    if set(prices)!=set(expected):
        raise LabBridgeRejected("market_pair_coverage_mismatch")
    scores=[]
    for pair,p in expected.items():
        robust=p*prices[pair]*(1-uncertainty_fraction)-1
        if robust>0:
            scores.append((robust,pair,p,prices[pair]))
    scores.sort(key=lambda row:(-row[0],row[1]))
    exposure_cap=(daily_budget_yen*35//10000)*100
    pair_cap=(daily_budget_yen*12//10000)*100
    race_cap=(daily_budget_yen*20//10000)*100
    cap=min(exposure_cap,race_cap)
    tickets=[]
    spent=0
    for _,pair,p,odds in scores:
        if len(tickets)>=max_tickets:break
        stake=min(pair_cap,cap-spent)
        if stake<100:continue
        tickets.append({"pair":list(pair),"stake_yen":stake,
                        "probability":p,"odds":odds})
        spent+=stake
    basis={"forecast_sha256":forecast["forecast_sha256"],
           "market_sha256":_hash(synthetic_market),
           "observed_utc":observed_utc,"frozen_utc":frozen_utc,
           "policy":{"budget_yen":daily_budget_yen,"max_tickets":max_tickets,
                     "uncertainty_fraction":uncertainty_fraction,
                     "max_exposure_fraction":.35,"max_race_fraction":.20,
                     "max_pair_fraction":.12}}
    frozen=None
    if tickets:
        frozen=freeze_fixture(
            scenario_id="LAB-P3-P6-"+snapshot["race_id"][4:],
            ticket_type=ticket_type,cutoff_utc=snapshot["race_start_utc"],
            frozen_utc=frozen_utc,model_version=model_id,
            source_sha256=_hash(basis),tickets=tickets)
    receipt={"schema":"kyoto_p3_p5_p6_synthetic_pipeline.v1",
        "race_id":snapshot["race_id"],"ticket_type":ticket_type,
        "model_id":model_id,"forecast_sha256":forecast["forecast_sha256"],
        "synthetic_market_sha256":_hash(synthetic_market),
        "risk_policy_sha256":_hash(basis["policy"]),
        "scenario_sha256":frozen["frozen_sha256"] if frozen else None,
        "status":"LAB_FIXTURE_FROZEN" if frozen else "LAB_SKIP_NO_POSITIVE_ROBUST_EV",
        "ticket_count":len(tickets),"spent_yen":spent,
        "unspent_yen":daily_budget_yen-spent,
        "frozen_utc":frozen_utc,"source_authenticated":False,
        "real_market_verified":False,"model_calibrated":False,
        "official_settlement":False,"actual_purchase":False}
    return {"receipt":{**receipt,"receipt_sha256":_hash(receipt)},
            "frozen":frozen}

def replay_lab_settlement(pipeline,events):
    if type(pipeline) is not dict or set(pipeline)!={"receipt","frozen"}:
        raise LabBridgeRejected("pipeline_schema_invalid")
    receipt=pipeline["receipt"]
    if _hash({k:v for k,v in receipt.items() if k!="receipt_sha256"})!=receipt.get("receipt_sha256"):
        raise LabBridgeRejected("pipeline_receipt_modified")
    frozen=pipeline["frozen"]
    if receipt["status"]=="LAB_SKIP_NO_POSITIVE_ROBUST_EV":
        if frozen is not None or events:
            raise LabBridgeRejected("skipped_scenario_cannot_settle")
        return {"status":"SKIPPED_LAB_NO_POSITION","profit_yen":0,
                "not_official":True,"virtual_only":True}
    if receipt["status"]!="LAB_FIXTURE_FROZEN" or frozen is None or receipt["scenario_sha256"]!=frozen.get("frozen_sha256"):
        raise LabBridgeRejected("missing_frozen_linkage")
    result=settle_fixture(frozen,events)
    return {**result,"not_official":True,"virtual_only":True}
