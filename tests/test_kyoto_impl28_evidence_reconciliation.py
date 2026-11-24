import unittest
from diagnostics.kyoto_impl28_evidence_reconciliation import reconcile

class TestReconciliation(unittest.TestCase):
    def test_no_false_structured_success(self):
        s={"day":"20261122","races":{"1":{"PC":{"state":"REAL_OFFICIAL_ORIGINAL_SAVED_ROSTER_NOT_AUTHENTICATED","identity_hints":{"same_day_kyoto_race_heading":True},"sha256":"a"*64}}}}
        result=reconcile(s,{"races":{"1":{"original_sha256":"b"*64,"state":"G03_ROSTER_AND_START_PARSED_FROM_ACTUAL_ORIGINAL"}}},[{}]*108)
        self.assertEqual(result["racecard_originals"],1)
        self.assertEqual(result["structured_rosters"],0)
        self.assertEqual(result["ledger_record_count"],108)
        self.assertEqual(len(result["unverified_families"]),7)

    def test_matching_sha_allows_roster(self):
        s={"day":"20261122","races":{"1":{"SP":{"state":"REAL_OFFICIAL_ORIGINAL_SAVED_ROSTER_NOT_AUTHENTICATED","identity_hints":{"same_day_kyoto_race_heading":True},"sha256":"c"*64}}}}
        result=reconcile(s,{"races":{"1":{"original_sha256":"c"*64,"state":"G03_ROSTER_AND_START_PARSED_FROM_ACTUAL_ORIGINAL"}}},[])
        self.assertEqual(result["structured_rosters"],1)
        self.assertEqual(result["races"]["1"]["channels"],["SP"])

    def test_wrong_day_rejected(self):
        with self.assertRaises(ValueError):
            reconcile({"day":"20261121"},{},[])
if __name__=="__main__":unittest.main()
