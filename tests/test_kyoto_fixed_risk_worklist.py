import hashlib,json,unittest
from diagnostics.kyoto_fixed_risk_worklist import worklist,IDS
class FixedRiskTests(unittest.TestCase):
 def fixture(self):
  risks=[{"id":r,"severity":"BLOCKER" if i<13 else "OPEN","affected_surfaces":[],"required_evidence":"independent proof"} for i,r in enumerate(IDS)]
  raw=json.dumps({"risks":risks}).encode()
  return raw,hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
 def test_all_fixed_risks_with_distinct_obligations(self):
  raw,h=self.fixture()
  w=worklist({"workflows":{"two-source-production-observer.yml":{"index_complete":True,"runs":[{"id":1,"artifacts":{"pc":{"ids":[7]}}}]}},"coverage":{"all_reviewed_cells_present":True}},raw,h)
  self.assertEqual([r["id"] for r in w["rows"]],list(IDS))
  self.assertEqual(w["independently_closed"],0)
  self.assertEqual(len({r["specific_proof"] for r in w["rows"]}),25)
  self.assertEqual(w["rows"][0]["evidence"][0]["artifact_ids"],[7])
  self.assertTrue(all(not r["closed"] for r in w["rows"]))
 def test_register_mutation_rejected(self):
  raw,h=self.fixture()
  with self.assertRaises(ValueError):worklist({"workflows":{}},raw+b" ",h)
if __name__=="__main__":unittest.main()
