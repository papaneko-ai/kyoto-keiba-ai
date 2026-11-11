"""Offline destructive tests for remote deployment verification contracts."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from diagnostics.p8_cloud_release_gate import validate_target
from diagnostics.p8_cloud_source_identity import source_checkout_sha


class CloudShadowProvenanceTests(unittest.TestCase):
    SHA="a"*40
    def test_public_streamlit_subdomain_accepted(self):
        self.assertEqual(
           validate_target("https://kyoto-ai-p8-shadow.streamlit.app/",self.SHA),
           "https://kyoto-ai-p8-shadow.streamlit.app")

    def test_other_websites_are_rejected(self):
        for site in ("https://jra.go.jp","https://example.com",
                     "https://streamlit.app.evil.test","https://evilstreamlit.app"):
            with self.subTest(site=site),self.assertRaises(ValueError):
                validate_target(site,self.SHA)

    def test_no_http_accepted(self):
        with self.assertRaises(ValueError):
            validate_target("http://safe.streamlit.app",self.SHA)

    def test_no_url_parameters_or_credentials(self):
        for suffix in ("?token=123","#fragment","/outside",":1234"):
            with self.subTest(suffix=suffix),self.assertRaises(ValueError):
                validate_target("https://safe.streamlit.app"+suffix,self.SHA)
        with self.assertRaises(ValueError):
            validate_target("https://user:password@safe.streamlit.app",self.SHA)

    def test_source_sha_exact_required(self):
        for s in (None,"",self.SHA[:12],self.SHA.upper(),"g"*40):
            with self.subTest(sha=s),self.assertRaises(ValueError):
                validate_target("https://safe.streamlit.app",s)

    @patch("diagnostics.p8_cloud_source_identity.subprocess.run")
    def test_git_sha_from_actual_checkout(self,runner):
        runner.return_value=subprocess.CompletedProcess(
            ["git"],0,self.SHA+"\n","")
        self.assertEqual(source_checkout_sha(),self.SHA)
        runner.assert_called_once()
        self.assertEqual(runner.call_args[0][0],["git","rev-parse","--verify","HEAD"])
        self.assertFalse(runner.call_args.kwargs.get("shell",False))

    @patch("diagnostics.p8_cloud_source_identity.subprocess.run")
    def test_unverifiable_checkout_denied(self,runner):
        runner.return_value=subprocess.CompletedProcess(["git"],128,"","not a repo")
        self.assertEqual(source_checkout_sha(),"UNKNOWN_NOT_CERTIFIED")

    @patch("diagnostics.p8_cloud_source_identity.subprocess.run")
    def test_short_git_sha_denied(self,runner):
        runner.return_value=subprocess.CompletedProcess(["git"],0,self.SHA[:7],"")
        self.assertEqual(source_checkout_sha(),"UNKNOWN_NOT_CERTIFIED")

    @patch("diagnostics.p8_cloud_source_identity.subprocess.run")
    def test_git_timeout_denied(self,runner):
        runner.side_effect=subprocess.TimeoutExpired("git",3)
        self.assertEqual(source_checkout_sha(),"UNKNOWN_NOT_CERTIFIED")

    @patch("diagnostics.p8_cloud_source_identity.subprocess.run")
    def test_missing_git_denied(self,runner):
        runner.side_effect=FileNotFoundError("git missing")
        self.assertEqual(source_checkout_sha(),"UNKNOWN_NOT_CERTIFIED")

    def test_deployable_subdirectory_dependencies_separate(self):
        root=Path(__file__).resolve().parents[1]
        deps=(root/"diagnostics/requirements.txt").read_text()
        self.assertIn("streamlit",deps)
        self.assertIn("beautifulsoup4",deps)
        self.assertFalse("turso" in deps.lower())
        self.assertFalse("playwright" in deps.lower())

    def test_shadow_shows_identity_not_wager(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/"diagnostics/p8_uploaded_archive_shadow_app.py").read_text()
        self.assertIn("source_checkout_sha()",app)
        self.assertIn("実運用予測、馬券購入は認定しません",app)
        self.assertNotIn("requests.get",app)
        self.assertNotIn("place_bet",app)

    def test_remote_receipt_always_excludes_cloud_reboot_billing(self):
        import inspect
        from diagnostics.p8_cloud_release_gate import probe_public_shadow_app
        src=inspect.getsource(probe_public_shadow_app)
        for key in ("actual_cloud_instance_reboot_verified",
                    "cloud_billing_and_free_tier_account_verified",
                    "P8_04_full_release_certified"):
            self.assertIn('"'+key+'":False',src)

if __name__=="__main__":unittest.main()
