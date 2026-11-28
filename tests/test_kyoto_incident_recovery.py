import json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_incident_recovery import inspect_source,run_identity,label,canonical,REPO
class IncidentRecoveryTests(unittest.TestCase):
 def put(self,root,name,value):
  (root/name).write_bytes(value if isinstance(value,bytes) else json.dumps(value).encode())
 def test_redirect_does_not_become_twelve_independent_causes(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"receipt.json",{"day":"20261128","error_code":"any_redirect_disallowed","error_class":"DiscoveryRejected"})
   v=inspect_source(r,"20261128","pc");i={x["stage"]:x for x in v["incidents"]}
   self.assertEqual(i["PC_ENTRY"]["code"],"any_redirect_disallowed")
   self.assertEqual(i["G03"]["blocked_by"],"PC_MEETING");self.assertEqual(i["G06"]["blocked_by"],"G03")
   self.assertIsNone(i["G05"]["blocked_by"]);self.assertFalse(i["PC_ENTRY"]["root_cause_closed"])
   self.assertEqual(canonical(v),canonical(inspect_source(r,"20261128","pc")))
 def test_observed_post_entry_and_zero_candidates(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"receipt.json",{"day":"20261128"})
   self.put(r,"sp_discovery_receipt.json",{"per_race_observed_navigation_candidates":{str(n):{"candidate_count":0} for n in range(1,13)},"attempts":[{"request_method":"GET"}]})
   self.put(r,"official_sp_discovery_1.html",'<a onclick="return doAction(\'/JRADB/accessD.html\',\'sw01dli00/80\')">出馬表</a>'.encode("utf8"))
   v=inspect_source(r,"20261128","sp")
   self.assertEqual(v["incidents"][0]["code"],"OBSERVED_POST_ENTRY_NO_POST_ATTEMPT")
   self.assertEqual(v["incidents"][1]["blocked_by"],"SP_DISCOVERY")
 def test_green_receipt_with_no_data_is_not_success(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"receipt.json",{"day":"20261129","state":"SOURCE_ONLY_FINISHED"})
   v=inspect_source(r,"20261129","postrace")
   self.assertFalse(v["source_claims_independently_certified"]);self.assertEqual(len(v["incidents"]),1)
 def test_no_secret_or_url_in_error(self):
  for x in ("https://private.invalid/key","A"*64,"token=private"):
   self.assertNotIn(x,label(x));self.assertTrue(label(x).startswith("UNCLASSIFIED_TEXT_SHA256_"))
 def test_wrong_day(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"receipt.json",{"day":"20261128"})
   with self.assertRaises(ValueError):inspect_source(r,"20261129","pc")
 def test_run_binding(self):
  r={"id":7,"head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","event":"workflow_dispatch","path":".github/workflows/kyoto-20261128-29-two-source-production-observer.yml","head_sha":"a"*40,"created_at":"2026-11-28T03:00:00Z"}
  self.assertEqual(run_identity(r,7)[1:],(("pc","sp"),("20261128",)))
  for k,v in (("head_branch","other"),("head_repository",{"full_name":"other/repo"}),("created_at","2026-11-30T00:00:00Z"),("path",".github/workflows/other.yml")):
   with self.assertRaises(ValueError):run_identity({**r,k:v},7)
if __name__=="__main__":unittest.main()
