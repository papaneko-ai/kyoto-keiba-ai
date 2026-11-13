"""R16 fixed synthetic P2-P8 lifecycle, two isolated filesystem restores.

No real JRA source authentication, production deployment, network, or wagering.
A precommitted LAB packet contains *separated* before/after-race fields;
no postrace field is passed to a forecast. Synthetic calculations are not
proof of model generalization or true market EV.
"""
from __future__ import annotations
import copy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from diagnostics.p2_prerace_feature_contract import freeze_feature_envelope
from diagnostics.p2_p3_p5_offline_feature_bridge import feature_forecast_snapshot, FEATURE_SCHEMA
from diagnostics.p3_offline_model_tournament import predict,_hash,_utc
from diagnostics.p3_p5_p6_synthetic_pipeline_lab import freeze_lab_market_scenario
from diagnostics.p6_fixture_durable_ledger import append_record,read_journal
from diagnostics.p6_fixture_temporal_aggregate import aggregate_fixture_journals
from diagnostics.p7_approved_evo_capability_screen import falsify_research_candidates, EXPECTED
from diagnostics.p7_guarded_research_rollback import monitor_research_decisions
from diagnostics.p8_r15_safe_mobile_viewmodel import build_mobile_state

class R16Rejected(ValueError):pass

def _sha(obj):return _hash(obj)

def _checked_packet(packet):
    fields={"schema","pre_race","post_race","research_evolution","mobile","packet_sha256"}
    if type(packet) is not dict or set(packet)!=fields or packet.get("schema")!="kyoto_r16_fixed_lab_packet.v1":
        raise R16Rejected("packet_schema_invalid")
    signed={k:v for k,v in packet.items() if k!="packet_sha256"}
    if packet["packet_sha256"]!=_sha(signed):raise R16Rejected("packet_sha256_mismatch")
    pre=packet["pre_race"]
    if type(pre) is not dict or set(pre)!={"features","fixed_plan","market","observed_utc","frozen_utc","budget_yen","model_id","ticket_type"}:
        raise R16Rejected("pre_race_contract_invalid")
    post=packet["post_race"]
    if type(post) is not dict or set(post)!={"result_utc","payout_per_100","corrected_payout_per_100"}:
        raise R16Rejected("postrace_contract_invalid")
    if type(packet["mobile"]) is not dict or set(packet["mobile"])!={"meeting_date","market"}:
        raise R16Rejected("mobile_contract_invalid")
    evo=packet["research_evolution"]
    if type(evo) is not dict or set(evo)!={"capabilities","epochs"}:
        raise R16Rejected("evolution_contract_invalid")
    return pre,post,evo

