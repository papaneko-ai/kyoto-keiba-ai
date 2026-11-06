import unittest
from datetime import datetime
from pathlib import Path
from diagnostics.parse_jra_result_roster import extract_result_roster

SOURCE="https://www.jra.go.jp/JRADB/accessD.html"
class TestJRAResultRoster(unittest.TestCase):
    def test_synthetic(self):
        html=("<table><tr><th class='horse'>馬名</th><th class='num'>馬番</th>"
              "<th class='waku'>枠</th><th class='place'>着順</th></tr>"
              "<tr><td class='place'>1</td><td class='waku'><img alt='枠3赤'></td>"
              "<td class='num'>5</td><td class='horse'><a href='/JRADB/accessU.html?CNAME=token01'>マルモリマイベスト</a></td></tr></table>")
        result=extract_result_roster(html.encode('cp932'),SOURCE)
        self.assertEqual((result['race_count'],result['horse_rows'],result['profile_links']),(1,1,1))
        self.assertEqual((result['races'][0]['rows'][0]['horse_number'],result['races'][0]['rows'][0]['frame_number']),(5,3))
        self.assertIsNone(result['races'][0]['rows'][0]['jra_horse_id'])
        self.assertFalse(result['ready_for_prediction'])
    def test_untrusted_url(self):
        with self.assertRaises(ValueError):
            extract_result_roster(b'abc',"https://example.org")
if __name__=="__main__":unittest.main()
