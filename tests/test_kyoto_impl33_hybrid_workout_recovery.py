import unittest
from diagnostics.kyoto_impl33_hybrid_workout import parse_table_v2,parse_labeled_turf,parse_news_turf
D='2026-11-22'
class RecoveryFormats(unittest.TestCase):
    def test_inline_date_and_table(self):
        s='<h3>A</h3><div><b>A 11月18日(水)</b></div><table><tr><th>時期</th><th>場所</th><th>6F</th><th>1F</th></tr><tr><td>最終追切</td><td>京都芝(良)</td><td>79.0</td><td>11.3</td></tr></table>'
        a=parse_table_v2(s.encode(),'A',D);self.assertEqual(a['elapsed_s'],79)
    def test_explicit_labeled(self):
        s='<h3>A（セン3）</h3><p>最終追い切り：11月18日（水）京都芝（良）6F79.0－5F64.8－4F50.5－3F37.0－ラスト1F11.3</p>'
        a=parse_labeled_turf(s.encode(),'A',D);self.assertEqual(a['last_1f_s'],11.3)
    def test_news(self):
        s='<h1>マイルCS A</h1><article><p>追い切り＝11月18日、京都競馬場</p><p>Aは芝コースで6ハロン79秒0―11秒3</p></article>'
        a=parse_news_turf(s.encode(),'A',D);self.assertEqual(a['distance_m'],1200);self.assertIsNone(parse_news_turf(s.encode(),'B',D))
    def test_no_wrong_date(self):
        s='<h3>A</h3><p>最終追い切り：11月30日（水）京都芝（良）6F79.0－ラスト1F11.3</p>'
        self.assertIsNone(parse_labeled_turf(s.encode(),'A',D))
if __name__=='__main__':unittest.main()
