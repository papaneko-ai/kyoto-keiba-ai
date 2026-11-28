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
    def test_canonical_profile_origin_is_preserved_across_both_weekend_days(self):
        import tempfile
        from urllib.parse import urlsplit
        from diagnostics.kyoto_g03_all_races import acquire_all
        from tests.test_kyoto_g03_all_races import meeting,source_race
        for day in ("20261128","20261129"):
            with tempfile.TemporaryDirectory() as td:
                base=Path(td);root=base/"pc";root.mkdir();stage=base/"g03"
                iso=f"{day[:4]}-{day[4:6]}-{day[6:]}"
                day_label=f"{int(day[:4])}年{int(day[4:6])}月{int(day[6:])}日".encode("cp932")
                original_label="2026年11月21日".encode("cp932")
                parent=fixture.PARENT.replace("jra.jp","www.jra.go.jp")
                result=acquire_all(day=day,root=stage,meeting_raw=meeting().replace(b"20261121",day.encode()),
                    meeting_url=parent,fetch=lambda url:fixture.horse_card(source_race(url)).replace(original_label,day_label),
                    captured_at_utc=lambda:iso+"T00:00:00Z",allowed=True)
                self.assertTrue(result["complete"])
                for f in stage.iterdir():
                    f.rename(root/(f.name if f.name in ("official_meeting.html","g03_receipt.json") else "g03_"+f.name))
                (root/"receipt.json").write_text('{"state":"OFFLINE_G03"}')
                calls=[]
                def fetch(url):
                    self.assertEqual(urlsplit(url).hostname,"www.jra.go.jp")
                    calls.append(url)
                    return self.fetch(url)
                report=capture(root=root,day=day,fetch=fetch,clock=lambda:iso+"T00:01:00Z",allowed=True,allow_partial=True)
                self.assertEqual(report["profile_verified_count"],36)
                self.assertEqual(len(calls),36)
                cached=candidates(root,day,101)
                self.assertEqual(len(cached),36)
                self.assertTrue(all(urlsplit(item["url"]).hostname=="www.jra.go.jp" for item in cached.values()))
if __name__=="__main__":unittest.main()
