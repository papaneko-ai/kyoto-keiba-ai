"""Adversarial tests of original P8-04 research acceptance versus operational attestation."""
import copy
import hashlib
import unittest
from diagnostics.p8_fixed_rubric_research_acceptance import assess,ResearchGateError,SHADOW,CLOUD_POLICY

SHA="a"*40
SHADOW_SOURCE=b'import streamlit as st\nst.title("research")'
REQUIREMENTS=b"streamlit>=1.37,<2\nbeautifulsoup4>=4.12,<5\n"
def fixtures():
    return dict(
      cloud=dict(expected_sha=SHA,public_shadow_deployment_git_sha_verified=True,
        fresh_browser_sessions=2,observations=[dict(git_sha_matches=True,
        mobile_viewport=390,read_only_missing_input_guard=True,
        no_betting_control=True,no_jra_browser_requests=True) for _ in range(2)],
        actual_purchase_authorized=False,
        actual_cloud_instance_reboot_verified=False,
        cloud_billing_and_free_tier_account_verified=False),
      local=dict(scope="GITHUB_RUNNER_LOCAL_ONLY_NOT_PUBLISHED_STREAMLIT_CLOUD",
        source_app=SHADOW,restart_cycles=2,same_local_port_reused=True,
        same_controls_on_restart=True,actual_purchase_authorized=False,
        source_sha256=hashlib.sha256(SHADOW_SOURCE).hexdigest()),
      workspace=dict(app_identity=dict(entrypoint=SHADOW,
        branch="jra-html-diagnostic-20261105",
        url="https://kyoto-keiba-ai-5opazxhrw7xwh4imfemey6.streamlit.app"),
        interpretation=dict(workspace_limits_visible=True,
          official_free_service_policy_verified=True,
          user_billing_transaction_history_independently_verified=False),
        official_sources=[dict(url=CLOUD_POLICY,finding="all for free")]),
      source_sha=SHA,shadow_source=SHADOW_SOURCE,requirements=REQUIREMENTS)

class P8ResearchGateTests(unittest.TestCase):
    def test_original_research_mode_can_pass_without_invented_invoice(self):
        r=assess(**fixtures())
        self.assertTrue(r["research_P8_04_accepted"])
        self.assertFalse(r["individual_account_zero_billing_independently_verified"])
        self.assertFalse(r["actual_cloud_admin_reboot_log_independently_verified"])
        self.assertFalse(r["operational_JRA_prediction_verified"])
        self.assertFalse(r["extra_operational_evidence_gate_satisfied"])
    def test_remote_falsification_fails(self):
        for section,key,value in [
            ("cloud","expected_sha","b"*40),
            ("cloud","public_shadow_deployment_git_sha_verified",False),
            ("cloud","fresh_browser_sessions",1),
            ("cloud","actual_purchase_authorized",True),
            ("local","restart_cycles",1),
            ("local","same_controls_on_restart",False),
            ("local","source_sha256","bad"),
            ("workspace","official_sources",[]),
            ("workspace","app_identity",{}),
            ("workspace","interpretation",{}),
        ]:
            e=fixtures();e[section][key]=value
            with self.subTest(section=section,key=key),self.assertRaises(ResearchGateError):
                assess(**e)
    def test_reject_remote_mobile_control_bypass(self):
        for k,v in [("git_sha_matches",False),("mobile_viewport",1280),
                    ("no_betting_control",False),("no_jra_browser_requests",False),
                    ("read_only_missing_input_guard",False)]:
            e=fixtures();e["cloud"]["observations"][0][k]=v
            with self.subTest(k=k),self.assertRaises(ResearchGateError):
                assess(**e)
    def test_paid_dependency_or_secret_access_denied(self):
        for requirement in (b"streamlit>=1.37\nrequests\n",b"openai>=1.0\n"):
            e=fixtures();e["requirements"]=requirement
            with self.assertRaises(ResearchGateError): assess(**e)
        e=fixtures();e["shadow_source"]=b"st.secrets['TOKEN']"
        e["local"]["source_sha256"]=hashlib.sha256(e["shadow_source"]).hexdigest()
        with self.assertRaises(ResearchGateError):assess(**e)
    def test_research_does_not_claim_personal_billing_verified(self):
        e=fixtures()
        e["workspace"]["interpretation"]["user_billing_transaction_history_independently_verified"]=True
        with self.assertRaises(ResearchGateError):assess(**e)
    def test_determinism(self):
        e=fixtures();self.assertEqual(assess(**e),assess(**copy.deepcopy(e)))

if __name__=="__main__":unittest.main()
