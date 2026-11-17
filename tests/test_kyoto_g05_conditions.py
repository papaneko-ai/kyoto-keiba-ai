"""G05 12-race source-bound conditions with missingness and adversarial tests."""
import json,shutil,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_g03_all_races import acquire_all
from diagnostics.kyoto_g05_conditions import compile_saved,G05Rejected
from tests.test_kyoto_g03_all_races import DAY,PARENT,meeting,card,source_race

def source(race,with_conditions=True):
    raw=card(count=4,race=race)
    if with_conditions:
        addition='<section class="race-condition">天候：晴 芝：良 ダート：稍重</section>'
        raw=raw.replace(b"<html>",("<html>"+addition).encode("cp932"))
        raw=raw.replace(b'<th class="horse">', '<th class="bodyweight">馬体重</th><th class="horse">'.encode("cp932"))
        for number in range(1,5):
            cell=f'<td class="bodyweight">{440+number}(+2)</td>'.encode("cp932")
            anchor=f'<td class="horse"><a href="/JRADB/accessU.html?CNAME=horse{number}">'.encode("cp932")
            raw=raw.replace(anchor,cell+anchor)
    return raw

class G05Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"saved";self.root.mkdir()
        original=Path(t.name)/"source"
        report=acquire_all(day=DAY,root=original,meeting_raw=meeting(),meeting_url=PARENT,
            fetch=lambda url:source(source_race(url)),captured_at_utc=lambda:"2026-11-21T00:00:00Z",allowed=True)
        self.assertTrue(report["complete"])
        for p in original.iterdir():p.rename(self.root/("g03_"+p.name))
        shutil.copyfile(self.root/"g03_official_meeting.html",self.root/"official_meeting.html")
        (self.root/"g03_receipt.json").write_text(json.dumps(report),encoding="utf8")
    def test_12r_horse_mass_weather_and_going_proven_from_same_source(self):
        r=compile_saved(self.root,day=DAY)
        self.assertEqual(len(r["races"]),12)
        self.assertEqual(r["observed_field_values"],12*(3+4*2))
        for race in range(1,13):
            item=r["races"][str(race)]
            self.assertEqual(item["track"]["weather"]["value"],"晴")
            self.assertEqual(item["track"]["turf_going"]["value"],"良")
            self.assertEqual(item["track"]["dirt_going"]["value"],"稍重")
            for h in item["horses"].values():
                self.assertEqual(h["body_weight_change_kg"]["value"],2)
                self.assertIsNone(h["workout"]["value"])
                self.assertEqual(h["workout"]["missing_reason"],"SOURCE_NOT_INDEPENDENTLY_OBSERVED")
                self.assertFalse(h["body_weight_kg"]["publication_time_independently_verified"])
        self.assertFalse(r["prediction_ready"])
    def test_not_in_original_is_missing_never_zero_or_fabricated(self):
        report=json.loads((self.root/"g03_receipt.json").read_text())
        for race in range(1,13):
            path=self.root/f"g03_official_racecard_{race:02d}.html"
            raw=source(race,with_conditions=False)
            path.write_bytes(raw)
            import hashlib
            h=hashlib.sha256(raw).hexdigest()
            report["races"][str(race)]["original_sha256"]=h
        (self.root/"g03_receipt.json").write_text(json.dumps(report))
        result=compile_saved(self.root,day=DAY)
        self.assertEqual(result["observed_field_values"],0)
        self.assertEqual(result["races"]["1"]["horses"]["1"]["body_weight_kg"]["state"],"MISSING")
        self.assertEqual(result["races"]["1"]["track"]["weather"]["missing_reason"],"NOT_OBSERVED_IN_ARCHIVED_OFFICIAL_SOURCE")
    def test_tampered_original_rejected(self):
        path=self.root/"g03_official_racecard_06.html"
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaisesRegex(Exception,"sha_mismatch"):
            compile_saved(self.root,day=DAY)
    def test_post_start_capture_rejected(self):
        report=json.loads((self.root/"g03_receipt.json").read_text())
        report["races"]["2"]["captured_at_utc"]="2026-11-22T15:00:00+00:00"
        (self.root/"g03_receipt.json").write_text(json.dumps(report))
        with self.assertRaisesRegex(G05Rejected,"post_start_source"):
            compile_saved(self.root,day=DAY)
    def test_cutoff_rejects_later_original(self):
        with self.assertRaisesRegex(G05Rejected,"source_after_requested_cutoff"):
            compile_saved(self.root,day=DAY,expected_cutoff_utc="2026-11-20T23:00:00Z")
    def test_duplicate_run_rejected(self):
        compile_saved(self.root,day=DAY)
        with self.assertRaisesRegex(G05Rejected,"receipt_already_exists"):
            compile_saved(self.root,day=DAY)

if __name__=="__main__":unittest.main()
