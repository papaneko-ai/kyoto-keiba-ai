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
from diagnostics.p5_bounded_risk_capital_lab import research_capital_control,CapitalRiskRejected
from diagnostics.kyoto_f12_ticket_budget_planner import plan_f12,F12Rejected
from diagnostics.p3_p6_research_no_bet import quinella_from_strength,bracket_from_quinella
from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture
from diagnostics.p6_fixture_durable_ledger import append_record,read_journal

class FrozenRankingRejected(ValueError):pass

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
                separators=(",",":"),allow_nan=False).encode()).hexdigest()

def freeze_ranked_research_day(*,day_inputs, ranking, destination,
                               commit_utc, stake_per_ticket_yen=100,
                               capital_receipt=None,capital_policy=None,
                               f12_receipt=None,f12_inputs=None):
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
    if (f12_receipt is None)!=(f12_inputs is None):
        raise FrozenRankingRejected("f12_plan_and_inputs_both_required")
    if f12_receipt is not None and (capital_receipt is not None or capital_policy is not None):
        raise FrozenRankingRejected("f12_and_capital_modes_mutually_exclusive")
    if (capital_receipt is None)!=(capital_policy is None):
        raise FrozenRankingRejected("capital_receipt_and_policy_both_required")
    selected_rows=ranking["selected"]
    chosen_spend=ranking["research_spent_yen"]
    capital_sha=None
    if capital_receipt is not None:
        # P5-03 must be independently recomputed from the exact P5 ranking,
        # original-bound P4 receipts and *explicit* allocation policy. Neither
        # a supplied claim nor a self-hashed capital receipt is sufficient.
        allowed={"exposure_fraction","max_race_fraction","max_pair_fraction",
                 "max_pair_stake_yen","downside_guard"}
        if (type(capital_policy) is not dict or set(capital_policy)!=allowed
            or type(capital_receipt) is not dict):
            raise FrozenRankingRejected("capital_policy_schema_invalid")
        try:
            recomputed=research_capital_control(ranking,**capital_policy)
        except (CapitalRiskRejected,TypeError,ValueError,KeyError) as exc:
            raise FrozenRankingRejected("capital_recomputation_failed") from exc
        if capital_receipt!=recomputed:
            raise FrozenRankingRejected("capital_recomputed_receipt_mismatch")
        candidate_rows={row["race"]:row for row in ranking["selected"]}
        selected_rows=[]
        for row in recomputed["selected"]:
            parent=candidate_rows.get(row["race"])
            if parent is None or row["rank"]!=parent["rank"] or (
                    row["source_p4_sha256"]!=parent["p4_comparison_sha256"]):
                raise FrozenRankingRejected("capital_source_race_conflict")
            allowed_pairs={tuple(t["pair"]) for t in parent["tickets"]}
            tickets=[]
            for t in row["tickets"]:
                amount=t["heuristic_stake_yen"]
                if tuple(t["pair"]) not in allowed_pairs:
                    raise FrozenRankingRejected("capital_pair_not_ranked")
                if amount>0:
                    tickets.append({"pair":t["pair"],"stake_yen":amount})
            if tickets:
                selected_rows.append({**parent,"tickets":tickets,
                                      "research_stake_yen":sum(t["stake_yen"] for t in tickets)})
        chosen_spend=recomputed["research_spent_yen"]
        if sum(t["stake_yen"] for row in selected_rows for t in row["tickets"])!=chosen_spend:
            raise FrozenRankingRejected("capital_budget_reconciliation_failed")
        capital_sha=recomputed["capital_sha256"]
    f12_sha=None
    if f12_receipt is not None:
        if type(f12_inputs) is not dict or type(f12_receipt) is not dict:
            raise FrozenRankingRejected("f12_input_schema_invalid")
        expected_fields={"day_budget_yen","exposure_target_yen","market","mode",
                         "candidates","selected_races","manual_race_amounts","concentrate"}
        if set(f12_inputs)!=expected_fields:
            raise FrozenRankingRejected("f12_complete_inputs_required")
        # The F12 standalone allocator is independent of odds/forecasts.
        # It can only be used here for already-ranked, source-bound pairs.
        allowed_ranked={row["race"]:row for row in ranking["selected"]}
        if (f12_inputs["market"]!=ranking["ticket_type"]
            or f12_inputs["day_budget_yen"]!=ranking["daily_budget_ceiling_yen"]
            or type(f12_inputs["candidates"]) is not list
            or len(f12_inputs["candidates"])!=len(allowed_ranked)):
            raise FrozenRankingRejected("f12_ranking_identity_conflict")
        seen_candidates=set()
        for candidate in f12_inputs["candidates"]:
            if type(candidate) is not dict:
                raise FrozenRankingRejected("f12_candidate_invalid")
            race=candidate.get("race")
            ranked=allowed_ranked.get(race)
            if (ranked is None or race in seen_candidates
                or candidate.get("priority")!=ranked["rank"]
                or candidate.get("ticket_type")!=ranking["ticket_type"]
                or candidate.get("eligible") is not True
                or type(candidate.get("tickets")) is not list
                or not candidate["tickets"]):
                raise FrozenRankingRejected("f12_candidate_not_source_ranked")
            permitted={tuple(t["pair"]) for t in ranked["tickets"]}
            offered=[t.get("pair") for t in candidate["tickets"] if type(t) is dict]
            if (len(offered)!=len(candidate["tickets"])
                or any(type(pair) is not list or tuple(pair) not in permitted
                       for pair in offered)):
                raise FrozenRankingRejected("f12_ticket_not_source_ranked")
            seen_candidates.add(race)
        if seen_candidates!=set(allowed_ranked):
            raise FrozenRankingRejected("f12_missing_ranked_candidate")
        try:
            expected_f12=plan_f12(**f12_inputs)
        except (F12Rejected,ValueError,TypeError,KeyError) as exc:
            raise FrozenRankingRejected("f12_plan_validation_failed") from exc
        if expected_f12!=f12_receipt:
            raise FrozenRankingRejected("f12_recomputed_receipt_mismatch")
        if (f12_receipt["scope"]!="OFFLINE_MANUAL_OR_AUTO_PLANNING_NOT_A_BET"
            or f12_receipt["real_source_verified"] is not False
            or f12_receipt["model_calibrated"] is not False
            or f12_receipt["real_purchase_authorized"] is not False):
            raise FrozenRankingRejected("f12_false_live_claim")
        selected_rows=[]
        for chosen in f12_receipt["selected"]:
            ranked=allowed_ranked.get(chosen["race"])
            if ranked is None or chosen["priority"]!=ranked["rank"]:
                raise FrozenRankingRejected("f12_race_selection_conflict")
            permitted={tuple(t["pair"]) for t in ranked["tickets"]}
            tickets=[{"pair":t["pair"],"stake_yen":t["stake_yen"]}
                     for t in chosen["tickets"] if t["stake_yen"]>0]
            if any(tuple(t["pair"]) not in permitted for t in tickets):
                raise FrozenRankingRejected("f12_frozen_pair_not_ranked")
            if tickets:
                selected_rows.append({**ranked,"tickets":tickets,
                                      "research_stake_yen":sum(t["stake_yen"] for t in tickets)})
        chosen_spend=f12_receipt["spent_yen"]
        if sum(t["stake_yen"] for row in selected_rows for t in row["tickets"])!=chosen_spend:
            raise FrozenRankingRejected("f12_stake_reconciliation_failed")
        f12_sha=f12_receipt["plan_sha256"]
    commits=[]
    for selected in selected_rows:
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
        source_basis={"p4":c["comparison_sha256"],"p5":ranking["ranking_sha256"],
                      "original":c["source_bundle_sha256"],"model":c["model_sha256"]}
        if capital_sha is not None:
            source_basis["capital_receipt_sha256"]=capital_sha
            source_basis["capital_policy_sha256"]=digest(capital_policy)
        if f12_sha is not None:
            source_basis["f12_receipt_sha256"]=f12_sha
            source_basis["f12_inputs_sha256"]=digest(f12_inputs)
        source_hash=digest(source_basis)
        frozen=freeze_fixture(scenario_id=scenario,ticket_type=ranking["ticket_type"],
              cutoff_utc=snap["prediction_cutoff_utc"],frozen_utc=commit_utc,
              model_version=m["model_version"],source_sha256=source_hash,tickets=tickets)
        commits.append((key,scenario,frozen,c["comparison_sha256"]))
    if sum(t["stake_yen"] for _,_,f,_ in commits for t in f["frozen"]["tickets"])!=chosen_spend:
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
          "research_spent_yen":chosen_spend,
          "unspent_yen":ranking["daily_budget_ceiling_yen"]-chosen_spend,
          "journals":manifest,"result_information_in_freeze":False,
          "official_origin_authenticated":False,
          "real_paper_trade_authorized":False,
          "actual_purchase_authorized":False}
        if capital_sha is not None:
            body["allocation_source"]="P5_RECOMPUTED_BOUNDED_RISK_CAPITAL"
            body["capital_receipt_sha256"]=capital_sha
            body["capital_policy_sha256"]=digest(capital_policy)
            body["not_real_risk_calibration"]=True
        if f12_sha is not None:
            body["allocation_source"]="F12_RECOMPUTED_USER_SELECTION"
            body["f12_receipt_sha256"]=f12_sha
            body["f12_inputs_sha256"]=digest(f12_inputs)
            body["f12_mode"]=f12_receipt["mode"]
            body["user_selected_races"]=f12_receipt["user_selected_races"]
            body["f12_exposure_target_yen"]=f12_receipt["exposure_target_yen"]
            body["not_real_risk_calibration"]=True
        receipt={**body,"receipt_sha256":digest(body)}
        (stage/"manifest.json").write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,
                         separators=(",",":"),allow_nan=False)+"\n",encoding="utf8")
        # os.rename rejects existing nonempty destination; no overwrite path
        # and no in-place modification of persistent existing ledgers.
        if target.exists() or target.is_symlink():
            raise FrozenRankingRejected("immutable_target_changed")
        os.rename(stage,target)
        return receipt
