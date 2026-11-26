import unittest
from diagnostics.kyoto_impl33_hybrid_workout import parse_table_v3,preserve_partial
D='2026-11-22'
class Offline(unittest.TestCase):
    def test_caption_row(self):
        s='<h3>A</h3><table><tr><th colspan="4">A 11月18日(水) 評価Ａ</th></tr><tr><th>時期</th><th>場所</th><th>6F</th><th>1F</th></tr><tr><td>最終追切</td><td>京都芝(良)</td><td>79.0</td><td>11.3</td></tr></table>'
        a=parse_table_v3(s.encode(),'A',D);self.assertEqual(a['elapsed_s'],79);self.assertIsNone(parse_table_v3(s.encode(),'B',D))
    def test_partial_separate(self):
        s='<h3>A</h3><h4>最終追い切りまでの21日間</h4><table><tr><th>日</th><th>コース</th><th>本線</th><th>終い</th></tr><tr><td>11/10</td><td>栗東CW</td><td>4F 110.4</td><td></td></tr></table>'
        a=preserve_partial(s.encode(),D,{9:'A'},'2026-11-26T04:00:00Z');self.assertEqual(len(a),1);self.assertIsNone(a[0]['last_1f_s']);self.assertEqual(a[0]['elapsed_s'],110.4);self.assertEqual(a[0]['state'],'PARTIAL_OBSERVED_NOT_COMPLETE')
    def test_partial_future_or_wrong_horse(self):
        s='<h3>A</h3><h4>最終追い切りまでの21日間</h4><table><tr><th>日</th><th>コース</th><th>本線</th><th>終い</th></tr><tr><td>11/30</td><td>栗東CW</td><td>4F 110.4</td><td></td></tr></table>'
        self.assertEqual(preserve_partial(s.encode(),D,{9:'A'},'2026-11-26T04:00:00Z'),[])
if __name__=='__main__':unittest.main()
