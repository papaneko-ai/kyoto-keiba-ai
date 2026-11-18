import unittest
from diagnostics.kyoto_g06_gap_recovery_plan import plan_gap_recovery
T="2026-11-21T01:00:00Z"; END="2026-11-21T05:00:00Z"
PROOF={"channel":"PC","sha256":"a"*64,"captured_at_utc":T}
def plan(**kw):
    a=dict(race_id="2026-11-21_KYOTO_01R",
      verified_market_receipts={"quinella":PROOF,"bracket_quinella":None},
      official_links={"PC":True,"SP":False},attempt_history=[],
      now_utc=T,cutoff_utc=END)
    a.update(kw)
    return plan_gap_recovery(**a)
class Tests(unittest.TestCase):
    def test_keep_verified(self):
        self.assertEqual(plan()["items"]["quinella"]["next_actions"],[])
    def test_unobserved_sp_must_navigate(self):
        self.assertEqual(plan()["items"]["bracket_quinella"]["next_actions"][1]["action"],
                         "OBSERVE_INDEPENDENT_OFFICIAL_NAVIGATION")
    def test_transient_recovery(self):
        history=[dict(market="bracket_quinella",source="PC",result="TIMEOUT",at_utc=T)]
        self.assertEqual(plan(attempt_history=history)["items"]["bracket_quinella"]["next_actions"][0]["action"],
                         "RETRY_OBSERVED_MARKET_ONLY")
    def test_403_blocks_other_host(self):
        history=[dict(market="bracket_quinella",source="PC",result="HTTP_403",at_utc=T)]
        self.assertEqual(plan(attempt_history=history)["items"]["bracket_quinella"]["next_actions"],[])
    def test_403_on_other_market_still_blocks(self):
        history=[dict(market="quinella",source="PC",result="HTTP_403",at_utc=T)]
        self.assertEqual(plan(attempt_history=history)["items"]["bracket_quinella"]["next_actions"],[])
    def test_after_start_no_http(self):
        self.assertEqual(plan(now_utc=END)["items"]["bracket_quinella"]["next_actions"],[])
    def test_supplemental_requires_license(self):
        with self.assertRaises(ValueError):
            plan(approved_supplemental=[dict(id="x",observed_url="https://example.com",license_verified=False,automation_permitted=True)])
    def test_approved_supplemental_not_authorized_http(self):
        x=plan(approved_supplemental=[dict(id="x",observed_url="https://example.com",license_verified=True,automation_permitted=True)])
        self.assertEqual(x["network_requests"],0)
        self.assertTrue(x["items"]["bracket_quinella"]["next_actions"][-1]["not_equivalent_to_official"])
    def test_future_attempt_bad(self):
        with self.assertRaises(ValueError):
            plan(attempt_history=[dict(market="bracket_quinella",source="PC",result="TIMEOUT",at_utc="2026-11-22T00:00:00Z")])
    def test_unfrozen_quote_bad(self):
        with self.assertRaises(ValueError):
            plan(verified_market_receipts={"quinella":dict(PROOF,captured_at_utc=END),"bracket_quinella":None})
if __name__=="__main__":unittest.main()
