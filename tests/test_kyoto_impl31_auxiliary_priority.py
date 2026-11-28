import tempfile, unittest
from pathlib import Path
from datetime import datetime,timezone
from diagnostics.kyoto_impl30_auxiliary_refresh import collect,SOURCE
from diagnostics.kyoto_g05_official_track import KYOTO_TRACK_PAGE,parse_kyoto_track
from diagnostics.kyoto_impl30_day_coverage import extract_slot,combine,proof
from tests.test_kyoto_g03_all_races import card,meeting,source_race
from tests.test_kyoto_g05_official_track import html
DAY='20261128'; STAMP='2026-11-28T04:00:00Z'
PARENT='https://jra.jp/JRADB/accessD.html?CNAME=pw01meeting20261128%2FAA'
TABLE='<table><caption>ゴール前と4コーナーの含水率</caption><tr><th></th><th>ゴール前</th><th>4コーナー</th></tr><tr><th>芝</th><td>10.1</td><td>9.2</td></tr><tr><th>ダート</th><td>7.4</td><td>7.1</td></tr></table>'
RAW=html(DAY).replace(b'</main>',TABLE.encode()+b'</main>')
class Aux(unittest.TestCase):
    def test_observed_priority_and_real_roster(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            if url==SOURCE:return f'<a href="{PARENT}">京都</a>'.encode('cp932')
            if url==PARENT:return meeting().replace(b'20261121',DAY.encode())
            if url==KYOTO_TRACK_PAGE:return RAW
            r=source_race(url);return card(race=r,day=DAY,time='発走 14:00')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'raw';r=collect(root,day=DAY,starts={1:'2026-11-28T04:40:00Z',4:'2026-11-28T04:10:00Z',3:'2026-11-28T03:00:00Z'},fetch=fetch,clock=lambda:STAMP)
            got=[source_race(u) for u in calls if u not in (SOURCE,PARENT,KYOTO_TRACK_PAGE)]
            self.assertEqual(got[:2],[4,1]);self.assertNotIn(3,got)
            self.assertIn(4,r['verified_races']);self.assertEqual(calls[-1],KYOTO_TRACK_PAGE)
            slot=extract_slot(root,DAY,1);self.assertIn('turf_moisture_finish_pct',slot['independent_track'])
            result=combine(DAY,[slot]);self.assertIn('turf_moisture_finish_pct',result['races']['4']['supplementary_track_observations'])
            self.assertFalse(result['full_data_acquisition_certified'])
    def test_both_days_observed_form_navigation_and_repair_evidence(self):
        from diagnostics.kyoto_nov29_public_forms import PC_HOME,PC_ENTRY
        for day in ("20261128","20261129"):
            form='<form id="new" method="post" action="/JRADB/accessD.html"><input type="hidden" name="cname"></form>'
            entry="pw01dli00/F3"
            token="pw01drl000820260508"+day+"/6B"
            home=(form+f'<button onclick="doAction (\'/JRADB/accessD.html\',\'{entry}\')">出馬表</button>').encode("cp932")
            sel=(form+f'<a href="javascript:doAction (\'/JRADB/accessD.html\',\'{token}\')">京都</a>').encode("cp932")
            urls={n:PC_ENTRY+f"?CNAME=pw01dde010820260508{n:02d}{day}/A1" for n in range(1,13)}
            meet="".join(f'<a href="{u}">出馬表</a>' for u in urls.values()).encode("cp932")
            calls=[]
            def fetch(url,*,token=None,referer=None):
                calls.append((url,token,referer))
                if url==PC_HOME:return home
                if token==entry:return sel
                if token is not None:return meet
                if url==KYOTO_TRACK_PAGE:return RAW
                race=next(n for n,u in urls.items() if u==url)
                return card(race=race,day=day,time="発走 14:00")
            with tempfile.TemporaryDirectory() as d:
                stamp=f"2026-11-{day[-2:]}T04:00:00Z"
                r=collect(Path(d)/"raw",day=day,starts={},fetch=fetch,clock=lambda:stamp,public_form_navigation=True)
                self.assertEqual(calls[:3],[(PC_HOME,None,None),(PC_ENTRY,entry,PC_HOME),(PC_ENTRY,token,PC_ENTRY)])
                self.assertEqual(len(r["adaptive_navigation_repairs"]),2)
                self.assertEqual(r["verified_races"],list(range(1,13)))
                slot=extract_slot(Path(d)/"raw",day,101)
                self.assertEqual(set(slot["races"]),{str(i) for i in range(1,13)})
                totals=combine(day,[slot])["totals"]
                self.assertEqual(totals["racecards"],12)
                self.assertEqual(totals["registered_horses_known"],96)
                self.assertEqual(calls[-1][0],KYOTO_TRACK_PAGE)
                self.assertFalse(r["prediction_ready"])
    def test_exact_moisture_table_only(self):
        r=parse_kyoto_track(RAW,DAY,KYOTO_TRACK_PAGE,STAMP)
        self.assertEqual([r[k] for k in ('turf_moisture_finish_pct','turf_moisture_turn4_pct','dirt_moisture_finish_pct','dirt_moisture_turn4_pct')],[10.1,9.2,7.4,7.1])
        for raw in (RAW.replace(TABLE.encode(),(TABLE+TABLE).encode()),RAW.replace(b'10.1',b'101'),RAW.replace('ゴール前と4コーナーの含水率'.encode(),'参考値'.encode())):
            self.assertIsNone(parse_kyoto_track(raw,DAY,KYOTO_TRACK_PAGE,STAMP)['turf_moisture_finish_pct'])
    def test_track_attempt_even_if_selector_fails(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            if url==KYOTO_TRACK_PAGE:return RAW
            raise TimeoutError()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'raw';r=collect(root,day=DAY,starts={},fetch=fetch,clock=lambda:STAMP)
            self.assertEqual(calls,[SOURCE,KYOTO_TRACK_PAGE]);self.assertEqual(r['verified_races'],[])
            self.assertIn('turf_moisture_finish_pct',extract_slot(root,DAY,1)['independent_track'])
if __name__=='__main__':unittest.main()
