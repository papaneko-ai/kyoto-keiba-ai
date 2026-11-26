import io,json,unittest
from diagnostics.kyoto_impl30_collector_selection import choose,verify_preflight,PREFLIGHT
A="a"*40;B="b"*40;REPO="papaneko-ai/kyoto-keiba-ai"
class TestSelection(unittest.TestCase):
    def test_saturday_ignores_override(self):
        self.assertEqual(choose("20261128",A,B,lambda x:self.fail("unnecessary API")),(A,"BASELINE"))
    def test_sunday_valid_override(self):
        self.assertEqual(choose("20261129",A,B,lambda x:x==B),(B,"EXACT_PREFLIGHT_VERIFIED_OVERRIDE"))
    def test_unverified_candidate_preserves_opportunity(self):
        self.assertEqual(choose("20261129",A,B,lambda x:False),(A,"OVERRIDE_NOT_VERIFIED_BASELINE_RETAINED"))
    def test_api_error_preserves_opportunity(self):
        def offline(x):raise TimeoutError()
        self.assertEqual(choose("20261129",A,B,offline),(A,"PREFLIGHT_UNAVAILABLE_BASELINE_RETAINED"))
    def test_invalid_override_never_interpolated(self):
        self.assertEqual(choose("20261129",A,"x\nBAD=1",lambda x:self.fail("invalid override checked")),(A,"OVERRIDE_INVALID_BASELINE_RETAINED"))
    def test_bad_baseline_or_day_rejected(self):
        for day,sha in (("20261122",A),("20261129","main")):
            with self.assertRaises(ValueError):choose(day,sha,B,lambda x:True)
    def test_exact_preflight_run_identity(self):
        good={"head_sha":B,"status":"completed","conclusion":"success","event":"push",
              "head_repository":{"full_name":REPO},"path":".github/workflows/"+PREFLIGHT}
        def check(row):
            def fetch(request,timeout):
                self.assertIn("head_sha="+B,request.full_url);self.assertEqual(timeout,8)
                return io.BytesIO(json.dumps({"workflow_runs":[row]}).encode())
            return verify_preflight(B,REPO,"dummy",fetch)
        self.assertTrue(check(good))
        for key,value in (("head_sha",A),("status","in_progress"),("conclusion","failure"),
                          ("event","pull_request"),("head_repository",{"full_name":"other/repo"}),
                          ("path",".github/workflows/old.yml")):
            with self.subTest(key=key):self.assertFalse(check({**good,key:value}))
if __name__=="__main__":unittest.main()
