import unittest
from diagnostics.jra_odds_matrix_parser import parse_matrix,OddsMatrixError
def html(market,rows):
    title="馬連オッズ" if market=="quinella" else "枠連オッズ"
    css="umaren" if market=="quinella" else "waku"
    body="".join('<table class="basic narrow-xy '+css+'">'+s+'</table>' for s in rows)
    return ("<html><title>"+title+" JRA</title><body>"+body+"</body></html>").encode("cp932")
class MatrixTests(unittest.TestCase):
 def test_quinella_three(self):
  d=parse_matrix(html("quinella",["1 2 12.3 3 4.1","2 3 5.5"]),"quinella",expected_runners=3)
  self.assertEqual(d["pair_count"],3)
  self.assertFalse(d["pre_race_quote_accepted"])
 def test_bracket_three(self):
  d=parse_matrix(html("bracket_quinella",["1 7.2 2 4.1 3 6.5","2 4.4 3 11.0","3 5.0"]),"bracket_quinella")
  self.assertEqual(d["pair_count"],6)
 def test_wrong_market(self):
  with self.assertRaises(OddsMatrixError):parse_matrix(html("quinella",["1 2 4.5"]),"bracket_quinella")
 def test_incomplete(self):
  with self.assertRaises(OddsMatrixError):parse_matrix(html("quinella",["1 2 3.5","2 3 4.5"]),"quinella")
 def test_missing_price(self):
  with self.assertRaises(OddsMatrixError):parse_matrix(html("quinella",["1 2 3.5","2 3 --"]),"quinella")
 def test_wrong_expected_runner_count(self):
  with self.assertRaises(OddsMatrixError):parse_matrix(html("quinella",["1 2 3.5"]),"quinella",expected_runners=4)
 def test_1_0_is_valid_market_value(self):
  d=parse_matrix(html("quinella",["1 2 1.0"]),"quinella")
  self.assertEqual(d["pairs"][0]["odds"],"1.0")
if __name__=="__main__":unittest.main()
