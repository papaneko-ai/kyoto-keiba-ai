import unittest
from diagnostics.jra_p1_sp_profile_offline import parse
def document(entries,horse="試験馬"):
    rows="".join("<tr><td>"+l+"</td><td>"+r+"</td></tr>" for l,r in entries)
    return ('<html><body><div class="bameiSection">'+horse+'</div><table><tr><th>出走レース</th><th>着順 / 人気</th></tr>'+rows+'</table></body></html>').encode("cp932")
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
        with self.assertRaisesRegex(ValueError,"sp_profile_identity_anchor_missing_or_mismatch"):
            parse(document([(RACE,"2着 3人気")]),"別馬")

    def test_local_four_venues_and_missing_popularity(self):
        cases=[("園田",1400),("船橋",1500),("水沢",1600),("盛岡",1200)]
        entries=[(f"2023年1月{i+1}日 {venue} 地方レース ダ{dist} 良 11頭 先着馬","2着 1人気") for i,(venue,dist) in enumerate(cases)]
        entries[0]=(entries[0][0],"2着 1:29.1 502kg 騎手 56.0")
        d=parse(document(entries),"試験馬")
        self.assertEqual(d["invalid_rows"],[])
        self.assertEqual([x["jurisdiction"] for x in d["prior_rows"]],["LOCAL"]*4)
        self.assertEqual(d["prior_rows"][0]["popularity"],None)
        self.assertTrue(d["prior_rows"][0]["popularity_missing"])
        self.assertEqual(d["prior_rows"][1]["popularity"],1)
    def test_missing_popularity_not_allowed_on_jra_race(self):
        d=parse(document([("2023年1月1日 京都 通常レース ダ1400 良 11頭 先着馬","2着 1:29.1")]),"試験馬")
        self.assertEqual(d["invalid_rows"][0]["reason"],"sp_finish_unparsed")
    def test_unknown_local_venue_remains_invalid(self):
        d=parse(document([("2023年1月1日 未確認競馬場 レース ダ1400 良 11頭 先着馬","2着 1人気")]),"試験馬")
        self.assertTrue(d["invalid_rows"])
    def test_opponent_name_cannot_substitute_for_profile_identity(self):
        raw=document([("2023年1月1日 京都 レース ダ1400 良 11頭 別馬","2着 1人気")])
        with self.assertRaisesRegex(ValueError,"sp_profile_identity_anchor_missing_or_mismatch"):
            parse(raw,"別馬")
if __name__=="__main__":unittest.main()
