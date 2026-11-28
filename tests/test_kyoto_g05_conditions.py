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

    def test_cancelled_runner_and_other_races_keep_observed_weight_and_track(self):
        import hashlib
        from diagnostics.kyoto_g03_all_races import parse
        from diagnostics.kyoto_g05_conditions import _body_weights
        from diagnostics.kyoto_impl30_day_coverage import extract_slot
        report=json.loads((self.root/"g03_receipt.json").read_text())
        path=self.root/"g03_official_racecard_02.html"
        raw=path.read_bytes().replace(b'<td class="num">2</td>',
              '<td class="num"><span class="cap">取消</span></td>'.encode("cp932"))
        path.write_bytes(raw)
        row=report["races"]["2"]
        parsed=parse(raw,DAY,2,row["source_url"],row["captured_at_utc"])
        self.assertTrue(parsed["runners"][1]["cancelled"])
        row.update(original_sha256=hashlib.sha256(raw).hexdigest(),runners=parsed["runners"])
        if "original_bytes" in row:row["original_bytes"]=len(raw)
        (self.root/"g03_receipt.json").write_text(json.dumps(report))
        result=compile_saved(self.root,day=DAY)
        self.assertEqual(result["observed_field_values"],12*(3+4*2)-2)
        h=result["races"]["2"]["horses"]
        self.assertEqual(h["1"]["body_weight_kg"]["value"],441)
        self.assertEqual(h["3"]["body_weight_change_kg"]["value"],2)
        self.assertIsNone(h["2"]["body_weight_kg"]["value"])
        self.assertEqual(h["2"]["body_weight_kg"]["missing_reason"],"CANCELLED_RUNNER_WEIGHT_NOT_OBSERVED")
        self.assertEqual(result["races"]["3"]["horses"]["2"]["body_weight_kg"]["value"],442)
        slot=extract_slot(self.root,DAY,101)
        self.assertIn("body_weight_kg",slot["races"]["2"]["horses"]["1"])
        self.assertNotIn("body_weight_kg",slot["races"]["2"]["horses"]["2"])
        self.assertIn("body_weight_kg",slot["races"]["2"]["horses"]["3"])
        for expected,changed in (((),raw),((3,),raw),((2,),raw.replace(b'class="cap"',b'class="other"')),
            ((2,),raw.replace(b'<td class="num">3</td>',b'<td class="num">4</td>'))):
            with self.assertRaises(G05Rejected):_body_weights(changed,[1,2,3,4],expected_cancelled=expected)
    def test_weight_parser_failure_isolates_race_and_preserves_track(self):
        from unittest.mock import patch
        from diagnostics.kyoto_g05_conditions import _body_weights
        def isolated(raw,*args,**kwargs):
            if raw==source(2):raise G05Rejected("unverified_weight_number")
            return _body_weights(raw,*args,**kwargs)
        with patch("diagnostics.kyoto_g05_conditions._body_weights",side_effect=isolated):
            result=compile_saved(self.root,day=DAY)
        self.assertEqual(result["observed_field_values"],12*(3+4*2)-8)
        self.assertEqual(result["body_weight_extraction_errors"],{"2":"unverified_weight_number"})
        self.assertFalse(result["full_twelve_race_data_verified"])
        self.assertEqual(result["races"]["2"]["track"]["weather"]["value"],"晴")
        self.assertIsNone(result["races"]["2"]["horses"]["1"]["body_weight_kg"]["value"])
        self.assertEqual(result["races"]["3"]["horses"]["1"]["body_weight_kg"]["value"],441)

    def test_actual_nested_current_weight_and_track_layout(self):
        from diagnostics.kyoto_g05_conditions import _body_weights,_race_fields
        def raw(horses,header='馬名 馬体重',going='芝：良'):
            return (f'<html><div class="record_unit mt30"><div class="data"><div class="inner"><div class="cell date"><span>{going}</span></div></div></div></div>'
                    '<table><tr><th class="waku">枠</th><th class="num">馬番</th>'
                    f'<th class="horse">{header}</th><th class="jockey">斤量</th><th class="past">前走</th></tr>'
                    +''.join(f'<tr><td class="waku">1</td><td class="num">{number}</td><td class="horse"><div class="name_line">馬名</div><div class="result_line">{nested}</div></td><td class="jockey">56kg</td><td class="past"><div class="result_line"><div class="cell weight">499kg (+9)</div></div><div class="record_unit mt30"><div class="data"><div class="inner"><div class="cell date"><span>芝：不良</span></div></div></div></div></td></tr>' for number,nested in horses)
                    +'</table></html>').encode('cp932')
        current='<div class="cell weight">480kg <span class="transition">(+4)</span></div>'
        second='<div class="cell weight">501kg <span class="transition">(0)</span></div>'
        r=raw([('1',current),('2',second),('3','')])
        self.assertEqual(_body_weights(r,[1,2,3]),{1:(480,4),2:(501,0),3:(None,None)})
        self.assertEqual(_race_fields(r)['turf_going'],'良')
        self.assertIsNone(_race_fields(r)['dirt_going'])
        # Unpublished, ambiguous, cancelled, wrong heading and lookalike
        # previous-race markup must not produce a current weight.
        for altered in (current+second,'<div class="past">'+current+'</div>',''):
            a=raw([('1',altered),('2',second),('3','')])
            self.assertEqual(_body_weights(a,[1,2,3])[1],(None,None))
            self.assertEqual(_body_weights(a,[1,2,3])[2],(501,0))
        self.assertEqual(_body_weights(raw([('1',current),('2',second)],header='馬名'),[1,2]),{1:(None,None),2:(None,None)})
        cancel='<span class="cap">取消</span>'
        self.assertEqual(_body_weights(raw([('1',current),(cancel,current),('3',second)]),[1,2,3],expected_cancelled=[2]),{1:(480,4),2:(None,None),3:(501,0)})
        conflict=r.replace(b'<table>', '<section class="race-condition">芝：不良</section><table>'.encode("cp932"))
        self.assertIsNone(_race_fields(conflict)['turf_going'])
        self.assertIsNone(_race_fields(raw([('1',current),('2',second)],going='芝：未発表'))['turf_going'])

if __name__=="__main__":unittest.main()
