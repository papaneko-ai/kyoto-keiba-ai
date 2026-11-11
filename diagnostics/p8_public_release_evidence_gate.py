"""P8-04 release evidence gate. No production/Cloud writes; fail closed.

Research CI passing does NOT authorize claiming billing or reboot evidence.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

STREAMLIT_FREE_POLICY="https://docs.streamlit.io/deploy/streamlit-community-cloud"

class P8ReleaseEvidenceError(ValueError):
    pass

def assess_p8_release(evidence):
    if not isinstance(evidence,dict):
        raise P8ReleaseEvidenceError("evidence_object_required")
    expected_sha=evidence.get("head_sha")
    if not isinstance(expected_sha,str) or re.fullmatch(r"[0-9a-f]{40}",expected_sha) is None:
        raise P8ReleaseEvidenceError("commit_sha_required")
    remote=evidence.get("external_cloud")
    reboot=evidence.get("cloud_reboot")
    price=evidence.get("cost")
    if any(not isinstance(obj,dict) for obj in (remote,reboot,price)):
        raise P8ReleaseEvidenceError("three_independent_evidence_sections_required")
    if (remote.get("sha")!=expected_sha or remote.get("ci_conclusion")!="success"
        or remote.get("verified") is not True
        or not isinstance(remote.get("run_id"),int) or remote.get("run_id")<=0
        or not isinstance(remote.get("receipt_sha256"),str)
        or re.fullmatch(r"[0-9a-f]{64}",remote["receipt_sha256"]) is None):
        raise P8ReleaseEvidenceError("verified_external_browser_receipt_required")
    if reboot.get("operation_confirmed") is True:
        if (reboot.get("before_sha")!=expected_sha or reboot.get("after_sha")!=expected_sha
            or not isinstance(reboot.get("independent_record"),str)
            or not reboot["independent_record"].strip()
            or not isinstance(reboot.get("operator_record"),str)
            or not reboot["operator_record"].strip()):
            raise P8ReleaseEvidenceError("independent_reboot_and_recovery_record_required")
    if price.get("official_community_free_policy") is True:
        if price.get("policy_url")!=STREAMLIT_FREE_POLICY:
            raise P8ReleaseEvidenceError("authoritative_free_policy_url_required")
    if price.get("account_no_charge_verified") is True:
        if (not isinstance(price.get("account_evidence"),str)
            or not price["account_evidence"].strip()):
            raise P8ReleaseEvidenceError("independent_account_billing_record_required")
    complete=(reboot.get("operation_confirmed") is True and
              price.get("official_community_free_policy") is True and
              price.get("account_no_charge_verified") is True)
    result={
      "schema":"kyoto_p8_04_public_release_evidence_gate.v1",
      "head_sha":expected_sha,
      "remote_browser_certified":True,
      "independent_reboot_certified":reboot.get("operation_confirmed") is True,
      "official_community_free_policy_confirmed":price.get("official_community_free_policy") is True,
      "account_billing_record_verified":price.get("account_no_charge_verified") is True,
      "P8_04_full_release_certified":bool(complete),
      "actual_purchase_authorized":False,
      "operational_JRA_racing_certified":False}
    digest=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {**result,"receipt_sha256":digest}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    report=assess_p8_release(json.loads(Path(a.evidence).read_text(encoding="utf-8")))
    Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("KYOTO_P8_04_FULL_RELEASE_CERTIFIED="+str(report["P8_04_full_release_certified"]).upper())

if __name__=="__main__":main()
