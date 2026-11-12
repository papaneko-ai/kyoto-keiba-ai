"""Independent F16 offline lab auditor; does NOT import the journal or stats code.

Read-only SQLite event replay from pinned first CI artifact, checks chain and
exact 3 settled + 1 unsettled fixture. Still NOT an authentic JRA operation.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

class F16AuditRejected(ValueError):pass
FIRST_RUN="43138143478"
FIRST_HEAD="1cf3dbf1bc989cd7eb0ef618e6b1c78c4080d60b"
RUBRIC="92bae5c1d61d6ac00a5380dd8d5e08beb59f96c898b03c05a3c8bf8721ced632"
ZERO="0"*64

def _dig(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
       separators=(",",":"),allow_nan=False).encode("utf8")).hexdigest()
def _check(v,msg):
    if not v:raise F16AuditRejected(msg)

def audit(db_path,receipt,rubric):
    if hashlib.sha256(rubric).hexdigest()!=RUBRIC:
        raise F16AuditRejected("rubric_mutation")
    rule=next(x for x in json.loads(rubric)["criteria"] if x["id"]=="F16")
    _check(rule["points"]==5 and rule["title"]=="仮想成績・リスクの自動集計","F16_fixed_rule_changed")
    _check(receipt.get("ci_run_id")==FIRST_RUN and receipt.get("ci_head_sha")==FIRST_HEAD
       and receipt.get("source_scope")=="OFFLINE_SYNTHETIC_VIRTUAL_ONLY"
       and receipt.get("source_live_authenticity") is False,"fake_or_wrong_provenance")
    path=Path(db_path)
    _check(path.is_file() and not path.is_symlink(),"invalid_db")
    _check(hashlib.sha256(path.read_bytes()).hexdigest()==receipt.get("sqlite_sha256"),"db_hash_mismatch")
    report=receipt.get("stats",{})
    _check(report.get("schema")=="kyoto_F16_virtual_performance_stats.v1"
           and report.get("scope")=="ISOLATED_LAB_REPLAY_ONLY_NOT_JRA_VERIFIED","report_scope_invalid")
    _check(report.get("stats_sha256")==_dig({k:v for k,v in report.items() if k!="stats_sha256"}),"stats_hash_invalid")
    for name in ("live_jra_authenticity_verified","production_turso_persistence_verified",
                 "real_paper_trade_stats_available","real_bet_authorized"):
        _check(report.get(name) is False,"false_live_claim")
    uri=path.resolve().as_uri()+"?mode=ro"
    con=sqlite3.connect(uri,uri=True)
    try:
        records=con.execute("SELECT event_key,race_id,event_type,payload,prev_sha256,entry_sha256 FROM events ORDER BY event_seq").fetchall()
    finally:con.close()
    prev=ZERO
    freezes={};finals={}
    for key,race,kind,raw,previous,digest in records:
        p=json.loads(raw)
        _check(raw==json.dumps(p,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False),"stored_payload_not_canonical")
        _check(previous==prev and digest==_dig({"event_key":key,"race_id":race,"type":kind,"payload":p,"prev_sha256":previous}),"event_chain_tampered")
        prev=digest
        if kind=="FREEZE":
            _check(race not in freezes and key=="freeze:"+race and p.get("provenance_scope")=="UNAUTHENTICATED_LAB_INPUT","freeze_invalid")
            freezes[race]=p
        elif kind=="FINAL":
            _check(race in freezes and key=="final:"+race+":"+str(p["result_version"])
                   and p.get("result_scope")=="UNAUTHENTICATED_LAB_FINAL","final_invalid")
            finals.setdefault(race,{})[p["result_version"]]=p
        else:raise F16AuditRejected("unknown_event_type")
    _check(len(records)==8 and len(freezes)==4 and len(finals)==3,"fixture_count_wrong")
    _check(report.get("source_chain_head")==prev,"reported_chain_head_changed")
    total_stake=total_return=hits=hit_races=tickets=0
    markets={};models={}
    cumulative=peak=drawdown=0;rows=[]
    for race,plan in sorted(freezes.items()):
        if race not in finals:continue
        version=max(finals[race])
        res=finals[race][version]
        payouts={tuple(x["pair"]):x["yen_per_100"] for x in res["payouts"]}
        refunds={tuple(x) for x in res["refund_pairs"]}
        stake=sum(x["stake_yen"] for x in plan["tickets"])
        revenue=sum(x["stake_yen"]//100*payouts.get(tuple(x["pair"]),0) +
                    (x["stake_yen"] if tuple(x["pair"]) in refunds else 0)
                    for x in plan["tickets"])
        won=sum(tuple(x["pair"]) in payouts for x in plan["tickets"])
        total_stake+=stake;total_return+=revenue;hits+=won
        hit_races+=int(won>0);tickets+=len(plan["tickets"])
        profit=revenue-stake;cumulative+=profit;peak=max(peak,cumulative)
        drawdown=max(drawdown,peak-cumulative)
        models[plan["model_version"]]=models.get(plan["model_version"],0)+profit
        markets[plan["ticket_type"]]=markets.get(plan["ticket_type"],0)+revenue
        rows.append((race,stake,revenue,won,version,cumulative,peak-cumulative))
    _check(len(rows)==3 and len(freezes)-len(rows)==1,"settlement_or_unsettled_wrong")
    _check((total_stake,total_return,hits,hit_races,tickets,drawdown)==(600,1500,2,2,6,200),"separate_recalculation_wrong")
    _check(markets=={"QUINELLA":600,"BRACKET":900}
           and models=={"MODEL-A":1100,"MODEL-B":-200},"market_model_breakdown_wrong")
    totals=report["totals"]
    _check((totals["stake_yen"],totals["return_yen"],totals["profit_yen"],
           totals["hit_tickets"],totals["hit_races"],totals["settled_tickets"])==
           (total_stake,total_return,total_return-total_stake,hits,hit_races,tickets),"reported_totals_wrong")
    _check(report["max_realized_drawdown_yen"]==drawdown
           and report["unsettled_races_excluded_from_roi"]==1
           and report["totals"]["roi_percent"]==250.0,"reported_drawdown_or_roi_wrong")
    for original,computed in zip(report["chronological_settled_races"],rows):
        _check((original["race_id"],original["stake_yen"],original["return_yen"],
                original["hit_tickets"],original["final_version"],
                original["cumulative_profit_yen"],original["drawdown_from_peak_yen"])==computed,
                "per_race_replay_mismatch")
    return {"schema":"kyoto_F16_second_independent_lab_verification.v1",
            "gate":"F16","accepted_points":5,
            "source_ci_run_id":int(FIRST_RUN),"source_ci_sha":FIRST_HEAD,
            "source_chain_head":prev,"source_stats_sha256":report["stats_sha256"],
            "verified_settled_races":len(rows),"verified_unsettled_races":1,
            "stake_yen":total_stake,"return_yen":total_return,
            "profit_yen":total_return-total_stake,"max_drawdown_yen":drawdown,
            "independent_method":"sqlite_readonly_event_replay_without_target_modules",
            "verified_live_jra":False,"verified_production_turso":False,
            "verified_real_paper_trading":False}
