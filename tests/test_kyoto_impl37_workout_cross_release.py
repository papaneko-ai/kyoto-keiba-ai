"""Offline cross-release compatibility regression, no external network."""
import json, shutil, tempfile, unittest
from pathlib import Path
from unittest.mock import Mock, patch
from diagnostics.kyoto_impl33_workout_runtime import gather_official, OBSERVER, AUXILIARY, REPO
from diagnostics.kyoto_g03_all_races import acquire_all
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence
import diagnostics.kyoto_nov15_encrypted_evidence as crypto
from tests.test_kyoto_g03_all_races import card, meeting, source_race, PARENT

DAY = "20261129"
PARENT_NEW = PARENT.replace("jra.jp", "www.jra.go.jp")
KEY = b"a" * 32

class CrossReleaseWorkout(unittest.TestCase):
    def test_modern_archive_and_cancelled_roster(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "raw"
            saved = root / "saved"
            saved.mkdir()
            def source(url):
                race = source_race(url)
                data = card(count=3, race=race, day=DAY)
                if race == 12:
                    data = data.replace(b'<td class="num">2</td>', '<td class="num"><span class="cap">取消</span></td>'.encode("cp932"))
                return data
            receipt = acquire_all(day=DAY, root=raw, meeting_raw=meeting().replace(b"20261121", DAY.encode()),
                meeting_url=PARENT_NEW, fetch=source, captured_at_utc=lambda:"2026-11-29T00:00:00Z", allowed=True)
            self.assertTrue(receipt["complete"], receipt)
            self.assertTrue(receipt["races"]["12"]["runners"][1]["cancelled"])
            for f in raw.iterdir():
                f.rename(saved / (f.name if f.name in ("official_meeting.html","g03_receipt.json") else "g03_"+f.name))
            (saved/"receipt.json").write_text(json.dumps({"day":DAY}))
            (saved/"official_pc_navigation_home.html").write_bytes(b"synthetic official home")
            cipher = root/"cipher"
            with patch.object(crypto, "DAY", DAY):
                encrypt_evidence(saved,cipher,key_hex=KEY.hex(),repo=REPO,run_id="101")
            def api(endpoint):
                rows=[{"id":101,"status":"completed","head_branch":"main","head_repository":{"full_name":REPO},
                       "path":".github/workflows/"+OBSERVER,"event":"workflow_dispatch","created_at":"2026-11-29T00:15:00Z"}] if OBSERVER in endpoint else []
                return {"total_count":len(rows),"workflow_runs":rows}
            def download(rid,name,dest):
                self.assertEqual((rid,name),(101,"kyoto-pc-101-20261129"))
                for f in cipher.iterdir():
                    shutil.copyfile(f,dest/f.name)
            b=Mock();b.api.side_effect=api;b.download.side_effect=download
            with patch.object(crypto,"DAY",DAY):
                got,conflicts,issues=gather_official(DAY,KEY,b,aux_budget_factory=lambda:b)
                self.assertEqual(len(got),12,issues)
                self.assertFalse(conflicts)
                self.assertFalse(issues)
                self.assertEqual(got[12]["roster"][2],"競走馬2")
                wrong,_,issues=gather_official(DAY,b"b"*32,b,aux_budget_factory=lambda:b)
                self.assertEqual(wrong,{})
                self.assertTrue(issues)
            # Explicit negative: never broaden to arbitrary archive members.
            (saved/"untrusted.bin").write_bytes(b"x")
            with patch.object(crypto,"DAY",DAY), self.assertRaises(crypto.EvidenceCryptoRejected):
                encrypt_evidence(saved,root/"bad",key_hex=KEY.hex(),repo=REPO,run_id="101")
if __name__=="__main__":unittest.main()
