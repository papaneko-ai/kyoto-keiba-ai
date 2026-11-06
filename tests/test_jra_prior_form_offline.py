"""Synthetic no-network tests. Real HTML regression is in local verification ZIP."""
import unittest
from datetime import date,datetime,timezone
from diagnostics.jra_prior_form_offline import parse_horse_history

H=('年月日','場','レース名','距離','馬場','頭数','人気','着順','騎手名','負担重量','馬体重','タイム','Rt','1着馬（2着馬）')
C=('date','course','race','dist','baba','num','pop','place','jockey','weight','h_weight','time','rate','horse')
def make_html():
    header=''.join('<th class="%s">%s</th>'%(a,b) for a,b in zip(C,H))
    def row(d,r):
        v=[d,'京都','2歳未勝利','ダ1400','重','16','1',str(r),'松山 弘平','56.0','422','1:24.1','','対戦馬']
        return '<tr>'+''.join('<td>%s</td>'%x for x in v)+'</tr>'
    html='<span class="txt"><span class="opt">競走馬情報</span>テスト馬<span class="name_en">Test</span></span><table><tr>'+header+'</tr>'+row('2026年10月31日',1)+row('2026年10月18日',3)+'</table>'
    return html.encode('cp932')

def run(**kwargs):
    p=dict(raw=make_html(),source_url='https://www.jra.go.jp/JRADB/accessU.html?CNAME=fixture',
           fetched_at_utc=datetime(2026,11,5,6,tzinfo=timezone.utc),
           prediction_cutoff_utc=datetime(2026,10,31,5,tzinfo=timezone.utc),
           target_date=date(2026,10,31),expected_horse_name='テスト馬')
    p.update(kwargs)
    return parse_horse_history(**p)

class PriorFormTest(unittest.TestCase):
    def test_result_date_excluded(self):
        r=run();self.assertEqual((r['history_rows_total'],r['prior_row_count'],len(r['excluded_rows'])),(2,1,1))
        self.assertEqual(r['excluded_rows'][0]['date'],'2026-10-31')
    def test_fail_closed_prediction(self):
        r=run();self.assertFalse(r['prediction_ready']);self.assertIsNone(r['jra_horse_id'])
        self.assertFalse(r['profile_captured_before_cutoff'])
    def test_deterministic(self):self.assertEqual(run(),run())
    def test_name_mismatch(self):
        with self.assertRaises(ValueError):run(expected_horse_name='別の馬')
    def test_untrusted_url(self):
        with self.assertRaises(ValueError):run(source_url='https://not-jra.example/JRADB/accessU.html')
    def test_same_cutoff_date_excluded(self):
        r=run(prediction_cutoff_utc=datetime(2026,10,18,4,tzinfo=timezone.utc))
        self.assertEqual(r['prior_row_count'],0)
    def test_wrong_table(self):
        with self.assertRaises(ValueError):run(raw=b'<html></html>',expected_horse_name=None)
    def test_naive_clock(self):
        with self.assertRaises(ValueError):run(prediction_cutoff_utc=datetime(2026,10,31,5))
    def test_finish_percentile(self):self.assertAlmostEqual(run()['prior_rows'][0]['finish_percentile'],13/15)
if __name__=='__main__':unittest.main()
