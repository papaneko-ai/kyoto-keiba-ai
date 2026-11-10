"""Independent *research fixture* challenger audit for P7-02.

This is a second scorer over the frozen holdout contract in
p7_independent_holdout_research.  Uses an independent Brier formula and
an exact one-sided sign test, with Bonferroni adjustment for all declared
candidate comparisons.  The scorer CANNOT verify authenticity of official
JRA source bytes, external timestamping, or actual deployment.

A PASS below certifies only the research-gate implementation on LAB inputs.
It is not a certificate that a racing model has evolved in the real world.
"""
from __future__ import annotations

from math import comb, fsum, isfinite
from diagnostics.p7_independent_holdout_research import (
    adjudicate, AuditRejected, digest
)

class IndependentResearchRejected(ValueError):
    pass

def independent_research_audit(plan, observations, *, alpha=0.05):
    if type(alpha) not in (float, int) or not isfinite(alpha) or not 0 < alpha <= 0.05:
        raise IndependentResearchRejected("audit_alpha_invalid")
    initial=adjudicate(plan, observations)
    improvements=[]
    score_champion=[]
    score_candidate=[]
    for row in observations:
        y=row["outcome"]
        old=(row["champion_probability"]-y)**2
        new=(row["candidate_probability"]-y)**2
        score_champion.append(old)
        score_candidate.append(new)
        improvements.append(old-new)
    n=len(improvements)
    n_win=sum(x>0 for x in improvements)
    n_loss=sum(x<0 for x in improvements)
    decisive=n_win+n_loss
    if not decisive:
        p_value=1.0
    else:
        p_value=sum(comb(decisive,k) for k in range(n_win,decisive+1))/(2**decisive)
    adjusted_p=min(1.0,p_value*plan["comparison_count"])
    brier_gain=fsum(improvements)/n
    pass_rules=(initial["research_verdict"]=="RESEARCH_HOLDOUT_PASS"
          and brier_gain>0 and adjusted_p<=alpha)
    details={
        "schema":"kyoto_p7_independent_research_audit.v1",
        "scope":"SYNTHETIC_OR_RESEARCH_ONLY_NOT_REAL_EVOLUTION_CERTIFICATION",
        "plan_sha256":initial["plan_sha256"],
        "observations_sha256":initial["observations_sha256"],
        "primary_holdout_receipt_sha256":initial["receipt_sha256"],
        "paired_race_count":n,
        "champion_mean_brier":fsum(score_champion)/n,
        "candidate_mean_brier":fsum(score_candidate)/n,
        "paired_brier_gain":brier_gain,
        "sign_test_p_one_sided":p_value,
        "bonferroni_adjusted_p":adjusted_p,
        "alpha_predeclared":alpha,
        "trial_count":plan["comparison_count"],
        "independent_algorithm_agrees":(brier_gain>0)==(initial["mean_log_loss_gain"]>0),
        "research_gate":"LAB_ONLY_PASS" if pass_rules else "LAB_ONLY_REJECT",
        "evolution_certified_on_official_evidence":False,
        "real_operational_score_eligible":False,
        "production_model_changed":False,
        "auto_promote":False,
        "actual_bet_authorized":False,
    }
    if not details["independent_algorithm_agrees"]:
        raise IndependentResearchRejected("independent_score_disagreement")
    return {**details,"audit_sha256":digest(details)}
