"""P8-04 fixed-rubric RESEARCH acceptance; never an operational Cloud/billing certification.

The locked rubric accepts research-mode tests. An earlier auxiliary gate requiring
a personal $0 invoice is stronger than the original criterion and remains
a separate operational attestation; it cannot silently change the fixed rubric.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

SHADOW="diagnostics/p8_uploaded_archive_shadow_app.py"
CLOUD_POLICY="https://docs.streamlit.io/deploy/streamlit-community-cloud"

class ResearchGateError(ValueError):
    pass

def assess(*,cloud,local,workspace,source_sha,shadow_source,requirements):
    if not isinstance(source_sha,str) or re.fullmatch(r"[0-9a-f]{40}",source_sha) is None:
        raise ResearchGateError("valid_source_sha_required")
    if cloud.get("public_shadow_deployment_git_sha_verified") is not True:
        raise ResearchGateError("independent_public_cloud_deployment_required")
    # The remote browser receipt must carry source_sha, not a prior different app.
    if cloud.get("expected_sha")!=source_sha:
        raise ResearchGateError("public_source_sha_mismatch")
    if (cloud.get("fresh_browser_sessions")!=2 or
        len(cloud.get("observations",[]))!=2 or
        any(not (o.get("git_sha_matches") is True and
                 o.get("mobile_viewport")==390 and
                 o.get("read_only_missing_input_guard") is True and
                 o.get("no_betting_control") is True and
                 o.get("no_jra_browser_requests") is True)
            for o in cloud.get("observations",[]))):
        raise ResearchGateError("independent_public_mobile_controls_required")
    if cloud.get("actual_purchase_authorized") is not False:
        raise ResearchGateError("research_only_cloud_required")
    if (local.get("scope")!="GITHUB_RUNNER_LOCAL_ONLY_NOT_PUBLISHED_STREAMLIT_CLOUD"
        or local.get("source_app")!=SHADOW or local.get("restart_cycles")!=2
        or local.get("same_local_port_reused") is not True
        or local.get("same_controls_on_restart") is not True
        or local.get("actual_purchase_authorized") is not False):
        raise ResearchGateError("two_cycle_local_restart_research_required")
    if local.get("source_sha256")!=hashlib.sha256(shadow_source).hexdigest():
        raise ResearchGateError("local_restart_source_bytes_mismatch")
    app=workspace.get("app_identity",{})
    interpretation=workspace.get("interpretation",{})
    policies=workspace.get("official_sources",[])
    if (app.get("entrypoint")!=SHADOW or
        app.get("branch")!="jra-html-diagnostic-20261105" or
        app.get("url")!="https://kyoto-keiba-ai-5opazxhrw7xwh4imfemey6.streamlit.app" or
        interpretation.get("workspace_limits_visible") is not True or
        interpretation.get("official_free_service_policy_verified") is not True or
        not any(v.get("url")==CLOUD_POLICY and "free" in v.get("finding","").lower() for v in policies)):
        raise ResearchGateError("official_free_workspace_context_required")
    lines=[line.strip() for line in requirements.decode("utf-8").splitlines()
           if line.strip() and not line.lstrip().startswith("#")]
    if not lines or any(not (line.startswith("streamlit") or line.startswith("beautifulsoup4"))
                        for line in lines):
        raise ResearchGateError("unexpected_paid_or_external_shadow_dependency")
    src=shadow_source.decode("utf-8")
    if "st.secrets" in src or "requests." in src or "place_bet" in src:
        raise ResearchGateError("shadow_must_not_use_secrets_network_or_purchase")
    if interpretation.get("user_billing_transaction_history_independently_verified") is not False:
        raise ResearchGateError("research_only_no_personal_billing_claim")
    return {
      "schema":"kyoto_p8_04_fixed_rubric_research_acceptance.v1",
      "source_sha":source_sha,
      "public_cloud_mobile_browser_verified":True,
      "two_cycle_local_restart_research_verified":True,
      "community_cloud_free_official_policy_and_workspace_verified":True,
      "shadow_external_paid_dependencies_configured":False,
      "research_P8_04_accepted":True,
      "actual_cloud_admin_reboot_log_independently_verified":False,
      "individual_account_zero_billing_independently_verified":False,
      "operational_JRA_prediction_verified":False,
      "real_purchase_authorized":False,
      "extra_operational_evidence_gate_satisfied":False,
    }

def main():
    import argparse
    p=argparse.ArgumentParser()
    for name in ("cloud","local","workspace","source-sha","shadow-source","requirements","out"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    out=assess(cloud=json.loads(Path(a.cloud).read_text()),
        local=json.loads(Path(a.local).read_text()),
        workspace=json.loads(Path(a.workspace).read_text()),
        source_sha=a.source_sha,
        shadow_source=Path(a.shadow_source).read_bytes(),
        requirements=Path(a.requirements).read_bytes())
    b=json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    out["receipt_sha256"]=hashlib.sha256(b).hexdigest()
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("KYOTO_P8_04_FIXED_RUBRIC_RESEARCH_ACCEPTED=TRUE")
    print("KYOTO_P8_04_INDIVIDUAL_BILLING_VERIFIED=FALSE")

if __name__=="__main__":
    main()
