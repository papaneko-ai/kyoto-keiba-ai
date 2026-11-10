"""Research graduation metric, independent of P1-P8 score and live operational score.

Individual prerequisite credits are derived ONLY from the already verified
fixed-rubric CI progress report. Integration credits demand a separate accepted
integration-proof record. Never infer E2E from isolated unit tests.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

RUBRIC = "docs/diagnostics/kyoto_research_graduation_rubric_v1.json"
INTEGRATION = "docs/diagnostics/kyoto_research_graduation_integration_claims_v1.json"
AREAS = ("RG-01", "RG-02", "RG-03", "RG-04", "RG-05", "RG-06")

class GraduationRejected(ValueError):
    pass

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def evaluate(rubric, verified_progress, integrations, *, accepted_integration_proofs=None):
    if (type(rubric) is not dict or rubric.get("schema") != "kyoto_research_graduation_rubric.v1"
            or rubric.get("criterion_count") != 12
            or rubric.get("graduate_requires") != "all_12_passed"
            or rubric.get("scope") != "RESEARCH_LAB_ONLY"):
        raise GraduationRejected("fixed_graduation_rubric_invalid")
    areas = rubric.get("areas")
    if type(areas) is not list or tuple(a.get("id") for a in areas) != AREAS:
        raise GraduationRejected("six_fixed_areas_changed")
    for area in areas:
        if set(area) != {"id","title","component","integration"}:
            raise GraduationRejected("area_schema_invalid")
        c, g = area["component"], area["integration"]
        if (set(c) != {"id","title","requires_progress_ids"} or
                set(g) != {"id","title"} or c["id"] != area["id"]+"A" or
                g["id"] != area["id"]+"B" or type(c["requires_progress_ids"]) is not list
                or len(c["requires_progress_ids"]) != 2 or
                any(type(v) is not str for v in c["requires_progress_ids"])):
            raise GraduationRejected("criterion_mutation_detected")
    if (type(verified_progress) is not dict or
            verified_progress.get("schema") != "kyoto_progress_result.v1" or
            verified_progress.get("scope_id") != "KYOTO_P1_P8_FIXED_20261110" or
            type(verified_progress.get("passed_ids")) is not list):
        raise GraduationRejected("validated_P1_P8_report_required")
    if type(integrations) is not dict or integrations.get("schema") != "kyoto_research_graduation_integration_claims.v1":
        raise GraduationRejected("integration_claim_schema_invalid")
    claims = integrations.get("claims")
    if type(claims) is not list:
        raise GraduationRejected("integration_claims_must_be_list")
    valid_integrated = {a["integration"]["id"] for a in areas}
    if len({c.get("id") for c in claims}) != len(claims) or any(
            type(c) is not dict or set(c) != {"id","proof_run_id","proof_job_id",
                    "proof_head_sha","source_paths","acceptance_test"} or
            c["id"] not in valid_integrated for c in claims):
        raise GraduationRejected("invalid_or_duplicate_integration_claim")
    allowed = set(accepted_integration_proofs or ())
    if any(c["id"] not in allowed for c in claims):
        raise GraduationRejected("unverified_integration_proof_claim")
    passes = set(verified_progress["passed_ids"])
    rows=[]
    for area in areas:
        c=area["component"]; g=area["integration"]
        component_pass=all(k in passes for k in c["requires_progress_ids"])
        integration_pass=component_pass and g["id"] in allowed and any(
            claim["id"]==g["id"] for claim in claims)
        rows.append({"id":area["id"],"title":area["title"],
                     "component_pass":component_pass,"integration_pass":integration_pass,
                     "component_requires":c["requires_progress_ids"]})
    credits=sum(int(row["component_pass"])+int(row["integration_pass"]) for row in rows)
    out={"schema":"kyoto_research_graduation_result.v1",
         "rubric_sha256":hashlib.sha256(canonical(rubric)).hexdigest(),
         "progress_source_commit":verified_progress.get("source_commit"),
         "progress_score_percent":verified_progress.get("score_percent"),
         "graduation_passed_conditions":credits,"graduation_total_conditions":12,
         "graduation_percent":round(credits*100/12,1),
         "graduation_eligible":credits==12,
         "integration_passed":sum(int(r["integration_pass"]) for r in rows),
         "integration_total":6,
         "interpretation":"RESEARCH_GRADUATION_PREREQUISITES_NOT_LIVE_READINESS",
         "areas":rows}
    return out

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--progress",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args(argv)
    root=Path(args.root)
    read=lambda file:json.loads(Path(file).read_text(encoding="utf-8"))
    progress=read(args.progress)
    if not os.getenv("GITHUB_SHA") or progress.get("source_commit")!=os.environ["GITHUB_SHA"]:
        raise GraduationRejected("progress_must_be_verified_on_current_SHA")
    rubric=read(root/RUBRIC)
    claims=read(root/INTEGRATION)
    # Deliberately fail closed: integration proofs require independent checking.
    # No integration claims are currently accepted by this metric.
    if claims.get("claims"):
        raise GraduationRejected("independent_integration_proof_verifier_not_yet_enabled")
    result=evaluate(rubric,progress,claims)
    Path(args.out).write_bytes(canonical(result)+b"\\n")
    print("KYOTO_RESEARCH_GRADUATION="+str(result["graduation_percent"])+"%")
    print("KYOTO_RESEARCH_GRADUATION_CONDITIONS="+str(result["graduation_passed_conditions"])+"/12")
    print("KYOTO_RESEARCH_GRADUATION_INTEGRATED="+str(result["integration_passed"])+"/6")
    print("KYOTO_RESEARCH_GRADUATION_ELIGIBLE="+str(result["graduation_eligible"]).upper())
    return result

if __name__=="__main__":
    main()
