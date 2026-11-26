import unittest
from diagnostics.kyoto_impl33_hybrid_workout import parse_table,parse_turf_line,recover,record,classify_rejected
from test_kyoto_impl33_workout_binding import case
D='2026-11-22'
def html(s):return s.encode()
T='<h3>A</h3><p>A 11月18日(水) 評価A</p><table><tr><th>時期</th><th>場所</th><th>6F</th><th>1F</th></tr><tr><td>最終追切</td><td>京都芝(良)</td><td>79.0</td><td>11.3</td></tr></table><h3>B</h3>'
L='<h5>A</h5><p>11/18(水) 京都芝 79.0-64.8-50.5-37.0-11.3</p><h5>B</h5>'
class Hybrid(unittest.TestCase):
    def test_two_formats(self):
        a=parse_table(html(T),'A',D);b=parse_turf_line(html(L),'A',D);self.assertEqual(a,b);self.assertEqual(a['distance_m'],1200)
    def test_other_horse_not_bound(self):
        self.assertIsNone(parse_table(html(T),'B',D));self.assertIsNone(parse_turf_line(html(L),'B',D))
    def test_invalid_date_and_course(self):
        self.assertIsNone(record(D,11,30,'KYOTO_TURF',6,'79.0','11.3'));self.assertIsNone(record(D,11,18,'UNKNOWN',6,'79.0','11.3'))
    def test_agreement_preserves_primary(self):
        a=parse_table(html(T),'A',D);p={1:[],2:[{'keep':True}]};obs={1:[{'provider':'x','record':a},{'provider':'y','record':a}]}
        r,log=recover(p,{1:'A',2:'B'},obs);self.assertEqual(r[1],[a]);self.assertEqual(r[2],p[2]);self.assertEqual(p[1],[]);self.assertEqual(log[0]['status'],'CORROBORATED')
    def test_same_provider_not_two(self):
        a=parse_table(html(T),'A',D);r,l=recover({1:[]},{1:'A'},{1:[{'provider':'x','record':a}]*2});self.assertEqual(r[1],[])
    def test_conflict_no_overwrite(self):
        a=parse_table(html(T),'A',D);r,l=recover({1:[]},{1:'A'},{1:[{'provider':'x','record':a},{'provider':'y','record':dict(a,elapsed_s=80)}]});self.assertEqual(r[1],[]);self.assertEqual(l[0]['status'],'CONFLICT')
    def test_rejection_reason(self):
        raw,_,_,_,stamp,roster,_=case(bad_date=True);r=classify_rejected(raw,D,roster,stamp);self.assertEqual([i['reason'] for i in r],['OUTSIDE_DATE_WINDOW']*2)
if __name__=='__main__':unittest.main()
