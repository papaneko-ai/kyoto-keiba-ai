"""Destructive tests: never inflate P8-04 from remote CI and free policy alone."""
import copy
import unittest
from diagnostics.p8_public_release_evidence_gate import (
    assess_p8_release,P8ReleaseEvidenceError,STREAMLIT_FREE_POLICY)

class P8EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.e={
            "head_sha":"a"*40,
            "external_cloud":{"sha":"a"*40,"ci_conclusion":"success",
                "verified":True,"run_id":42953012865,"receipt_sha256":"b"*64},
            "cloud_reboot":{"operation_confirmed":False,
                "before_sha":"a"*40,"after_sha":"a"*40,
                "operator_record":"","independent_record":""},
            "cost":{"official_community_free_policy":True,
                "policy_url":STREAMLIT_FREE_POLICY,
                "account_no_charge_verified":False,"account_evidence":""}}
    def test_real_current_evidence_never_scores_100(self):
        r=assess_p8_release(self.e)
        self.assertTrue(r["remote_browser_certified"])
        self.assertTrue(r["official_community_free_policy_confirmed"])
        self.assertFalse(r["P8_04_full_release_certified"])
        self.assertFalse(r["account_billing_record_verified"])
    def test_missing_external_proof_fails_closed(self):
        for key,value in [("sha","c"*40),("ci_conclusion","failure"),
                          ("verified",False),("receipt_sha256","bad")]:
            e=copy.deepcopy(self.e);e["external_cloud"][key]=value
            with self.subTest(key=key),self.assertRaises(P8ReleaseEvidenceError):
                assess_p8_release(e)
    def test_free_policy_does_not_equal_account_billing(self):
        r=assess_p8_release(self.e)
        self.assertFalse(r["account_billing_record_verified"])
        e=copy.deepcopy(self.e);e["cost"]["account_no_charge_verified"]=True
        with self.assertRaises(P8ReleaseEvidenceError):assess_p8_release(e)
    def test_unverified_reboot_cannot_claim_success(self):
        e=copy.deepcopy(self.e);e["cloud_reboot"]["operation_confirmed"]=True
        with self.assertRaises(P8ReleaseEvidenceError):assess_p8_release(e)
    def test_reboot_and_account_proofs_both_required(self):
        e=copy.deepcopy(self.e)
        e["cloud_reboot"].update(operation_confirmed=True,
            operator_record="operator event record reference",
            independent_record="independent reboot validation reference")
        self.assertFalse(assess_p8_release(e)["P8_04_full_release_certified"])
        e["cost"].update(account_no_charge_verified=True,
                           account_evidence="verified billing account record reference")
        r=assess_p8_release(e)
        self.assertTrue(r["P8_04_full_release_certified"])
        self.assertFalse(r["operational_JRA_racing_certified"])
        self.assertFalse(r["actual_purchase_authorized"])
    def test_noncanonical_commit_rejected(self):
        for val in ("a"*7,"A"*40,"z"*40,None):
            e=copy.deepcopy(self.e);e["head_sha"]=val
            with self.subTest(val=val),self.assertRaises(P8ReleaseEvidenceError):
                assess_p8_release(e)

if __name__=="__main__":unittest.main()
