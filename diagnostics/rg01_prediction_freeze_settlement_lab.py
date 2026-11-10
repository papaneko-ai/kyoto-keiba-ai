"""RG-01B: LAB-only prediction -> pre-cutoff freeze -> fixture settlement.

Composes existing P3 horse/frame distributions, P4 market EV, and P6
hash-chain journal. No real JRA HTTP, no actual wagers, no real-paper trades.
The freeze API NEVER accepts a result; the settlement API only accepts an
already persisted journal and a later outcome. Each phase re-reads its journal.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from diagnostics.p3_p6_research_no_bet import (
    quinella_from_strength, bracket_from_quinella, market_ev
)
from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture, LabRejected
from diagnostics.p6_fixture_durable_ledger import append_record, read_journal

class IntegratedLabRejected(ValueError):
    pass

def _when(s):
    try:
        if type(s) is not str: raise ValueError()
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
        if t.utcoffset()!=timezone.utc.utcoffset(None): raise ValueError()
        return t
    except (ValueError,TypeError,AttributeError):
        raise IntegratedLabRejected("UTC_timestamp_required")

def _sha(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,
                        separators=(",",":"),allow_nan=False).encode("utf8")).hexdigest()

def freeze_research_prediction(path, *, scenario_id, ticket_type, strengths,
                               frames, market, observed_utc, frozen_utc,
                               cutoff_utc, model_version="LAB-PL-NOT-CALIBRATED",
                               amount_yen=100):
    """Pre-result stage; requires an EXPLICIT lab marker and no outcome argument."""
    if not isinstance(path,(str,Path)):raise IntegratedLabRejected("journal_path_invalid")
    if ticket_type not in ("QUINELLA","BRACKET"):
        raise IntegratedLabRejected("ticket_type_invalid")
    if type(strengths) is not dict or type(frames) is not dict or type(market) is not dict:
        raise IntegratedLabRejected("invalid_lab_inputs")
    if type(scenario_id) is not str or not scenario_id.startswith("LAB-"):
        raise IntegratedLabRejected("lab_identity_required")
    if type(amount_yen) is not int or amount_yen<100 or amount_yen%100:
        raise IntegratedLabRejected("stake_invalid")
    if not _when(observed_utc) <= _when(frozen_utc) < _when(cutoff_utc):
        raise IntegratedLabRejected("post_cutoff_or_future_market")
    if set(frames)!=set(strengths):
        raise IntegratedLabRejected("frame_roster_mismatch")
    if any(type(n) is not int or type(f) is not int for n,f in frames.items()):
        raise IntegratedLabRejected("frame_roster_invalid")
    if not all(type(x) is tuple and len(x)==2 for x in market):
        raise IntegratedLabRejected("market_pair_schema_invalid")
    pairs=quinella_from_strength(strengths)
    if ticket_type=="BRACKET":
        pairs=bracket_from_quinella(pairs,frames)
    ev=market_ev(pairs,market,uncertainty_margin=0.05)
    # The lab may skip without writing if no strictly positive conservative EV.
    candidates=sorted((x for x in ev if x["lower_bound_net_per_1"]>0),
                      key=lambda x:(-x["lower_bound_net_per_1"],tuple(x["pair"])))
    if not candidates:
        return {"state":"LAB_NO_BET","journal_written":False,
                "prediction_ready":False,"actual_purchase":False}
    best=candidates[0]
    original={"provenance":"LAB_SYNTHETIC_ONLY","scenario_id":scenario_id,
              "ticket_type":ticket_type,"strengths":strengths,
              "frames":frames,"market":sorted((list(p),str(v)) for p,v in market.items()),
              "observed_utc":observed_utc}
    frozen=freeze_fixture(scenario_id=scenario_id,ticket_type=ticket_type,
          cutoff_utc=cutoff_utc,frozen_utc=frozen_utc,
          model_version=model_version,source_sha256=_sha(original),
          tickets=[{"pair":list(best["pair"]),"stake_yen":amount_yen,
                    "probability":best["theoretical_probability"],
                    "odds":float(best["decimal_odds"])}])
    state=append_record(Path(path),"FROZEN",frozen,expected_head="0"*64)
    return {"state":"LAB_FROZEN_UNSETTLED",
            "journal_head_sha256":state["head"],
            "frozen_prediction_sha256":frozen["frozen_sha256"],
            "chosen_pair":list(best["pair"]),"ticket_type":ticket_type,
            "stake_yen":amount_yen,"journal_written":True,
            "lab_source_sha256":_sha(original),
            "prediction_ready":False,"actual_purchase":False}

def settle_research_result(path, *, expected_head, version, payout_per_100,
                           refunded_pairs, event_utc, state="PAYOUT_FINAL"):
    """Post-result stage; never changes prediction bytes. Requires head anchor."""
    if type(expected_head) is not str or len(expected_head)!=64:
        raise IntegratedLabRejected("external_journal_head_required")
    journal=read_journal(path,expected_head=expected_head)
    if not journal["entries"] or journal["entries"][0]["payload"]["type"]!="FROZEN":
        raise IntegratedLabRejected("freeze_must_precede_result")
    body=journal["entries"][0]["payload"]["record"]["frozen"]
    if _when(event_utc)<=_when(body["cutoff_utc"]):
        raise IntegratedLabRejected("result_before_race_cutoff")
    if type(version) is not int or version<1 or state not in ("PAYOUT_FINAL","RESULT_PRELIMINARY"):
        raise IntegratedLabRejected("event_version_or_state_invalid")
    if type(payout_per_100) is not dict or type(refunded_pairs) is not list:
        raise IntegratedLabRejected("fixture_result_invalid")
    event={"scenario_id":body["scenario_id"],"source_kind":"FIXTURE",
           "version":version,"state":state,
           "payout_per_100":payout_per_100,"refunded_pairs":refunded_pairs}
    updated=append_record(path,"RESULT_EVENT",event,expected_head=expected_head)
    # An independent restart-read is integral to acceptance.
    replayed=read_journal(path,expected_head=updated["head"])
    if replayed["result"]!=updated["result"]:
        raise IntegratedLabRejected("restart_replay_divergence")
    return {"state":replayed["result"]["status"],
            "journal_head_sha256":replayed["head"],
            "result":replayed["result"],
            "fixture_only":True,"official_results_verified":False,
            "real_bet_authorized":False}

def verify_research_restart(path, *, expected_head):
    checked=read_journal(path,expected_head=expected_head)
    return {"head_sha256":checked["head"],"entries":len(checked["entries"]),
            "outcome":checked["result"],"fixture_only":True}
