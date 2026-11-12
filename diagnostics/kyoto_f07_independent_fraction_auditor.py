"""Independent, read-only F07 acceptance auditor.

This implementation does NOT import the algorithm under review. Calculates
all ordered PL probabilities with Fraction, checks every horse/frame pair,
source witness hash, fixed status and GitHub action provenance. Separately
checks that 16 distinct field entries and 8 two-runner frames exactly match.
Cannot grant live JRA data authenticity or other F01-F20 gates.
"""
from __future__ import annotations
import hashlib,json,math,re
from fractions import Fraction

RUN_ID="43132839820"
SOURCE_SHA="1f002d8572a16aa60f269f8f8bad3859165582e7"
RUBRIC_SHA="92bae5c1d61d6ac00a5380dd8d5e08beb59f96c898b03c05a3c8bf8721ced632"
class AuditRejected(ValueError):
    pass
def canonical(x):
    return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
def digest(x):
    return hashlib.sha256(canonical(x).encode("utf-8")).hexdigest()
def audit(receipt, rubric_bytes):
    if hashlib.sha256(rubric_bytes).hexdigest()!=RUBRIC_SHA:
        raise AuditRejected("rubric_changed")
    rubric=json.loads(rubric_bytes)
    rule=next(x for x in rubric["criteria"] if x["id"]=="F07")
    if rule["points"]!=5 or rule["phase"]!="P3" or rule["mandatory"] is not True:
        raise AuditRejected("f07_fixed_rule_invalid")
    if receipt.get("ci_run_id")!=RUN_ID or receipt.get("ci_head_sha")!=SOURCE_SHA:
        raise AuditRejected("unexpected_source_run")
    if receipt.get("schema")!="kyoto_F07_independent_math_receipt.v1" or receipt.get("scope")!="OFFLINE_P3_PROBABILITY_INTEGRITY_ONLY":
        raise AuditRejected("witness_scope_mismatch")
    if (receipt.get("active_runners") != list(range(1,17)) or
        receipt.get("scratched_or_excluded_runners")!=[] or
        receipt.get("ordered_first_second_pairs")!=240 or
        receipt.get("same_frame_pairs")!=[[i,i] for i in range(1,9)] or
        receipt.get("market_coverage_verified") is not True):
        raise AuditRejected("witness_field_and_frame_mismatch")
    for k in ("live_source_authenticated","price_ev_computed","calibration_verified","actual_bet_authorized","live_market_source_accepted","production_deployment_authorized"):
        if receipt.get(k) is not False:
            raise AuditRejected("false_live_readiness_claim:"+k)
    before={k:v for k,v in receipt.items() if k not in (
        "ci_run_id","ci_head_sha","f07_fixed_acceptance_verified_by",
        "live_market_source_accepted","production_deployment_authorized","sha256")}
    if receipt["sha256"]!=digest(before):
        raise AuditRejected("witness_hash_tampered")
    # Deliberately do not call the original PL pair calculation code.
    weights={i:Fraction(i,1) for i in range(1,17)}
    total=sum(weights.values(),Fraction())
    horse={}
    for i in range(1,17):
        for j in range(i+1,17):
            pi=(weights[i]/total)*(weights[j]/(total-weights[i]))
            pj=(weights[j]/total)*(weights[i]/(total-weights[j]))
            horse[(i,j)]=pi+pj
    bracket={}
    for (i,j),prob in horse.items():
        pair=tuple(sorted(((i+1)//2,(j+1)//2)))
        bracket[pair]=bracket.get(pair,Fraction())+prob
    if sum(horse.values()) != 1 or sum(bracket.values()) != 1:
        raise AuditRejected("independent_exact_probability_sum_failed")
    if len(horse)!=120 or len(bracket)!=36:
        raise AuditRejected("independent_pair_universe_wrong")
    for market,expected in (("quinella",horse),("bracket",bracket)):
        data=receipt.get(market)
        if type(data) is not list or len(data)!=len(expected):
            raise AuditRejected("witness_pair_count_wrong:"+market)
        observed={}
        for row in data:
            if not isinstance(row,dict) or set(row)!={"pair","probability"}:
                raise AuditRejected("witness_pair_row_invalid")
            pair=row["pair"]
            if type(pair) is not list or len(pair)!=2 or any(type(x) is not int for x in pair):
                raise AuditRejected("witness_pair_identity_invalid")
            key=tuple(pair)
            if key in observed or type(row["probability"]) not in (float,int) or not math.isfinite(row["probability"]):
                raise AuditRejected("witness_duplicate_or_probability_invalid")
            observed[key]=row["probability"]
        if set(observed)!=set(expected):
            raise AuditRejected("witness_pair_keys_mismatch")
        for key,value in expected.items():
            if not math.isclose(observed[key],float(value),rel_tol=0,abs_tol=2e-14):
                raise AuditRejected("independent_fraction_probability_mismatch:"+market)
        if not math.isclose(math.fsum(observed.values()),1.0,rel_tol=0,abs_tol=1e-12):
            raise AuditRejected("witness_probability_mass_mismatch")
    return {
        "schema":"kyoto_F07_independent_acceptance_audit.v1",
        "gate":"F07",
        "accepted_points":5,
        "acceptance":"PASS_OFFLINE_MATH_ONLY",
        "source_ci_run_id":int(RUN_ID),
        "source_ci_head_sha":SOURCE_SHA,
        "source_rubric_sha256":RUBRIC_SHA,
        "source_witness_sha256":receipt["sha256"],
        "independent_algorithm":"exact_rational_PL_combinatorics_no_import_under_review",
        "positive_negative_suite":"18_unittest_cases_ci_success_required",
        "independent_exact_horse_pair_count":len(horse),
        "independent_exact_bracket_pair_count":len(bracket),
        "live_source_independently_verified":False,
        "real_market_or_model_calibration_accepted":False,
        "F01_to_F06_accepted":False,
        "F08_to_F20_accepted":False,
        "final_completion_certified":False
    }
