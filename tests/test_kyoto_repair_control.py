import unittest
from diagnostics.kyoto_repair_control import recover_collection,RetryableFailure,PermanentFailure,page
P="actions/runs/123/artifacts?per_page=100"
def rows(n,start=1):return [{"id":i} for i in range(start,start+n)]
class RepairControlTests(unittest.TestCase):
 def test_incomplete_collection_auto_recovery(self):
  trace=[]
  def fetch(p):
   if "per_page=100" in p:return {"total_count":31,"artifacts":rows(30)}
   return {"total_count":31,"artifacts":rows(25) if p.endswith("page=1") else rows(6,26)}
  d=recover_collection(P,"artifacts",fetch=fetch,sleep=lambda _:None,trace=trace)
  self.assertEqual([r["id"] for r in d["artifacts"]],list(range(1,32)))
  self.assertEqual([x["state"] for x in trace],["REJECTED","COMPLETE"])
 def test_transient_auto_recovery(self):
  trace=[]
  def fetch(p):
   if "per_page=100" in p:raise RetryableFailure("api_timeout")
   return {"total_count":0,"artifacts":[]}
  self.assertEqual(recover_collection(P,"artifacts",fetch=fetch,sleep=lambda _:None,trace=trace)["total_count"],0)
  self.assertEqual(trace[0]["reason"],"api_timeout")
 def test_denied_never_retry(self):
  calls=[]
  def fetch(p):
   calls.append(p);raise PermanentFailure("http_403")
  with self.assertRaises(PermanentFailure):recover_collection(P,"artifacts",fetch=fetch,sleep=lambda _:None)
  self.assertEqual(len(calls),1)
  with self.assertRaises(PermanentFailure):page("https://evil.invalid/")
 def test_persistent_unknown_not_green(self):
  for bad in ({"total_count":2,"artifacts":[{"id":1},{"id":1}]},{"total_count":500,"artifacts":[]},{"total_count":2,"artifacts":[]}):
   with self.assertRaises(RetryableFailure):recover_collection(P,"artifacts",fetch=lambda _:bad,sleep=lambda _:None)
if __name__=="__main__":unittest.main()
