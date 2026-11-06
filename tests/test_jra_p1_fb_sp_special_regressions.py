import unittest
from diagnostics.jra_p1_sp_profile_offline import parse
def document(entries,horse="試験馬"):
    rows="".join("<tr><td>"+l+"</td><td>"+r+"</td></tr>" for l,r in entries)
    return ('<html><body><h1>'+horse+'</h1><table><tr><th>出走レース</th><th>着順 / 人気</th></tr>'+rows+'</table></body></html>').encode("cp932")
RACE="2026年7月26日 京都 障害レース 障芝3000 良 10頭 先着馬"
TRANSFER="2024年3月13日 JRAへ転入"
class SPHistorySafety(unittest.TestCase):
    def test_exact_transfer_held_separately(self):
        d=parse(document([(TRANSFER,""),(RACE,"2着 3人気")]),"試験馬")
        self.assertEqual(d["invalid_rows"],[])
        self.assertEqual(len(d["administrative_events"]),1)
        self.assertEqual(d["administrative_events"][0]["event_type"],"JRA_TRANSFER_IN")
        self.assertEqual(d["prior_rows"][0]["surface"],"障芝")
        self.assertEqual(len(d["prior_rows"]),1)
    def test_transfer_with_finish_is_not_silent(self):
        d=parse(document([(TRANSFER,"1着 1人気")]),"試験馬")
        self.assertEqual(len(d["administrative_events"]),0)
        self.assertEqual(d["invalid_rows"][0]["reason"],"sp_history_left_unparsed")
    def test_other_admin_event_is_not_a_race(self):
        d=parse(document([("2024年3月13日 不明事項","")]),"試験馬")
        self.assertEqual(len(d["administrative_events"]),0)
        self.assertTrue(d["invalid_rows"])
    def test_date_that_does_not_exist_is_invalid(self):
        d=parse(document([("2025年2月30日 京都 障害 障芝3000 良 10頭","2着 3人気")]),"試験馬")
        self.assertEqual(d["invalid_rows"][0]["reason"],"sp_invalid_date")
    def test_finish_exceeding_field_is_invalid(self):
        d=parse(document([(RACE,"11着 3人気")]),"試験馬")
        self.assertEqual(d["invalid_rows"][0]["reason"],"sp_rank_out_of_range")
    def test_nonfinish_is_excluded(self):
        d=parse(document([(RACE,"中止")]),"試験馬")
        self.assertEqual(len(d["nonfinish_rows"]),1)
        self.assertEqual(d["prior_rows"],[])
    def test_wrong_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"horse_name_missing"):
            parse(document([(RACE,"2着 3人気")]),"別馬")
if __name__=="__main__":unittest.main()
