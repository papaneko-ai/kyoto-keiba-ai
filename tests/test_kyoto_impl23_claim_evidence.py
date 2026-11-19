import unittest
from diagnostics.kyoto_g06_claim_evidence import summarize_claims
class Tests(unittest.TestCase):
    def test_not_configured_does_not_certify(self):
        x=summarize_claims([],day="20261121",slot=0)
        self.assertEqual(x["status"],"NO_G06_REMOTE_CLAIM_EVIDENCE")
        self.assertFalse(x["production_claim_certified"])
    def test_claim_commit_and_skip_still_need_independent_db_proof(self):
        x=summarize_claims([
            {"race":11,"claim_state":"ACQUIRED","claim_commit_state":"COMMITTED","both_markets_verified":True},
            {"race":12,"claim_state":"ACTIVE_LEASE","both_markets_verified":False}
        ],day="20261121",slot=0)
        self.assertEqual(x["counts"]["committed"],1)
        self.assertEqual(x["counts"]["skipped"],1)
        self.assertFalse(x["independent_remote_db_verified"])
        self.assertFalse(x["production_claim_certified"])
    def test_uncertain_coordinator_not_success(self):
        x=summarize_claims([{"race":10,"claim_state":"COORDINATOR_UNCONFIRMED"}],day="20261121",slot=0)
        self.assertEqual(x["counts"]["unconfirmed"],1)
        self.assertEqual(x["counts"]["committed"],0)
if __name__=="__main__":unittest.main()
