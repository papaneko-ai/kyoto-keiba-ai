"""P6 research-only chronological virtual ledger aggregation, never real returns."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
from diagnostics.p6_fixture_durable_ledger import read_journal,LabRejected


def _time(value):
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
        if t.utcoffset()!=timezone.utc.utcoffset(None):
            raise ValueError("UTC required")
        return t
    except (AttributeError,ValueError,TypeError) as exc:
        raise LabRejected("aggregate_freeze_time_invalid") from exc


def aggregate_fixture_journals(records):
    """Read anchored journals, sort by frozen time, score settled only.

    records: [{path, expected_head}]. The external SHA head is mandatory,
    since valid-line truncation is otherwise invisible to a local journal.
    """
    if not isinstance(records,list) or not records:
        raise LabRejected("aggregate_nonempty_journal_list_required")
    seen_paths=set();seen_scenarios=set();rows=[]
    for record in records:
        if not isinstance(record,dict) or set(record)!={"path","expected_head"}:
            raise LabRejected("aggregate_journal_spec_invalid")
        path=Path(record["path"])
        if not path.is_file() or path.is_symlink():
            raise LabRejected("aggregate_journal_file_invalid")
        resolved=str(path.resolve())
        if resolved in seen_paths:
            raise LabRejected("aggregate_duplicate_journal")
        seen_paths.add(resolved)
        anchor=record["expected_head"]
        if not isinstance(anchor,str) or len(anchor)!=64 or any(c not in "0123456789abcdef" for c in anchor):
            raise LabRejected("aggregate_head_anchor_required")
        journal=read_journal(path,expected_head=anchor)
        if not journal["entries"]:
            raise LabRejected("aggregate_empty_journal")
        frozen=journal["entries"][0]["payload"]["record"]["frozen"]
        scenario=frozen["scenario_id"]
        if scenario in seen_scenarios:
            raise LabRejected("aggregate_duplicate_scenario")
        seen_scenarios.add(scenario)
        outcome=journal["result"]
        if outcome["fixture_only"] is not True or frozen["ledger_type"]!="VIRTUAL_FIXTURE_ONLY":
            raise LabRejected("aggregate_real_trade_forbidden")
        rows.append({"scenario_id":scenario,"frozen_utc":frozen["frozen_utc"],
                     "frozen_time":_time(frozen["frozen_utc"]),
                     "head_sha256":anchor,"model_version":frozen["model_version"],
                     "ticket_type":frozen["ticket_type"],"outcome":outcome})
    rows.sort(key=lambda x:(x["frozen_time"],x["scenario_id"]))
    settled=[];stake=0;payout=0;hits=0;peak=0;max_drawdown=0;profit=0
    history=[]
    for row in rows:
        outcome=row["outcome"]
        final=outcome["status"]=="FINAL_FIXTURE_ONLY"
        if final:
            if (type(outcome["stake_yen"]) is not int or
                type(outcome["payout_yen"]) is not int or
                type(outcome["profit_yen"]) is not int or
                outcome["profit_yen"]!=outcome["payout_yen"]-outcome["stake_yen"]):
                raise LabRejected("aggregate_final_arithmetic_invalid")
            stake+=outcome["stake_yen"];payout+=outcome["payout_yen"]
            profit+=outcome["profit_yen"];hits+=int(outcome["ticket_hits"]>0)
            peak=max(peak,profit)
            max_drawdown=max(max_drawdown,peak-profit)
            settled.append(row)
        elif outcome["status"] not in ("UNSETTLED","PRELIMINARY_UNSETTLED"):
            raise LabRejected("aggregate_unknown_settlement_status")
        history.append({"scenario_id":row["scenario_id"],"frozen_utc":row["frozen_utc"],
                        "status":outcome["status"],"cumulative_profit_yen":profit,
                        "cumulative_stake_yen":stake,
                        "cumulative_roi_percent":100*payout/stake if stake else None})
    midpoint=len(settled)//2
    def cohort(items):
        s=sum(x["outcome"]["stake_yen"] for x in items)
        p=sum(x["outcome"]["payout_yen"] for x in items)
        return {"races":len(items),"stake_yen":s,"payout_yen":p,
                "profit_yen":p-s,"roi_percent":100*p/s if s else None}
    early=cohort(settled[:midpoint]);late=cohort(settled[midpoint:])
    return {"schema":"kyoto_p6_fixture_temporal_aggregate.v1",
            "status":"RESEARCH_VIRTUAL_ONLY_NOT_LIVE",
            "total_scenarios":len(rows),"settled_scenarios":len(settled),
            "unsettled_scenarios":len(rows)-len(settled),
            "stake_yen":stake,"payout_yen":payout,"profit_yen":profit,
            "roi_percent":100*payout/stake if stake else None,
            "race_hit_rate_percent":100*hits/len(settled) if settled else None,
            "max_drawdown_yen":max_drawdown,
            "first_half":early,"second_half":late,
            "second_minus_first_roi_points":(
                late["roi_percent"]-early["roi_percent"]
                if early["roi_percent"] is not None and late["roi_percent"] is not None else None),
            "chronological_history":history,
            "actual_purchase":False,"official_results_verified":False,
            "prediction_ready":False}


def aggregate_model_version_cohorts(records):
    """P6-04: aggregate independently anchored fixture journals by model version.

    This is a DESCRIPTIVE unpaired time-series breakdown; versions may have
    different races/periods. No superiority/adoption claim or real return.
    All anchors are validated by aggregate_fixture_journals *before* grouping.
    A corrected final settlement supersedes the earlier payout via read_journal.
    """
    import hashlib
    import json
    base=aggregate_fixture_journals(records)
    versions={}
    for record in records:
        current=read_journal(record["path"],expected_head=record["expected_head"])
        frozen=current["entries"][0]["payload"]["record"]["frozen"]
        version=frozen["model_version"]
        if type(version) is not str or not version:
            raise LabRejected("model_version_invalid")
        versions.setdefault(version,[]).append(record)
    groups={}
    for version in sorted(versions):
        a=aggregate_fixture_journals(versions[version])
        groups[version]={
            "total_scenarios":a["total_scenarios"],
            "settled_scenarios":a["settled_scenarios"],
            "unsettled_scenarios":a["unsettled_scenarios"],
            "stake_yen":a["stake_yen"],
            "payout_yen":a["payout_yen"],
            "profit_yen":a["profit_yen"],
            "roi_percent":a["roi_percent"],
            "race_hit_rate_percent":a["race_hit_rate_percent"],
            "max_drawdown_yen":a["max_drawdown_yen"],
            "first_half":a["first_half"],
            "second_half":a["second_half"],
            "chronological_history":a["chronological_history"]
        }
    # No cross-model ranking: unequal race samples are not a paired holdout.
    output={
        "schema":"kyoto_p6_fixture_model_cohorts.v1",
        "scope":"LAB_ONLY_UNPAIRED_DESCRIPTIVE_NOT_MODEL_SELECTION",
        "total_scenarios":base["total_scenarios"],
        "settled_scenarios":base["settled_scenarios"],
        "unsettled_scenarios":base["unsettled_scenarios"],
        "total_stake_yen":base["stake_yen"],
        "total_payout_yen":base["payout_yen"],
        "total_profit_yen":base["profit_yen"],
        "overall_roi_percent":base["roi_percent"],
        "max_drawdown_yen":base["max_drawdown_yen"],
        "model_version_cohorts":groups,
        "unpaired_comparison_may_be_biased":True,
        "model_adoption_authorized":False,
        "official_result_verified":False,
        "real_racing_performance_verified":False,
        "actual_purchase":False
    }
    digest=hashlib.sha256(json.dumps(output,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {**output,"receipt_sha256":digest}
