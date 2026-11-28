import io,json,unittest
from diagnostics.kyoto_impl30_collector_selection import choose,verify_preflight,PREFLIGHT,choose_deployed,DEPLOYED_RECEIPT
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
    def test_deployed_receipt_retains_verified_sunday_on_api_outage(self):
        d=DEPLOYED_RECEIPT
        def offline(x):raise TimeoutError()
        for failure,reason in ((offline,"PREFLIGHT_UNAVAILABLE_EXACT_DEPLOYED_RECEIPT"),
                               (lambda x:False,"PREFLIGHT_INDEX_NOT_CONFIRMED_EXACT_DEPLOYED_RECEIPT")):
            self.assertEqual(choose_deployed(d["day"],d["baseline"],d["override"],failure,repo=d["repo"]),(d["override"],reason))
        self.assertEqual(choose_deployed(d["day"],d["baseline"],d["override"],lambda x:True,repo=d["repo"]),(d["override"],"EXACT_PREFLIGHT_VERIFIED_OVERRIDE"))
    def test_deployed_receipt_does_not_authorize_other_release_or_repo(self):
        d=DEPLOYED_RECEIPT
        for day,base,override,repo in (
            ("20261128",d["baseline"],d["override"],d["repo"]),
            (d["day"],A,d["override"],d["repo"]),
            (d["day"],d["baseline"],B,d["repo"]),
            (d["day"],d["baseline"],d["override"],"other/repo"),
            (d["day"],d["baseline"],"not-a-sha",d["repo"])):
            with self.subTest(day=day,base=base,override=override,repo=repo):
                self.assertEqual(choose_deployed(day,base,override,lambda x:False,repo=repo),choose(day,base,override,lambda x:False))
    def test_production_entry_uses_receipt_and_matches_configured_pins(self):
        import os,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from diagnostics import kyoto_impl30_collector_selection as selector
        d=DEPLOYED_RECEIPT
        wf=(Path(__file__).resolve().parents[1]/".github/workflows/kyoto-20261128-29-two-source-production-observer.yml").read_text()
        self.assertIn("DEFAULT_COLLECTOR_SHA: '"+d["baseline"]+"'",wf)
        self.assertIn("SUNDAY_OVERRIDE_SHA: '"+d["override"]+"'",wf)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"out"
            env={"KYOTO_TARGET_DAY":d["day"],"DEFAULT_COLLECTOR_SHA":d["baseline"],"SUNDAY_OVERRIDE_SHA":d["override"],"GITHUB_REPOSITORY":d["repo"],"GITHUB_OUTPUT":str(out)}
            with patch.dict(os.environ,env),patch.object(selector,"verify_preflight",side_effect=TimeoutError):
                selector.main()
            self.assertEqual(out.read_text().splitlines(),["collector_sha="+d["override"],"selection_reason=PREFLIGHT_UNAVAILABLE_EXACT_DEPLOYED_RECEIPT"])
if __name__=="__main__":unittest.main()
