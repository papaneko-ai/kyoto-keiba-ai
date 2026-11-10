"""RG-02B: end-to-end research-market integration using EXISTING P3/P4/P5.

LAB-only PL/Harville strengths -> full horse/frame distributions -> exact
market coverage -> conservative EV -> tickets -> bounded research budget.

Interfaces deliberately carry provenance, observation and cutoff placeholders
for a future independently authenticated P1 source adapter. No actual odds,
official provenance, calibrated model, purchase or LIVE deployment is implied.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from diagnostics.p3_p6_research_no_bet import (
    quinella_from_strength, bracket_from_quinella,
    market_ev, allocate_research_budget, ResearchRejected
)

class IntegratedMarketRejected(ValueError):
    pass

def _utc(value):
    if type(value) is not str:
        raise IntegratedMarketRejected("UTC_timestamp_required")
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
        if t.utcoffset()!=timezone.utc.utcoffset(None):
            raise ValueError("UTC required")
        return t
    except (ValueError,TypeError,AttributeError) as exc:
        raise IntegratedMarketRejected("UTC_timestamp_required") from exc

def _hash(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,
           separators=(",",":"),allow_nan=False).encode("utf8")).hexdigest()

def integrate_research_market(races, *, budget_yen, per_ticket_yen=100,
                              uncertainty_margin=0.05, max_tickets=2):
    """One atomic, read-only research computation for both ticket markets.

    Every race contains synthetic full-coverage market quotes in JSON-friendly
    sorted "a-b" keys, not authenticated live odds. Pair gaps are rejected.
    """
    if type(races) is not list or not 1 <= len(races) <= 12:
        raise IntegratedMarketRejected("one_to_twelve_lab_races_required")
    if type(budget_yen) is not int or budget_yen < 0 or budget_yen % 100:
        raise IntegratedMarketRejected("invalid_budget")
    if type(per_ticket_yen) is not int or per_ticket_yen < 100 or per_ticket_yen%100:
        raise IntegratedMarketRejected("invalid_ticket_size")
    if type(max_tickets) is not int or not 1 <= max_tickets <= 3:
        raise IntegratedMarketRejected("invalid_ticket_cap")
    if type(uncertainty_margin) not in (int,float) or not 0 <= uncertainty_margin < 1:
        raise IntegratedMarketRejected("invalid_uncertainty")
    candidates=[]
    market_summaries=[]
    seen=set()
    for race in races:
        if type(race) is not dict or set(race)!={
            "date","race","venue","provenance","strengths","frames","odds",
            "market_observed_utc","scheduled_start_utc"
        }:
            raise IntegratedMarketRejected("race_schema_invalid")
        key=(race["date"],race["venue"],race["race"])
        if key in seen or type(race["race"]) is not int or not 1 <= race["race"] <= 12:
            raise IntegratedMarketRejected("duplicate_or_invalid_race")
        seen.add(key)
        if type(race["date"]) is not str or len(race["date"])!=10 or race["venue"]!="京都":
            raise IntegratedMarketRejected("unsupported_date_or_venue")
        if race["provenance"]!="LAB_SYNTHETIC_ONLY":
            raise IntegratedMarketRejected("unauthenticated_live_market_prohibited")
        observed=_utc(race["market_observed_utc"])
        cutoff=_utc(race["scheduled_start_utc"])
        if not observed < cutoff or observed.date().isoformat()!=race["date"]:
            raise IntegratedMarketRejected("market_not_prerace_or_wrong_day")
        if type(race["strengths"]) is not dict or type(race["frames"]) is not dict or type(race["odds"]) is not dict:
            raise IntegratedMarketRejected("invalid_market_input")
        def _parse_int_map(raw):
            result={}
            for k,v in raw.items():
                if type(k) is not str or not k.isdecimal() or k!=str(int(k)):
                    raise IntegratedMarketRejected("invalid_horse_number_key")
                result[int(k)]=v
            return result
        strengths=_parse_int_map(race["strengths"])
        frames=_parse_int_map(race["frames"])
        if set(frames)!=set(strengths):
            raise IntegratedMarketRejected("frame_roster_mismatch")
        horse_probs=quinella_from_strength(strengths)
        frame_probs=bracket_from_quinella(horse_probs,frames)
        for ticket_type,probs,odds_label in (
            ("QUINELLA",horse_probs,"quinella"),
            ("BRACKET",frame_probs,"bracket")
        ):
            raw_market=race["odds"].get(odds_label)
            if type(raw_market) is not dict:
                raise IntegratedMarketRejected("missing_market_"+odds_label)
            expected={f"{a}-{b}":(a,b) for a,b in probs}
            if set(raw_market)!=set(expected):
                raise IntegratedMarketRejected("market_coverage_mismatch_"+odds_label)
            market={pair:raw_market[label] for label,pair in expected.items()}
            ev=market_ev(probs,market,uncertainty_margin=uncertainty_margin)
            valid=sorted((x for x in ev if x["lower_bound_net_per_1"]>0),
                         key=lambda x:(-x["lower_bound_net_per_1"],tuple(x["pair"])))
            tickets=[{"pair":list(x["pair"]),"amount_yen":per_ticket_yen,
                      "expected_net_per_1":x["expected_net_per_1"],
                      "lower_bound_net_per_1":x["lower_bound_net_per_1"]}
                     for x in valid[:max_tickets]]
            market_summaries.append({
                "date":race["date"],"race":race["race"],"ticket_type":ticket_type,
                "all_pairs_checked":len(ev),"selected_pair_count":len(tickets),
                "probability_sum":sum(probs.values()),"tickets":tickets,
                "market_observed_utc":race["market_observed_utc"],
                "source_type":"LAB_SYNTHETIC_ONLY"})
            if tickets:
                candidates.append({
                    "date":race["date"],"race":race["race"],"ticket_type":ticket_type,
                    "prediction_ready":True, "market_verified":True,
                    "model_calibrated":True, "clock_verified":True,
                    "confidence":min(1.0,max(x["lower_bound_net_per_1"] for x in tickets)),
                    "tickets":tickets})
    # The flags above are local algebraic eligibility flags used ONLY by the
    # existing research allocator, never externally asserted live readiness.
    allocation=allocate_research_budget(candidates,daily_limit_yen=budget_yen)
    allocated_keys={(r["race"],r["ticket_type"]) for r in allocation["selected"]}
    output={
        "schema":"kyoto_rg02_dual_market_research_integrated.v1",
        "scope":"LAB_FIXTURE_NOT_REAL_RACING",
        "input_sha256":_hash(races),"market_summaries":market_summaries,
        "selected_allocations":allocation["selected"],
        "selected_market_keys":[list(x) for x in sorted(allocated_keys)],
        "budget_yen":budget_yen,"spent_yen":allocation["spent_yen"],
        "unspent_yen":allocation["unspent_yen"],
        "has_complete_market_coverage":True,
        "authorized_jra_source":False,
        "externally_verified_market":False,
        "calibrated_real_prediction":False,
        "real_bet_authorized":False,
        "prediction_ready":False,
        "real_paper_trade_recorded":False,
        "network_requests":0
    }
    if output["spent_yen"]>budget_yen:
        raise IntegratedMarketRejected("over_budget")
    output["receipt_sha256"]=_hash(output)
    return output
