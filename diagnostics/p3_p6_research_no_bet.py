"""Research-only P3/P4/P5 engine. No approved model, bets or JRA network.

Mathematical PL/Harville pair mechanics + market price arithmetic can be
tested without pretending to have calibrated probabilities or true live odds.
"""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math

class ResearchRejected(ValueError):
    pass

def _positive(value, label):
    if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
        raise ResearchRejected(label + "_invalid")
    return float(value)

def ordered_first_second(weights):
    """Research-only Plackett-Luce P(i first, j second)."""
    if not isinstance(weights, dict) or not 2 <= len(weights) <= 18:
        raise ResearchRejected("runner_count_invalid")
    clean = {}
    for number, value in weights.items():
        if type(number) is not int or not 1 <= number <= 18:
            raise ResearchRejected("horse_number_invalid")
        clean[number] = _positive(value, "strength")
    total = sum(clean.values())
    ordered = {}
    for i in sorted(clean):
        for j in sorted(clean):
            if i != j:
                ordered[(i,j)] = (clean[i] / total) * (clean[j] / (total - clean[i]))
    return ordered

def quinella_from_strength(weights):
    """Exhaustive theoretical quinella joint probability; uncalibrated."""
    ordered = ordered_first_second(weights)
    numbers = sorted(weights)
    result = {(i,j): ordered[(i,j)] + ordered[(j,i)]
              for ix,i in enumerate(numbers) for j in numbers[ix+1:]}
    if not math.isclose(sum(result.values()), 1.0, abs_tol=1e-12):
        raise ResearchRejected("joint_probabilities_not_normalized")
    return result

def bracket_from_quinella(pair_prob, frames):
    """Aggregate HORSE pairs into unordered FRAME pairs incl. same-frame 1-1.

    No assumption that a frame ticket is offered or active; must check market.
    """
    if not isinstance(frames, dict) or not frames:
        raise ResearchRejected("missing_frames")
    sums = {}
    for pair,p in pair_prob.items():
        if not isinstance(pair, tuple) or len(pair)!=2 or pair[0]==pair[1]:
            raise ResearchRejected("invalid_quinella_pair")
        a,b = pair
        if a not in frames or b not in frames:
            raise ResearchRejected("frame_missing_for_runner")
        x,y = frames[a],frames[b]
        if type(x) is not int or type(y) is not int or not 1 <= x <= 8 or not 1 <= y <= 8:
            raise ResearchRejected("frame_value_invalid")
        if type(p) not in (float,int) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ResearchRejected("pair_probability_invalid")
        key=tuple(sorted((x,y)))
        sums[key]=sums.get(key,0.0)+float(p)
    if not math.isclose(sum(sums.values()),1.0,abs_tol=1e-10):
        raise ResearchRejected("bracket_probability_not_normalized")
    return dict(sorted(sums.items()))

def _money_odds(raw):
    if isinstance(raw, bool):
        raise ResearchRejected("odds_invalid")
    try:
        x=Decimal(str(raw))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise ResearchRejected("odds_invalid") from exc
    if not x.is_finite() or not Decimal("1") < x < Decimal("100000"):
        raise ResearchRejected("odds_invalid")
    return x

def market_ev(pair_probs, market, *, uncertainty_margin=0.0):
    """Unit-stake theoretical gross return, require exact market coverage.

    Odds are NOT inferred here; caller must provide externally authenticated
    official prerace odds and later establish market completeness.
    """
    if type(uncertainty_margin) not in (float,int) or not 0 <= uncertainty_margin < 1:
        raise ResearchRejected("uncertainty_invalid")
    if not isinstance(market,dict) or set(market)!=set(pair_probs):
        raise ResearchRejected("market_coverage_mismatch")
    result=[]
    for pair in sorted(pair_probs):
        p=pair_probs[pair]
        if type(p) not in (float,int) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ResearchRejected("pair_probability_invalid")
        odds=_money_odds(market[pair])
        gross=float(odds)*float(p)
        robust=float(odds)*float(p)*(1-float(uncertainty_margin))
        result.append({"pair":pair,"theoretical_probability":float(p),
                       "decimal_odds":str(odds),
                       "gross_return_per_1":gross,
                       "expected_net_per_1":gross-1.0,
                       "lower_bound_net_per_1":robust-1.0})
    return result

