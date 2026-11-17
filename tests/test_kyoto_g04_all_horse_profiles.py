"""G04 pre-event all-race horse profiles: independent source, time and failure tests."""
import json,re,shutil,tempfile,unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from unittest.mock import patch
from diagnostics.kyoto_g03_all_races import acquire_all
from diagnostics.kyoto_g04_all_horse_profiles import capture, G04Rejected, _metadata, _observed_profile_code
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence
from tests.test_kyoto_g03_all_races import DAY,PARENT,meeting,card,source_race

def horse_card(race):
    raw=card(count=3,race=race)
    for n in range(1,4):
        raw=raw.replace(f"CNAME=horse{n}".encode(),
            f"CNAME=pw11{race:02d}{n:02d}%2FAA".encode())
    return raw

def profile(name):
    return (
        '<html><span class="txt"><span class="opt">競走馬情報</span>'+name+'</span>'
        '<dl><dt>性別</dt><dd>牝</dd></dl>'
        '<dl><dt>馬齢</dt><dd>2歳</dd></dl>'
        '<dl><dt>調教師名</dt><dd>テスト 調教師（栗東）</dd></dl>'
        '<dl><dt>父</dt><dd>父馬名</dd></dl>'
        '<h2>出走履歴</h2></html>'
    ).encode("cp932")

