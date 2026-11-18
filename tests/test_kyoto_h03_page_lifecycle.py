import unittest
from diagnostics.kyoto_h03_page_lifecycle import classify,SPPageError
HEAD="2026年11月7日(土曜) 5回京都1日 1R "
def raw(content):
    return ("<html><title>出馬表</title><body>"+HEAD+content+"</body></html>").encode("cp932")
class TestLifecycle(unittest.TestCase):
    def test_real_observed_expiry_message(self):
        x=classify(raw("このレースの出馬表の掲載は終了しております。レース結果はこちらから。"),
                   race_day="20261107",race_number=1)
        self.assertEqual(x["state"],"EXPIRED_RACECARD_OFFICIAL_PAGE")
        self.assertFalse(x["prediction_ready"])
    def test_missing_table_not_marked_valid(self):
        x=classify(raw("公開中"),race_day="20261107",race_number=1)
        self.assertEqual(x["state"],"NO_VERIFIED_SP_ROSTER")
    def test_wrong_date_rejected(self):
        with self.assertRaises(SPPageError):
            classify(raw("このレースの出馬表の掲載は終了しております"),
                     race_day="20261121",race_number=1)
    def test_wrong_race_rejected(self):
        with self.assertRaises(SPPageError):
            classify(raw("このレースの出馬表の掲載は終了しております"),
                     race_day="20261107",race_number=2)
if __name__=="__main__":unittest.main()
