import unittest
from diagnostics.kyoto_operational_readiness import evaluate,OperationalError,GATES,REQUIRED

def receipt(gate):
 return {"gate_id":gate,"evidence_kind":REQUIRED[gate],
         "source_sha256":"a"*64,"verified_by":"external-independent-auditor",
         "verified_at_utc":"2026-11-10T08:00:00Z",
         "independent_receipt":"external-archive-ref",
         "race_day":"2026-11-08","source_reference":"source-ref",
         "pass":True}

class OperationalTests(unittest.TestCase):
 def test_empty_manifest_is_zero_verified_not_zero_code(self):
  x=evaluate([])
  self.assertEqual(x["verified_points"],0)
  self.assertEqual(sum(g["points"] for g in x["gates"]),100)
  self.assertIn("LOWER_BOUND",x["interpretation"])
 def test_ci_claims_alone_never_raise_score(self):
  self.assertEqual(evaluate([receipt(x[0]) for x in GATES])["verified_points"],0)
 def test_independent_verified_prerequisites_required(self):
  x=evaluate([receipt("MODEL_VALIDATION")],independent_verifier=lambda r:True)
  self.assertEqual(x["verified_points"],0)
  x=evaluate([receipt("LIVE_RACECARD"),receipt("PRE_RACE_FEATURES"),receipt("MODEL_VALIDATION")],
             independent_verifier=lambda r:True)
  self.assertEqual(x["verified_points"],40)
 def test_verifier_failure_never_credits(self):
  x=evaluate([receipt("LIVE_RACECARD")],independent_verifier=lambda r:False)
  self.assertEqual(x["verified_points"],0)
 def test_full_chain_only_independently_verified(self):
  x=evaluate([receipt(g[0]) for g in GATES],independent_verifier=lambda r:True)
  self.assertEqual(x["verified_points"],100)
 def test_duplicate_and_forged_rejected(self):
  with self.assertRaisesRegex(OperationalError,"unknown_or_duplicate_gate"):
   evaluate([receipt("LIVE_RACECARD")]*2)
  r=receipt("LIVE_RACECARD");r["source_sha256"]="bad"
  with self.assertRaisesRegex(OperationalError,"invalid_source_hash"):
   evaluate([r])
  r=receipt("LIVE_RACECARD");r["evidence_kind"]="research_ci"
  with self.assertRaisesRegex(OperationalError,"wrong_evidence_type"):
   evaluate([r])
 def test_deterministic(self):
  self.assertEqual(evaluate([]),evaluate([]))

if __name__=="__main__":unittest.main()