class AllHorseProfile(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        home=Path(temp.name)
        self.root=home/"pc";self.root.mkdir()
        stage=home/"g03"
        result=acquire_all(day=DAY,root=stage,meeting_raw=meeting(),
            meeting_url=PARENT,
            fetch=lambda url:horse_card(source_race(url)),
            captured_at_utc=lambda:"2026-11-21T00:00:00Z",allowed=True)
        self.assertTrue(result["complete"])
        for f in stage.iterdir():f.rename(self.root/("g03_"+f.name))
        shutil.copyfile(self.root/"g03_official_meeting.html",self.root/"official_meeting.html")
        (self.root/"g03_receipt.json").write_text(json.dumps(result),encoding="utf8")
        (self.root/"receipt.json").write_text('{"state":"OFFLINE_G03"}')
        self.calls=[]

    def fetch(self,url):
        self.calls.append(url)
        token=parse_qs(urlsplit(url).query)["CNAME"][0]
        number=int(token[-5:-3])
        return profile(f"競走馬{number}")

    def run_profile(self,clock=None,fetch=None):
        return capture(root=self.root,day=DAY,fetch=fetch or self.fetch,
            clock=clock or (lambda:"2026-11-21T00:01:00Z"),allowed=True)

    def test_36_profiles_all_12r_no_duplicate_and_encrypted(self):
        result=self.run_profile()
        self.assertEqual(result["expected_horses"],36)
        self.assertEqual(result["profile_verified_count"],36)
        self.assertTrue(result["all_profiles_parsed"])
        self.assertEqual(len(set(self.calls)),36)
        self.assertEqual(len(list(self.root.glob("g04_profile_r*_h*.html"))),36)
        self.assertEqual(len(list(self.root.glob("g04_profile_r*_h*_parsed.json"))),36)
        self.assertEqual(result["profiles"][0]["demographics"]["sex"],"牝")
        self.assertFalse(result["current_jockey_verified_for_all"])
        with patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY",DAY):
            sealed=encrypt_evidence(self.root,self.root.parent/"encrypted",
                key_hex="aa"*32,repo="papaneko-ai/kyoto-keiba-ai",run_id="1002")
        self.assertTrue(sealed["encrypted_only"])

    def test_network_failure_preserves_originals_and_fails_partial(self):
        injected=[False]
        def bad(url):
            if len(self.calls)==4 and not injected[0]:
                injected[0]=True
                raise TimeoutError("injected")
            return self.fetch(url)
        r=self.run_profile(fetch=bad)
        self.assertFalse(r["all_profiles_parsed"])
        self.assertEqual(r["profile_verified_count"],35)
        self.assertEqual(len(r["missing_profiles"]),1)
        self.assertTrue((self.root/"g04_profile_r01_h01.html").is_file())

    def test_response_after_start_is_not_promoted(self):
        current=iter(["2026-11-21T00:01:00Z","2026-11-21T15:00:00Z"]*36)
        result=self.run_profile(clock=lambda:next(current))
        self.assertEqual(result["profile_verified_count"],0)
        self.assertTrue((self.root/"g04_profile_r01_h01.html").is_file())
        self.assertEqual(result["profiles"][0]["failure_reason"],"response_after_race_start")

    def test_preflight_forged_g03_roster_prevents_all_network(self):
        r=json.loads((self.root/"g03_receipt.json").read_text())
        r["races"]["1"]["runners"][0]["name"]="偽造"
        (self.root/"g03_receipt.json").write_text(json.dumps(r))
        with self.assertRaisesRegex(G04Rejected,"g03_not_independently_verified"):
            self.run_profile()
        self.assertEqual(self.calls,[])

    def test_parse_identity_mismatch_preserves_raw_but_not_verified(self):
        r=self.run_profile(fetch=lambda url:profile("別の馬"))
        self.assertEqual(r["profile_verified_count"],0)
        self.assertTrue((self.root/"g04_profile_r01_h01.html").is_file())

    def test_profile_metadata_not_accepted_without_trainer(self):
        with self.assertRaisesRegex(G04Rejected,"trainer_unverified"):
            _metadata(profile("競走馬1").replace("調教師名".encode("cp932"),"不明".encode("cp932")),"競走馬1")

    def test_historical_all_148_official_profile_codes_unique(self):
        rows=json.loads(Path("docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json").read_text(encoding="utf8"))
        codes=[_observed_profile_code("https://jra.jp"+row["profile_href"]) for row in rows]
        self.assertEqual(len(codes),148)
        self.assertTrue(all(code and len(code)==10 and code.isdigit() for code in codes))
        self.assertEqual(len(set(codes)),148)
        self.assertIsNone(_observed_profile_code("https://jra.jp/JRADB/accessU.html?CNAME=pw1/AA"))
    def test_216_runner_capacity_does_not_hardcode_historical_148(self):
        import hashlib
        from tests.test_kyoto_g03_all_races import DAY,PARENT,meeting,card
        root=self.root.parent/"max_216";root.mkdir()
        stage=self.root.parent/"max_stage"
        def full_card(url):
            race=source_race(url)
            html=card(count=18,race=race)
            for n in range(18,0,-1):
                html=html.replace(f"CNAME=horse{n}".encode(),f"CNAME=pw22{race:02d}{n:02d}%2FAA".encode())
            return html
        proof=acquire_all(day=DAY,root=stage,meeting_raw=meeting(),meeting_url=PARENT,
            fetch=full_card,captured_at_utc=lambda:"2026-11-21T00:00:00Z",allowed=True)
        self.assertTrue(proof["complete"])
        for file in stage.iterdir():file.rename(root/("g03_"+file.name))
        shutil.copyfile(root/"g03_official_meeting.html",root/"official_meeting.html")
        (root/"g03_receipt.json").write_text(json.dumps(proof),encoding="utf8")
        result=capture(root=root,day=DAY,fetch=lambda url:profile(f"競走馬{int(parse_qs(urlsplit(url).query)['CNAME'][0][-5:-3])}"),
            clock=lambda:"2026-11-21T00:01:00Z",allowed=True)
        self.assertEqual(result["expected_horses"],216)
        self.assertEqual(result["profile_verified_count"],216)
        self.assertTrue(result["all_profiles_parsed"])
        self.assertFalse(result["current_jockey_verified_for_all"])
    def test_no_permission_no_http(self):
        with self.assertRaisesRegex(G04Rejected,"not_authorized"):
            capture(root=self.root,day=DAY,fetch=self.fetch,
                clock=lambda:"2026-11-21T00:00:00Z",allowed=False)
        self.assertEqual(self.calls,[])

if __name__=="__main__":unittest.main()
