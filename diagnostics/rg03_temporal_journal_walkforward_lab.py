"""RG-03B: strict chronological LAB walk-forward from P6 frozen journals.

Uses prior precommitted research inputs and journaled fixture settlement events
to construct P3 walk-forward scoring. Prevents using a later result to fit an
earlier fold; never interprets research labels as authentic official results.
No network, live prediction or actual orders.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from diagnostics.p6_fixture_durable_ledger import read_journal
from diagnostics.p3_p6_research_no_bet import quinella_from_strength
from diagnostics.p3_research_calibration import walk_forward_overfit_audit
from diagnostics.rg01_prediction_freeze_settlement_lab import _sha

class TemporalIntegrationRejected(ValueError):
    pass

def _utc(raw):
    try:
        if type(raw) is not str:
            raise ValueError()
        t=datetime.fromisoformat(raw.replace("Z","+00:00"))
        if t.utcoffset()!=timezone.utc.utcoffset(None):
            raise ValueError()
        return t
    except (ValueError, TypeError, AttributeError):
        raise TemporalIntegrationRejected("UTC_required")

def audit_frozen_walkforward(records, *, min_train=3):
    """Strictly ordered, externally head-anchored, settled LAB scenario list.

    Each record requires a snapshot of the pre-result strengths, frames,
    exact market and observation time. Those bytes are bound to the journal
    freeze SHA written before the recorded outcome. The supplied result time
    is a LAB assertion, not an independent timestamp.
    """
    if type(records) is not list or len(records)<5 or len(records)>100:
        raise TemporalIntegrationRejected("at_least_five_lab_journals_required")
    if type(min_train) is not int or min_train<3 or min_train>=len(records):
        raise TemporalIntegrationRejected("invalid_train_window")
    parsed=[]
    prior_cutoff=None
    prior_result=None
    seen_ids=set()
    seen_paths=set()
    for index, row in enumerate(records):
        required={"path","expected_head","race_id","strengths","frames","market",
                  "observed_utc","result_recorded_utc"}
        if type(row) is not dict or set(row)!=required:
            raise TemporalIntegrationRejected("input_schema_invalid")
        path=Path(row["path"])
        if path.is_symlink() or not path.is_file() or str(path.resolve()) in seen_paths:
            raise TemporalIntegrationRejected("journal_missing_or_duplicate")
        seen_paths.add(str(path.resolve()))
        if type(row["expected_head"]) is not str or len(row["expected_head"])!=64:
            raise TemporalIntegrationRejected("external_head_required")
        journal=read_journal(path,expected_head=row["expected_head"])
        entries=journal["entries"]
        if len(entries)!=2 or [e["payload"]["type"] for e in entries]!=["FROZEN","RESULT_EVENT"]:
            raise TemporalIntegrationRejected("final_fixture_journal_required")
        frozen=entries[0]["payload"]["record"]
        body=frozen["frozen"]
        event=entries[1]["payload"]["record"]
        if (journal["result"]["status"]!="FINAL_FIXTURE_ONLY" or
                body["ticket_type"]!="QUINELLA" or
                event.get("state")!="PAYOUT_FINAL" or event.get("source_kind")!="FIXTURE"):
            raise TemporalIntegrationRejected("quinella_final_fixture_required")
        race_id=row["race_id"]
        if type(race_id) is not str or not race_id.startswith("LAB-") or race_id in seen_ids:
            raise TemporalIntegrationRejected("duplicate_or_nonlab_race")
        seen_ids.add(race_id)
        if race_id != body["scenario_id"]:
            raise TemporalIntegrationRejected("journal_race_mismatch")
        observed=_utc(row["observed_utc"])
        freeze_time=_utc(body["frozen_utc"])
        cutoff=_utc(body["cutoff_utc"])
        result_time=_utc(row["result_recorded_utc"])
        if not observed<=freeze_time<cutoff<result_time:
            raise TemporalIntegrationRejected("future_information_or_cutoff_violation")
        if prior_cutoff is not None and not prior_cutoff<cutoff:
            raise TemporalIntegrationRejected("races_out_of_order")
        # Much stronger than train/holdout cutoff only: every previous
        # outcome must have become available before the next freeze.
        if prior_result is not None and not prior_result<freeze_time:
            raise TemporalIntegrationRejected("previous_outcome_not_available_at_freeze")
        prior_cutoff,prior_result=cutoff,result_time
        if (type(row["strengths"]) is not dict or type(row["frames"]) is not dict or
                type(row["market"]) is not dict or set(row["strengths"])!=set(row["frames"])):
            raise TemporalIntegrationRejected("invalid_or_mismatched_roster")
        if any(type(n) is not int or type(f) is not int for n,f in row["frames"].items()):
            raise TemporalIntegrationRejected("roster_number_invalid")
        pairs=quinella_from_strength(row["strengths"])
        if type(row["market"]) is not dict or set(row["market"])!=set(pairs):
            raise TemporalIntegrationRejected("incomplete_original_market")
        snapshot={"provenance":"LAB_SYNTHETIC_ONLY","scenario_id":race_id,
                  "ticket_type":"QUINELLA","strengths":row["strengths"],
                  "frames":row["frames"],
                  "market":sorted((list(p),str(v)) for p,v in row["market"].items()),
                  "observed_utc":row["observed_utc"]}
        if _sha(snapshot)!=body["source_sha256"]:
            raise TemporalIntegrationRejected("precommitted_input_mismatch")
        paid=event.get("payout_per_100")
        if (type(paid) is not dict or len(paid)!=1 or
                event.get("refunded_pairs")!=[] or
                any(type(v) is not int or v<=0 for v in paid.values())):
            raise TemporalIntegrationRejected("unambiguous_final_winner_required")
        winner_string=next(iter(paid))
        if (type(winner_string) is not str or
                winner_string.count("-")!=1):
            raise TemporalIntegrationRejected("final_winner_format_invalid")
        try:
            winner=tuple(map(int,winner_string.split("-")))
        except (TypeError,ValueError):
            raise TemporalIntegrationRejected("final_winner_format_invalid")
        if winner not in pairs or winner_string!=f"{winner[0]}-{winner[1]}":
            raise TemporalIntegrationRejected("winning_pair_not_in_original_roster")
        parsed.append({
            "race_id":race_id,
            "prediction_cutoff_utc":body["frozen_utc"],
            "pairs":[{"pair":list(p),"probability":prob} for p,prob in sorted(pairs.items())],
            "winning_pair":list(winner),
            "pre_result_frozen":True
        })
    scored=walk_forward_overfit_audit(parsed,min_train=min_train)
    folds=scored["folds"]
    if len(folds)!=len(records)-min_train:
        raise TemporalIntegrationRejected("holdout_fold_missing")
    return {
        "schema":"kyoto_rg03_temporal_journal_lab.v1",
        "scope":"LAB_ONLY_P6_FROZEN_JOURNALS",
        "scored":scored,
        "journal_heads":[x["expected_head"] for x in records],
        "freeze_order":[x["race_id"] for x in records],
        "holdout_races":len(folds),
        "sequential_result_availability_enforced":True,
        "leak_free_to_declared_lab_times":True,
        "external_timestamp_proven":False,
        "official_result_authenticated":False,
        "calibrated_live_model":False,
        "operational_prediction_ready":False,
        "actual_bet_authorized":False
    }