def allocate_research_budget(races, *, daily_limit_yen):
    """Research scenario only. Never turns an unapproved record into a bet."""
    if type(daily_limit_yen) is not int or daily_limit_yen < 0 or daily_limit_yen%100:
        raise ResearchRejected("budget_invalid")
    if not isinstance(races,list) or len(races)>12:
        raise ResearchRejected("race_list_invalid")
    eligible=[]
    seen=set()
    for race in races:
        if not isinstance(race,dict):
            raise ResearchRejected("race_invalid")
        key=(race.get("date"),race.get("race"),race.get("ticket_type"))
        if key in seen:
            raise ResearchRejected("duplicate_race")
        seen.add(key)
        if race.get("prediction_ready") is not True or race.get("market_verified") is not True:
            continue
        if race.get("model_calibrated") is not True or race.get("clock_verified") is not True:
            continue
        tickets=race.get("tickets")
        if not isinstance(tickets,list) or not 1 <= len(tickets) <= 3:
            continue
        if any(type(t.get("amount_yen")) is not int or t["amount_yen"] < 100
               or t["amount_yen"]%100 for t in tickets if isinstance(t,dict)):
            raise ResearchRejected("stake_invalid")
        if any(not isinstance(t,dict) for t in tickets):
            raise ResearchRejected("ticket_invalid")
        eligible.append((race,tickets))
    # Budget is a ceiling. Prefer keeping capital unspent, no forced allocation.
    eligible.sort(key=lambda rt:(-float(rt[0].get("confidence",0)),rt[0]["race"]))
    selected=[]
    spent=0
    for race,tickets in eligible:
        cost=sum(t["amount_yen"] for t in tickets)
        if len(selected)>=4 or spent+cost>daily_limit_yen:
            continue
        selected.append({"race":race["race"],"ticket_type":race["ticket_type"],
                         "tickets":tickets,"total_yen":cost})
        spent+=cost
    return {"status":"RESEARCH_ALLOCATION_ONLY_NOT_AUTHORIZED",
            "selected":selected, "spent_yen":spent,
            "unspent_yen":daily_limit_yen-spent,
            "prediction_ready":False,"live_bet_authorized":False}

def historical_no_bet_receipt(matrix_rows):
    """Create reproducible refusal receipt from historical feature records."""
    if not isinstance(matrix_rows,list) or not matrix_rows:
        raise ResearchRejected("features_missing")
    if any(not isinstance(row,dict) or row.get("source_row_status") !=
           "HISTORICAL_NOT_MODEL_ELIGIBLE" for row in matrix_rows):
        raise ResearchRejected("history_source_state_invalid")
    canon=json.dumps(matrix_rows,ensure_ascii=False,sort_keys=True,
                     separators=(",",":")).encode("utf-8")
    return {"schema":"kyoto_p3_p6_historical_no_bet_receipt.v1",
            "feature_sha256":sha256(canon).hexdigest(),
            "runner_count":len(matrix_rows),
            "reason_codes":["HISTORICAL_CLOSED_MEETING","NO_CALIBRATED_P3_MODEL",
                            "NO_VERIFIED_PRERACE_QUINELLA_ODDS",
                            "NO_VERIFIED_PRERACE_BRACKET_ODDS",
                            "P1_SOURCE_AUTHENTICITY_UNVERIFIED"],
            "suggested_races":[],"quinella_tickets":[],
            "bracket_tickets":[],"virtual_investment_yen":0,
            "ledger_events_written":0,
            "model_calibrated":False, "market_verified":False,
            "prediction_ready":False,"actual_purchase":False,
            "historical_analysis_only":True}