def _one_replay(packet,root):
    pre,post,evo=_checked_packet(packet)
    frozen_features=freeze_feature_envelope(copy.deepcopy(pre["features"]))
    if frozen_features["p3_snapshot"] is None:
        raise R16Rejected("missing_features_fail_closed")
    plan=copy.deepcopy(pre["fixed_plan"])
    if plan.get("feature_schema")!=list(FEATURE_SCHEMA) or plan.get("research_only") is not True:
        raise R16Rejected("feature_plan_scope_invalid")
    snapshot=feature_forecast_snapshot(plan,frozen_features["p3_snapshot"])
    forecast=predict(snapshot,pre["model_id"])
    m=copy.deepcopy(pre["market"])
    if m["race_id"]!=snapshot["race_id"] or m["market_type"]!=pre["ticket_type"]:
        raise R16Rejected("market_model_identity_mismatch")
    pipe=freeze_lab_market_scenario(snapshot,model_id=pre["model_id"],synthetic_market=m,
        observed_utc=pre["observed_utc"],frozen_utc=pre["frozen_utc"],
        daily_budget_yen=pre["budget_yen"],ticket_type=pre["ticket_type"])
    if pipe["frozen"] is None:raise R16Rejected("unexpected_no_position")
    frozen=pipe["frozen"]
    if frozen["frozen"]["source_sha256"] is None or pipe["receipt"]["forecast_sha256"]!=forecast["forecast_sha256"]:
        raise R16Rejected("prediction_freeze_linkage_failed")
    if _utc(post["result_utc"])<=_utc(snapshot["race_start_utc"]):
        raise R16Rejected("result_not_after_race")
    journal=Path(root)/"paper.jsonl"
    before=append_record(journal,"FROZEN",frozen,expected_head="0"*64)
    initial_head=before["head"]
    if before["result"]["status"]!="UNSETTLED":raise R16Rejected("freeze_must_be_unsettled")
    scenario=frozen["frozen"]["scenario_id"]
    def event(version,payout):return {"scenario_id":scenario,"source_kind":"FIXTURE",
        "version":version,"state":"PAYOUT_FINAL","payout_per_100":payout,"refunded_pairs":[]}
    first=append_record(journal,"RESULT_EVENT",event(1,post["payout_per_100"]),expected_head=initial_head)
    final=append_record(journal,"RESULT_EVENT",event(2,post["corrected_payout_per_100"]),expected_head=first["head"])
    reopened=read_journal(journal,expected_head=final["head"])
    if len(reopened["entries"])!=3 or reopened["result"]["event_version"]!=2:
        raise R16Rejected("correction_not_replayed")
    summary=aggregate_fixture_journals([{"path":str(journal),"expected_head":final["head"]}])
    if summary["profit_yen"]!=reopened["result"]["profit_yen"]:
        raise R16Rejected("ledger_aggregate_mismatch")
    restored=Path(root)/"isolated_restore";restored.mkdir()
    restored_path=restored/"paper.jsonl"
    restored_path.write_bytes(journal.read_bytes())
    if sha256(journal.read_bytes()).digest()!=sha256(restored_path.read_bytes()).digest():
        raise R16Rejected("restore_bytes_differ")
    if read_journal(restored_path,expected_head=final["head"])["result"]!=reopened["result"]:
        raise R16Rejected("restore_replay_divergence")
    capabilities=falsify_research_candidates(copy.deepcopy(evo["capabilities"]))
    if set(x["id"] for x in capabilities["results"])!=set(EXPECTED):
        raise R16Rejected("evolution_eight_missing")
    monitor=monitor_research_decisions(copy.deepcopy(evo["epochs"]))
    if not any(x["decision"]=="ROLLBACK_TO_RETAINED_CHAMPION" for x in monitor["epochs"]):
        raise R16Rejected("rollback_not_demonstrated")
    if monitor["auto_deploy"] or any(x["retained_champion"]!="LAB-CHAMPION" for x in monitor["epochs"]):
        raise R16Rejected("unauthorized_model_promotion")
    mobile=build_mobile_state(meeting_date=packet["mobile"]["meeting_date"],
        market=packet["mobile"]["market"],budget_yen=pre["budget_yen"])
    if mobile["simulation_write_enabled"] or mobile["cumulative_profit_yen"] is not None:
        raise R16Rejected("unverified_preview_claim")
    body={"schema":"kyoto_r16_p2_p8_replayed_lab.v1","packet_sha256":packet["packet_sha256"],
        "P2_feature_receipt_sha256":frozen_features["receipt"]["receipt_sha256"],
        "P3_forecast_sha256":forecast["forecast_sha256"],
        "P4_synthetic_market_sha256":pipe["receipt"]["synthetic_market_sha256"],
        "P5_budget_spent_yen":pipe["receipt"]["spent_yen"],
        "P6_frozen_sha256":frozen["frozen_sha256"],
        "P6_final_journal_head_sha256":final["head"],
        "P6_profit_fixture_only_yen":reopened["result"]["profit_yen"],
        "P6_aggregate_sha256":_sha(summary),
        "P7_evo_eight_screen_sha256":_sha(capabilities),
        "P7_monitor_chain_sha256":monitor["decision_chain_head"],
        "P8_mobile_safe_sha256":mobile["receipt_sha256"],
        "restart_verified":True,"isolated_restore_verified":True,
        "live_source_authenticated":False,"production_model_promoted":False,
        "real_paper_trade_written":False,"real_bet_authorized":False,"network_requests":0}
    return {**body,"receipt_sha256":_sha(body)}

def run_r16(packet):
    _checked_packet(packet)
    with TemporaryDirectory() as a:
        first=_one_replay(copy.deepcopy(packet),a)
    with TemporaryDirectory() as b:
        second=_one_replay(copy.deepcopy(packet),b)
    if first!=second:raise R16Rejected("two_isolated_replays_mismatch")
    return {**first,"independent_replay_count":2}
