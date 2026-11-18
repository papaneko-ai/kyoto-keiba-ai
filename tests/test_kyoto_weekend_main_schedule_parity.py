"""Cross-check exact main production schedule against source opportunity guard.
Does not execute JRA HTTP or modify production.
"""
import re
import unittest
from pathlib import Path
from diagnostics.kyoto_weekend_retry_guard import evaluate, RetryGuardRejected, EARLY, PRIMARY, BACKUP
WF_PATH="production/.github/workflows/kyoto-20261121-22-two-source-production-observer.yml"
def schedule_from_file(root):
    text=(Path(root)/WF_PATH).read_text(encoding="utf-8")
    return re.findall(r"^\s*- cron: ['\"]([^'\"]+)['\"]",text,re.M)
class Tests(unittest.TestCase):
    def test_production_has_exactly_eight_slots(self):
        crons=schedule_from_file(Path(".."))
        self.assertEqual(len(crons),8)
        expected=sorted([*EARLY["20261121"],PRIMARY["20261121"],BACKUP["20261121"],
                         *EARLY["20261122"],PRIMARY["20261122"],BACKUP["20261122"]])
        self.assertEqual(sorted(crons),expected)
        for day in ("20261121","20261122"):
            for cron in (c for c in crons if f"{day[6:]} 11 *" in c):
                with self.subTest(day=day,cron=cron):
                    decision=evaluate(day,"101","schedule",cron,[],{})
                    self.assertIn("ALLOWED",decision)
    def test_wrong_day_schedule_must_be_rejected(self):
        for wrong_day,cron in (("20261122",EARLY["20261121"][0]),
                               ("20261121",EARLY["20261122"][0])):
            with self.assertRaises(RetryGuardRejected):
                evaluate(wrong_day,"101","schedule",cron,[],{})
    def test_arbitrary_cron_must_not_be_accepted(self):
        with self.assertRaises(RetryGuardRejected):
            evaluate("20261121","101","schedule","0 0 21 11 *",[],{})
if __name__=="__main__":unittest.main()
