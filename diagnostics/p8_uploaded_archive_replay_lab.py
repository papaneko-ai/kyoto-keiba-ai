"""P8-03 opt-in offline atomic P1 archive -> P4/P5/P6 freeze/settle replay.

User-provided bytes and *synthetic, LAB-only* model. Never downloads data,
records real paper trades, authenticates JRA, touches production app/Turso, or
sends orders. Result bytes can be omitted to inspect PRE-RESULT frozen state.
"""
from __future__ import annotations
import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from diagnostics.p1_atomic_dual_market_handoff import verify_prerace_handoff_archive
from diagnostics.p4_source_bound_model_ev_research import compare_source_market_to_frozen_model
from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races
from diagnostics.p6_source_bound_ranked_freeze_lab import freeze_ranked_research_day
from diagnostics.p6_final_html_settlement_lab import settle_ranked_lab_results

class IntegrationReplayRejected(ValueError): pass

def replay_user_supplied_lab_archive(*, archive_bytes, archive_sha256,
        observed_utc, channel, frozen_model,
        commit_utc, ticket_type="QUINELLA", daily_budget_yen=1000,
        final_result_bytes=None, final_result_utc=None):
    if type(archive_bytes) is not bytes or not 0<len(archive_bytes)<13_000_000:
        raise IntegrationReplayRejected("upload_archive_invalid")
    if type(archive_sha256) is not str or hashlib.sha256(archive_bytes).hexdigest()!=archive_sha256:
        raise IntegrationReplayRejected("independent_archive_sha_mismatch")
    verify_prerace_handoff_archive(archive_bytes,expected_sha256=archive_sha256,
                                   observed_utc=observed_utc,channel=channel)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        # Archive members are checked by the P1 independent validator first.
        bundle=z.read("source_bundle.zip")
        snapshot=json.loads(z.read("snapshot.json"))
    params={"bundle":bundle,"snapshot":snapshot,"observed_utc":observed_utc,
            "channel":channel,"frozen_model":frozen_model}
    p4=compare_source_market_to_frozen_model(**params)
    p5=rank_lab_research_races([p4],daily_budget_yen=daily_budget_yen,
                               ticket_type=ticket_type)
    if (final_result_bytes is None)!=(final_result_utc is None):
        raise IntegrationReplayRejected("result_bytes_and_time_must_be_together")
    if final_result_bytes is not None and type(final_result_bytes) is not bytes:
        raise IntegrationReplayRejected("result_bytes_required")
    with tempfile.TemporaryDirectory(prefix="kyoto-p8-offline-") as temp:
        root=Path(temp)
        p6=freeze_ranked_research_day(day_inputs=[params],ranking=p5,
                    destination=root/"frozen",commit_utc=commit_utc)
        for row in p6["journals"]:
            fp=root/"frozen"/row["file"]
            if not fp.is_file():
                raise IntegrationReplayRejected("freeze_journal_not_materialized")
        finalized=None
        if final_result_bytes is not None:
            if not p6["journals"]:
                raise IntegrationReplayRejected("no_frozen_bets_to_settle")
            from hashlib import sha256
            frozen_manifest_sha=sha256((root/"frozen"/"manifest.json").read_bytes()).hexdigest()
            result=settle_ranked_lab_results(
                prior_directory=root/"frozen",destination=root/"settled",
                result_captures={str(snapshot["race"]):{
                    "raw":final_result_bytes,"captured_utc":final_result_utc,
                    "declared_scope":"LAB_RESULT_FIXTURE_ONLY"}},
                expected_prior_manifest_sha256=frozen_manifest_sha)
            finalized={
                "p6_settlement_receipt_sha256":result["receipt_sha256"],
                "settled_fixture_payout_yen":result["settled_fixture_payout_yen"],
                "settled_fixture_profit_yen":result["settled_fixture_profit_yen"],
                "settled_race_count":len(result["journals"])}
        output={"schema":"kyoto_p8_uploaded_archive_lab_replay.v1",
            "scope":"USER_SUPPLIED_CONTENT_ONLY_NOT_INDEPENDENT_JRA_AUTHENTICATION",
            "source_archive_sha256":archive_sha256,
            "race_date":snapshot["meeting_date"],"race":snapshot["race"],
            "ticket_type":ticket_type,"source_p4_sha256":p4["comparison_sha256"],
            "source_p5_sha256":p5["ranking_sha256"],
            "source_p6_sha256":p6["receipt_sha256"],
            "selected_race_count":len(p5["selected"]),
            "selected_ticket_count":sum(len(r["tickets"]) for r in p5["selected"]),
            "research_stake_yen":p5["research_spent_yen"],
            "unused_budget_yen":p5["unspent_yen"],
            "research_result":finalized,
            "official_source_authenticated":False,
            "official_payout_authenticated":False,
            "live_model_evaluated":False,
            "real_paper_trade_verified":False,
            "actual_purchase_authorized":False,
            "network_requests":0}
        digest=hashlib.sha256(json.dumps(output,sort_keys=True,
               ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        return {**output,"replay_sha256":digest}
