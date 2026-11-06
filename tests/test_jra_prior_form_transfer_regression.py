"""Offline regression tests for Japanese official JRA administrative transfer rows.

Synthetic HTML only; separate Actions job replays actual incident source by SHA.
"""
import unittest
from datetime import date,datetime,timezone
from html import escape
from diagnostics.jra_prior_form_offline import parse_horse_history,HEADERS

URL="https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103507/A5"
STAMP=datetime(2026,11,6,5,56,tzinfo=timezone.utc)
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)

def profile(*rows):
    headers="".join('<th class="%s">%s</th>' % (('date','place','dist')[i] if i<3 else 'other',h) for i,h in enumerate(HEADERS))
    rendered="".join("<tr>"+"".join("<td>"+escape(v)+"</td>" for v in vals)+"</tr>" for vals in rows)
    html='<html><body><span class="txt"><span class="opt">競走馬情報</span>グラニットピーク</span><h2>出走履歴</h2><table><tr>'+headers+'</tr>'+rendered+'</table></body></html>'
    return html.encode("cp932")

def race(day="2024年5月1日",course="ダ1800",rank="2"):
    return [day,"東京","1勝クラス",course,"良","12","2",rank,"騎手","56","490","1:52.0","0","勝馬"]

def transfer(day,label):
    return [day,"",label,"","","","","","","","","","",""]

def parse(raw):
    return parse_horse_history(raw,source_url=URL,fetched_at_utc=STAMP,prediction_cutoff_utc=CUTOFF,target_date=date(2026,11,7),expected_horse_name="グラニットピーク")

class TransferParsing(unittest.TestCase):
    def test_two_administrative_transfer_rows_are_not_race_finishes(self):
        d=parse(profile(race(),transfer("2024年3月13日","JRAへ転入"),
            transfer("2023年6月16日","JRAより転出")))
        self.assertEqual(d["history_rows_total"],3)
        self.assertEqual(d["prior_row_count"],1)
        self.assertEqual(d["invalid_rows"],[])
        self.assertEqual([e["event_type"] for e in d["administrative_events"]],
            ["JRA_TRANSFER_IN","JRA_TRANSFER_OUT"])
        self.assertEqual(len(d["excluded_rows"]),2)
        self.assertEqual(d["prior_rows"][0]["finish_position"],2)
    def test_unrecognized_blank_course_still_invalid(self):
        d=parse(profile(race(),transfer("2024年3月13日","不明な事項")))
        self.assertEqual(d["prior_row_count"],1)
        self.assertEqual(d["invalid_rows"],[{"row":2,"reason":"unparsed_surface_or_distance"}])
    def test_transfer_with_nonempty_finish_still_invalid(self):
        wrong=transfer("2024年3月13日","JRAへ転入")
        wrong[7]="1"
        d=parse(profile(wrong))
        self.assertEqual(d["prior_row_count"],0)
        self.assertEqual(d["administrative_events"],[])
        self.assertEqual(d["invalid_rows"],[{"row":1,"reason":"unparsed_surface_or_distance"}])
    def test_nonfinish_race_is_not_transfer(self):
        d=parse(profile(race(rank="中止")))
        self.assertEqual(len(d["nonfinish_rows"]),1)
        self.assertEqual(d["administrative_events"],[])
        self.assertEqual(d["invalid_rows"],[])
    def test_future_and_same_day_rows_excluded(self):
        d=parse(profile(race(day="2026年11月7日")))
        self.assertEqual(d["prior_row_count"],0)
        self.assertEqual(d["excluded_rows"][0]["reason"],"same_day_or_future_event")
    def test_duplicate_real_race_date_fails_closed(self):
        d=parse(profile(race(),race()))
        self.assertEqual(d["invalid_rows"],[{"row":2,"reason":"duplicate_race_date_unresolved"}])
if __name__=="__main__":unittest.main()
