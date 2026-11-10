import unittest
from diagnostics.p7_approved_evo_capability_screen import screen_capabilities,CapabilityRejected,EXPECTED,REQUIRED

class ApprovedEvolutionTests(unittest.TestCase):
 def test_all_eight_approved_capabilities_not_hyp_features(self):
  r=screen_capabilities({})
  self.assertEqual([x["id"] for x in r["capabilities"]],list(EXPECTED))
  self.assertEqual(r["research_hypothesis_count"],0)
  self.assertTrue(all(x["status"].startswith("BLOCKED") for x in r["capabilities"]))
  self.assertFalse(r["independent_evolution_certified"])
  self.assertFalse(r["auto_promote"])
  self.assertFalse(r["prediction_ready"])
  self.assertFalse(r["real_bet_authorized"])
 def test_eight_specific_candidate_schemas_and_replay(self):
  obs={eid:{k:1 for k in REQUIRED[eid]} for eid in EXPECTED}
  r=screen_capabilities(obs)
  self.assertEqual(r["research_hypothesis_count"],8)
  self.assertTrue(all(x["status"]=="RESEARCH_HYPOTHESIS_ONLY" for x in r["capabilities"]))
  self.assertEqual(r,screen_capabilities(obs))
  self.assertFalse(r["independent_evolution_certified"])
 def test_partial_is_blocked_and_unknown_ids_rejected(self):
  r=screen_capabilities({"EVO-03":{"paired_races":3}})
  self.assertEqual(r["capabilities"][2]["status"],"BLOCKED_INCOMPLETE_RESEARCH_EVIDENCE")
  with self.assertRaises(CapabilityRejected):screen_capabilities({"HYP-01":{}})
  with self.assertRaises(CapabilityRejected):screen_capabilities({"EVO-01":{"unapproved":1}})
  with self.assertRaises(CapabilityRejected):screen_capabilities({"EVO-08":{"surprise_metric":None}})
if __name__=="__main__":unittest.main()
