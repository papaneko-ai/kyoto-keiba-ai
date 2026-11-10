"""P6-02 isolated LAB pre-result freeze of P1/P4/P5 chain.

Each race's genuine saved HTML bytes are validated by the existing P1 gate.
P4 risk comparison and P5 selection are *recomputed from those bytes* before
any state is written. Journal is staged off-path, then published as a new
directory without overwriting an existing record. Does NOT prove live JRA
origin, authorized data collection, calibrated forecasts, or real paper trades.
"""
from __future__ import annotations
import hashlib
import json
import tempfile
import os
from pathlib import Path
from diagnostics.p4_source_bound_model_ev_research import compare_source_market_to_frozen_model, _utc
from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races
from diagnostics.p3_p6_research_no_bet import quinella_from_strength,bracket_from_quinella
from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture
from diagnostics.p6_fixture_durable_ledger import append_record,read_journal

class FrozenRankingRejected(ValueError):pass

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
                separators=(",",":"),allow_nan=False).encode()).hexdigest()

def freeze_ranked_research_day(*,day_inputs, ranking, destination,
                               commit_utc, stake_per_ticket_yen=100):
    """day_inputs: list of P4 argument dictionaries, no real/network IO.

    Preflight compares P4 receipts and recalculates P5 with the exact displayed
    caps and stake. No results or payout values are accepted by this API.
    Destination directory must be absent. Existing main, Turso, public app
    or purchase systems are unreachable.
    """
    if type(day_inputs) is not list or not 1<=len(day_inputs)<=12:
        raise FrozenRankingRejected("day_inputs_invalid")
    if type(ranking) is not dict or ranking.get("schema")!="kyoto_p5_source_bound_research_ranking.v1":
        raise FrozenRankingRejected("p5_receipt_required")
    if type(commit_utc) is not str:
        raise FrozenRankingRejected("independent_commit_utc_required")
    target=Path(destination)
    if target.exists() or target.is_symlink() or not target.parent.is_dir():
        raise FrozenRankingRejected("immutable_target_must_be_new")
    if type(stake_per_ticket_yen) is not int or stake_per_ticket_yen<100 or stake_per_ticket_yen%100:
        raise FrozenRankingRejected("stake_invalid")
    records={}
    comparisons=[]
    for a in day_inputs:
        if type(a) is not dict or set(a)!={"bundle","snapshot","observed_utc","channel","frozen_model"}:
            raise FrozenRankingRejected("complete_p4_input_required")
        c=compare_source_market_to_frozen_model(**a)
        key=(c["race_date"],c["race"])
        if key in records:
            raise FrozenRankingRejected("duplicate_day_race")
        records[key]=(a,c)
        comparisons.append(c)
    expected=rank_lab_research_races(
        comparisons,daily_budget_yen=ranking["daily_budget_ceiling_yen"],
        ticket_type=ranking["ticket_type"],max_races=ranking["max_races"],
        max_tickets_per_race=ranking["max_tickets_per_race"],
        stake_per_ticket_yen=stake_per_ticket_yen)
    if ranking!=expected:
        raise FrozenRankingRejected("p5_ranking_recomputed_receipt_mismatch")
    if len({k[0] for k in records})!=1:
        raise FrozenRankingRejected("mixed_racing_days_forbidden")
    commits=[]
    for selected in ranking["selected"]:
        key=(selected["race_date"],selected["race"])
        a,c=records[key];snap=a["snapshot"];m=a["frozen_model"]
        if not (_utc(a["observed_utc"])<=_utc(commit_utc)<_utc(snap["prediction_cutoff_utc"])):
            raise FrozenRankingRejected("pre_cutoff_commit_required")
        if _utc(m["frozen_utc"])>_utc(commit_utc):
            raise FrozenRankingRejected("model_not_frozen_before_commit")
        strength={int(k):v for k,v in m["strengths"].items()}
        frames={r["number"]:r["bracket"] for r in snap["runners"]}
        q=quinella_from_strength(strength)
        probs=q if ranking["ticket_type"]=="QUINELLA" else bracket_from_quinella(q,frames)
        price_key="odds" if ranking["ticket_type"]=="QUINELLA" else "bracket_odds"
        prices={(x["first"],x["second"]):x["decimal"] for x in snap[price_key]}
        tickets=[]
        for ticket in selected["tickets"]:
            pair=tuple(ticket["pair"])
            if pair not in probs or pair not in prices:
                raise FrozenRankingRejected("selected_pair_not_in_original")
            tickets.append({"pair":list(pair),"stake_yen":ticket["stake_yen"],
              "probability":probs[pair],"odds":float(prices[pair])})
        scenario=f"LAB-P5-P6-{key[0].replace('-','')}-R{key[1]:02d}"
        source_hash=digest({"p4":c["comparison_sha256"],"p5":ranking["ranking_sha256"],
                            "original":c["source_bundle_sha256"],"model":c["model_sha256"]})
        frozen=freeze_fixture(scenario_id=scenario,ticket_type=ranking["ticket_type"],
              cutoff_utc=snap["prediction_cutoff_utc"],frozen_utc=commit_utc,
              model_version=m["model_version"],source_sha256=source_hash,tickets=tickets)
        commits.append((key,scenario,frozen,c["comparison_sha256"]))
    if sum(t["stake_yen"] for _,_,f,_ in commits for t in f["frozen"]["tickets"])!=ranking["research_spent_yen"]:
        raise FrozenRankingRejected("budget_not_reconciled")
    # Materialize all temporary journals, read every one back, then publish
    # the entire immutable directory atomically, never an individual journal.
    with tempfile.TemporaryDirectory(prefix=".lab-p6-stage-",dir=target.parent) as tmp:
        stage=Path(tmp)
        manifest=[]
        for key,scenario,frozen,comparison_sha in commits:
            filename=f"race-{key[1]:02d}.jsonl"
            state=append_record(stage/filename,"FROZEN",frozen,expected_head="0"*64)
            replay=read_journal(stage/filename,expected_head=state["head"])
            if len(replay["entries"])!=1 or replay["result"]["status"]!="UNSETTLED":
                raise FrozenRankingRejected("pre_result_restart_replay_invalid")
            manifest.append({"race_date":key[0],"race":key[1],"scenario_id":scenario,
                "file":filename,"journal_head_sha256":state["head"],
                "frozen_prediction_sha256":frozen["frozen_sha256"],
                "p4_comparison_sha256":comparison_sha})
        body={"schema":"kyoto_p6_pre_result_ranked_lab.v1",
          "scope":"RESEARCH_FIXTURE_ONLY_UNAUTHENTICATED_ORIGINAL_SOURCE",
          "p5_ranking_sha256":ranking["ranking_sha256"],
          "commit_utc":commit_utc,"ticket_type":ranking["ticket_type"],
          "budget_ceiling_yen":ranking["daily_budget_ceiling_yen"],
          "research_spent_yen":ranking["research_spent_yen"],
          "unspent_yen":ranking["unspent_yen"],
          "journals":manifest,"result_information_in_freeze":False,
          "official_origin_authenticated":False,
          "real_paper_trade_authorized":False,
          "actual_purchase_authorized":False}
        receipt={**body,"receipt_sha256":digest(body)}
        (stage/"manifest.json").write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,
                         separators=(",",":"),allow_nan=False)+"\n",encoding="utf8")
        # os.rename rejects existing nonempty destination; no overwrite path
        # and no in-place modification of persistent existing ledgers.
        if target.exists() or target.is_symlink():
            raise FrozenRankingRejected("immutable_target_changed")
        os.rename(stage,target)
        return receipt
