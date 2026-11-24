import json,shutil,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_g04_all_horse_profiles import capture
from diagnostics.kyoto_impl30_profile_resume import candidates,recover
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence,decrypt_evidence
from tests import test_kyoto_g04_all_horse_profiles as fixture

DAY=fixture.DAY
STAMP="2026-11-21T00:01:00Z"
LATER="2026-11-21T00:05:00Z"

class ResumeTests(fixture.AllHorseProfile):
    def previous(self):
        current=self.root.parent/"current"
        shutil.copytree(self.root,current)
        # Preserve one genuine failed GET and all other successful originals.
        def fetch(url):
            if "pw110101" in url:raise TimeoutError("missing first horse")
            return self.fetch(url)
        first=capture(root=self.root,day=DAY,fetch=fetch,clock=lambda:STAMP,allowed=True)
        self.assertEqual(first["profile_verified_count"],35)
        with patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY",DAY):
            encrypt_evidence(self.root,self.root.parent/"sealed",key_hex="aa"*32,
                repo="papaneko-ai/kyoto-keiba-ai",run_id="101")
            decrypt_evidence(self.root.parent/"sealed",self.root.parent/"restored",
                key_hex="aa"*32,repo="papaneko-ai/kyoto-keiba-ai",run_id="101")
        return current,self.root.parent/"restored"
    def test_resume_35_originals_and_fetch_only_one(self):
        current,prior=self.previous()
        cache=candidates(prior,DAY,101)
        self.assertEqual(len(cache),35)
        self.calls.clear()
        result=capture(root=current,day=DAY,fetch=self.fetch,clock=lambda:LATER,
                       allowed=True,prior_profiles=cache)
        self.assertEqual(result["profile_verified_count"],36)
        self.assertEqual(result["profiles_reused_count"],35)
        self.assertEqual(len(self.calls),1)
        for row in result["profiles"]:
            detail=json.loads((current/row["parsed_file"]).read_text(encoding="utf8"))
            self.assertEqual(detail["source_sha256"],row["source_sha256"])
            self.assertEqual(row["captured_at_utc"],"2026-11-21T00:01:00+00:00"
                             if row.get("reused_from_run_id") else "2026-11-21T00:05:00+00:00")
    def test_tampered_cache_wrong_name_and_post_start_not_reused(self):
        current,prior=self.previous()
        cache=candidates(prior,DAY,101)
        keys=list(cache)
        cache[keys[0]]["raw"]+=b"bad"
        cache[keys[1]]["name"]="different"
        cache[keys[2]]["captured_at_utc"]="2026-11-21T05:00:00Z"
        self.calls.clear()
        result=capture(root=current,day=DAY,fetch=self.fetch,clock=lambda:LATER,
                       allowed=True,prior_profiles=cache)
        self.assertEqual(result["profile_verified_count"],36)
        self.assertEqual(result["profiles_reused_count"],32)
        self.assertEqual(result["prior_profile_rejected_count"],3)
        self.assertEqual(len(self.calls),4)
    def test_github_outage_returns_empty_cache_not_veto(self):
        with patch("diagnostics.kyoto_impl30_profile_resume.subprocess.check_output",side_effect=OSError):
            cache,report=recover("20261128","papaneko-ai/kyoto-keiba-ai","aa"*32,103,
                                 deadline=100,monotonic=lambda:1)
        self.assertEqual(cache,{})
        self.assertTrue(report["errors"])
if __name__=="__main__":unittest.main()
