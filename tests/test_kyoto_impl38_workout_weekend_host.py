"""Targeted same-root repair: existing workout roster reader accepts both exact weekend days."""
import json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_impl33_workout_runtime import official
from diagnostics.kyoto_g03_all_races import acquire_all
from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec
from diagnostics.jra_market_integrity_gate import normal_sales_open
from diagnostics.jra_market_source_chain import SourceChainError
from datetime import date
from tests.test_kyoto_g03_all_races import card,meeting,source_race,PARENT

class WorkoutWeekendHost(unittest.TestCase):
    def test_both_days_existing_roster_bridge(self):
        for day in ("20261128","20261129"):
            with self.subTest(day=day), tempfile.TemporaryDirectory() as td:
                root=Path(td)
                src=root/"capture";saved=root/"saved";saved.mkdir()
                acquire_all(day=day,root=src,meeting_raw=meeting().replace(b"20261121",day.encode()),
                    meeting_url=PARENT.replace("jra.jp","www.jra.go.jp"),
                    fetch=lambda url:card(count=3,race=source_race(url),day=day),
                    captured_at_utc=lambda:day[:4]+"-"+day[4:6]+"-"+day[6:]+"T00:00:00Z",allowed=True)
                for f in src.iterdir():
                    f.rename(saved/(f.name if f.name in ("official_meeting.html","g03_receipt.json") else "g03_"+f.name))
                got=official(saved,day,101)
                self.assertEqual(set(got),set(range(1,13)))
                self.assertTrue(all(len(x["roster"])==3 for x in got.values()))
                # The original source SHA remains a hard gate.
                p=saved/"g03_official_racecard_01.html"
                p.write_bytes(p.read_bytes()+b"tamper")
                self.assertNotIn(1,official(saved,day,101))
    def test_old_day_other_host_and_wrong_day_still_rejected(self):
        for day,host,token_day in (("20261121","www.jra.go.jp","20261121"),("20261128","www.jra.go.jp.example.org","20261128"),("20261128","www.jra.go.jp","20261129")):
            d=date.fromisoformat(day[:4]+"-"+day[4:6]+"-"+day[6:])
            spec=ObservedRaceSpec(day,1,d.isoformat()+"_KYOTO_1R","京都",
                f"https://{host}/JRADB/accessD.html?CNAME=pw01dde01082026050101{token_day}%2F13","",normal_sales_open(d).isoformat())
            with self.assertRaises(SourceChainError):spec.validate(require_channels=("PC",))
if __name__=="__main__":unittest.main()
