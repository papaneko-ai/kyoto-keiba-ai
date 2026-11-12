"""F07 fixed-rubric independent P3 quinella/bracket probability acceptance.

Pure math from pre-specified model strengths; all inputs are unauthenticated
offline test fixtures. Market availability is enforced, no live odds, bets,
result labels, training or historical-final-price interpolation.
"""
from __future__ import annotations

import hashlib
import json
import math

from diagnostics.p3_p6_research_no_bet import (
    ordered_first_second, quinella_from_strength, bracket_from_quinella
)

class F07Rejected(ValueError):
    pass

_ALLOWED = {"ACTIVE", "SCRATCHED", "EXCLUDED"}
_PAIRS = {"QUINELLA", "BRACKET"}

def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True,
            ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

def calculate_f07(*, runners, market_status, quoted_pairs):
    """Return exhaustive pair probabilities, or refuse rather than misprice.

    runners: [{number, frame, status, strength},...]
    market_status: {"QUINELLA":"OPEN","BRACKET":"OPEN"}
    quoted_pairs: exact pair lists for each market; used for coverage only.
    A same-frame bracket pair is emitted IFF >=2 active runners share frame.
    """
    if not isinstance(runners, list) or not 2 <= len(runners) <= 18:
        raise F07Rejected("runner_count_invalid")
    if type(market_status) is not dict or set(market_status) != _PAIRS:
        raise F07Rejected("market_status_schema_invalid")
    if type(quoted_pairs) is not dict or set(quoted_pairs) != _PAIRS:
        raise F07Rejected("market_pairs_schema_invalid")
    for market in _PAIRS:
        if market_status[market] != "OPEN":
            raise F07Rejected("market_not_open:" + market)

    strengths, frames, found, scratch = {}, {}, set(), []
    for r in runners:
        if type(r) is not dict or set(r) != {"number","frame","status","strength"}:
            raise F07Rejected("runner_schema_invalid")
        number, frame, status, strength = (r[k] for k in ("number","frame","status","strength"))
        if type(number) is not int or not 1 <= number <= 18 or number in found:
            raise F07Rejected("runner_identity_invalid")
        found.add(number)
        if type(frame) is not int or not 1 <= frame <= 8 or status not in _ALLOWED:
            raise F07Rejected("runner_frame_or_status_invalid")
        if type(strength) not in (int,float) or not math.isfinite(strength) or strength <= 0:
            raise F07Rejected("strength_invalid")
        if status == "ACTIVE":
            strengths[number] = strength
            frames[number] = frame
        else:
            scratch.append(number)
    if len(strengths) < 2:
        raise F07Rejected("active_runner_count_invalid")

    ordered = ordered_first_second(strengths)
    q = quinella_from_strength(strengths)
    b = bracket_from_quinella(q, frames)
    expected = {"QUINELLA":set(q), "BRACKET":set(b)}
    for market in _PAIRS:
        raw = quoted_pairs[market]
        if type(raw) is not list:
            raise F07Rejected("offered_pairs_not_list:" + market)
        seen = []
        for pair in raw:
            if type(pair) is not list or len(pair) != 2:
                raise F07Rejected("offered_pair_shape_invalid:" + market)
            a,c = pair
            maximum=18 if market=="QUINELLA" else 8
            if type(a) is not int or type(c) is not int or not (1 <= a <= maximum and 1 <= c <= maximum):
                raise F07Rejected("offered_pair_number_invalid:" + market)
            if a > c or (market=="QUINELLA" and a==c):
                raise F07Rejected("offered_pair_order_invalid:" + market)
            seen.append((a,c))
        if len(seen) != len(set(seen)) or set(seen) != expected[market]:
            raise F07Rejected("missing_or_extra_offered_pair:" + market)

    if not math.isclose(math.fsum(ordered.values()),1.0,abs_tol=1e-10,rel_tol=0):
        raise F07Rejected("ordered_mass_not_one")
    if not math.isclose(math.fsum(q.values()),1.0,abs_tol=1e-10,rel_tol=0):
        raise F07Rejected("quinella_mass_not_one")
    if not math.isclose(math.fsum(b.values()),1.0,abs_tol=1e-10,rel_tol=0):
        raise F07Rejected("bracket_mass_not_one")

    result = {
        "schema": "kyoto_F07_independent_math_receipt.v1",
        "scope": "OFFLINE_P3_PROBABILITY_INTEGRITY_ONLY",
        "active_runners":sorted(strengths),
        "scratched_or_excluded_runners":sorted(scratch),
        "ordered_first_second_pairs":len(ordered),
        "quinella": [{"pair":list(pair),"probability":p} for pair,p in sorted(q.items())],
        "bracket": [{"pair":list(pair),"probability":p} for pair,p in sorted(b.items())],
        "ordered_sum":math.fsum(ordered.values()),
        "quinella_sum":math.fsum(q.values()),
        "bracket_sum":math.fsum(b.values()),
        "same_frame_pairs":[list(pair) for pair in b if pair[0]==pair[1]],
        "market_coverage_verified":True,
        "live_source_authenticated":False,
        "price_ev_computed":False,
        "calibration_verified":False,
        "actual_bet_authorized":False
    }
    return {**result,"sha256":digest(result)}
