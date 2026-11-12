"""P6 F16 replay-only statistics from the existing immutable virtual SQLite journal.

No HTTP, no Turso, no real tickets. Only LAB events are accepted by the
underlying journal. Unsettled races are excluded from settled ROI (not losses).
Corrected results REPLACE older versions rather than doubling income.
Drawdown is measured on chronological realized LAB P&L, not paper forecasts.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from diagnostics.kyoto_virtual_sqlite_journal import (
    _connect, _load, dashboard, VirtualLedgerRejected
)

class StatsRejected(ValueError):pass

def _hash(data):
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()

def _bucket():
    return {"settled_races":0,"settled_tickets":0,"hit_races":0,
            "hit_tickets":0,"stake_yen":0,"return_yen":0,"profit_yen":0}

def _rate(a,b):
    return round(100*a/b,3) if b else None

def _finish(d):
    return {**d,"roi_percent":_rate(d["return_yen"],d["stake_yen"]),
       "ticket_hit_percent":_rate(d["hit_tickets"],d["settled_tickets"]),
       "race_hit_percent":_rate(d["hit_races"],d["settled_races"])}

def summarize_lab_journal(db_path):
    if not Path(db_path).is_file():
        raise StatsRejected("existing_journal_required")
    with _connect(db_path) as con:
        events,frozen,finals=_load(con)
    # Strict cryptographic replay is validated before any arithmetic.
    official_dashboard=dashboard(db_path)
    settled=[]
    by_market,by_model={},{}
    totals=_bucket()
    unknown=0
    for race,plan in sorted(frozen.items()):
        versions=[v for (key,v) in finals if key==race]
        if not versions:
            unknown+=1
            continue
        result=finals[(race,max(versions))]
        pay={tuple(t["pair"]):t["yen_per_100"] for t in result["payouts"]}
        refund={tuple(p) for p in result["refund_pairs"]}
        stake=sum(t["stake_yen"] for t in plan["tickets"])
        returns=0
        wins=0
        for ticket in plan["tickets"]:
            pair=tuple(ticket["pair"])
            value=ticket["stake_yen"]//100*pay.get(pair,0)
            if pair in refund:value+=ticket["stake_yen"]
            returns+=value
            wins+=int(pair in pay)
        market=plan["ticket_type"]
        model=plan["model_version"]
        row={"race_id":race,"ticket_type":market,"model_version":model,
             "stake_yen":stake,"return_yen":returns,
             "profit_yen":returns-stake,"tickets":len(plan["tickets"]),
             "hit_tickets":wins,"hit_race":wins>0,
             "final_version":max(versions),"source_scope":"LAB_UNAUTHENTICATED"}
        settled.append(row)
        for bucket in (totals,by_market.setdefault(market,_bucket()),
                       by_model.setdefault(model,_bucket())):
            bucket["settled_races"]+=1
            bucket["settled_tickets"]+=len(plan["tickets"])
            bucket["hit_races"]+=int(wins>0)
            bucket["hit_tickets"]+=wins
            bucket["stake_yen"]+=stake
            bucket["return_yen"]+=returns
            bucket["profit_yen"]+=returns-stake

    # race_id is YYYYMMDD-KYOTO-RXX, so sorting is chronological.
    # Peak starts at zero, no intra-race mark-to-market is invented.
    cumulative=peak=max_drawdown=0
    for row in settled:
        cumulative+=row["profit_yen"]
        peak=max(peak,cumulative)
        max_drawdown=max(max_drawdown,peak-cumulative)
        row["cumulative_profit_yen"]=cumulative
        row["drawdown_from_peak_yen"]=peak-cumulative

    if (totals["settled_races"]!=official_dashboard["settled_races"]
        or unknown!=official_dashboard["unsettled_races"]
        or totals["stake_yen"]!=official_dashboard["settled_stake_yen"]
        or totals["return_yen"]!=official_dashboard["settled_return_yen"]
        or totals["profit_yen"]!=official_dashboard["settled_profit_yen"]
        or totals["hit_tickets"]!=official_dashboard["hit_ticket_count"]):
        raise StatsRejected("ledger_dashboard_disagrees_with_statistics")
    result={
       "schema":"kyoto_F16_virtual_performance_stats.v1",
       "scope":"ISOLATED_LAB_REPLAY_ONLY_NOT_JRA_VERIFIED",
       "event_count":len(events),"source_chain_head":official_dashboard["chain_head"],
       "frozen_races":len(frozen),"settled_races":len(settled),
       "unsettled_races_excluded_from_roi":unknown,
       "totals":_finish(totals),
       "max_realized_drawdown_yen":max_drawdown,
       "by_ticket_type":{k:_finish(v) for k,v in sorted(by_market.items())},
       "by_model_version":{k:_finish(v) for k,v in sorted(by_model.items())},
       "chronological_settled_races":settled,
       "corrected_versions_replace_earlier_results":True,
       "refunds_count_as_hits":False,
       "live_jra_authenticity_verified":False,
       "production_turso_persistence_verified":False,
       "real_paper_trade_stats_available":False,
       "real_bet_authorized":False
    }
    return {**result,"stats_sha256":_hash(result)}
