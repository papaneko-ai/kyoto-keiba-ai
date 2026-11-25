import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_impl32_fmea_adjudication import *
class Adjudication(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.collector=self.root/"collector";self.production=self.root/"production"
        self.sha="a"*40
        self.ledger={"schema":"kyoto_fmea_reverse_coverage_v1","risks":[{"id":x,"severity":"OPEN","remediated":False,"test_proven":False} for x in sorted(IDS)]}
        self.put(self.collector,LEDGER,json.dumps(self.ledger))
        def job(install):
            steps=[{"uses":"actions/setup-python@v5","with":{"python-version":PYTHON}}]
            if install:steps.append({"run":"python -m pip install --no-deps "+" ".join(f"{k}=={v}" for k,v in PACKAGES.items())})
            return {"steps":steps}
        for path,expected in WORKFLOWS.items():
            jobs={n:job(i) for n,i in expected.items()}
            if path.endswith("two-source-production-observer.yml"):
                jobs["select-collector"]["env"]={"DEFAULT_COLLECTOR_SHA":self.sha}
                for n in ("pc-originals-independent","sp-originals-independent"):jobs[n]["env"]={"COLLECTOR_SHA":"${{ needs.select-collector.outputs.collector_sha }}"}
            else:next(iter(jobs.values()))["steps"].insert(0,{"uses":"actions/checkout@v4","with":{"ref":self.sha}})
            self.put(self.production,path,json.dumps({"jobs":jobs}))
        self.put(self.collector,PREF,json.dumps({"jobs":{"offline-next-week":job(True)}}))
        self.run_doc={"id":1,"head_sha":self.sha,"repository":{"full_name":REPO},"head_repository":{"full_name":REPO},"path":PREF,"event":"push","status":"completed","conclusion":"success"}
        self.jobs={"total_count":1,"jobs":[{"id":2,"run_id":1,"name":"offline-next-week","status":"completed","conclusion":"success","steps":[{"name":n,"conclusion":"success"} for n in ("Run actions/setup-python@v5","Install existing parsing and crypto libraries","Exact candidate and offline root cause regression")]}]}
        self.log=self.sha+"\nSuccessfully installed "+" ".join(f"{k}-{v}" for k,v in PACKAGES.items())
    def put(self,root,path,content):
        p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    def result(self):
        with patch("diagnostics.kyoto_impl32_fmea_adjudication.git_head",return_value=self.sha):
            return assess(self.production,self.collector,self.run_doc,self.jobs,self.log)
    def test_specific_closure_and_idempotence(self):
        a=self.result();self.assertEqual(a,self.result());self.assertEqual(a["closed_ids"],["GAP-17"]);self.assertEqual(len(a["open_ids"]),24);self.assertFalse(a["all_fixed_risks_closed"]);self.assertFalse(a["production_activation_authorized"])
    def test_changed_pin_reopens(self):
        p=self.production/next(iter(WORKFLOWS));p.write_text(p.read_text().replace("cryptography==46.0.7","cryptography>=46"))
        self.assertEqual(self.result()["closed_count"],0)
    def test_removed_installer_reopens(self):
        p=self.production/next(iter(WORKFLOWS));d=json.loads(p.read_text());d["jobs"]["sp-originals-independent"]["steps"].pop();p.write_text(json.dumps(d))
        self.assertEqual(self.result()["closed_count"],0)
    def test_unrelated_ci_or_changed_collector_rejected(self):
        self.run_doc["head_sha"]="b"*40;self.assertEqual(self.result()["closed_count"],0)
    def test_install_log_drift_reopens(self):
        self.log=self.log.replace("cffi-2.1.1","cffi-2.1.2");self.assertEqual(self.result()["closed_count"],0)
    def test_no_self_reported_pass(self):
        self.run_doc["conclusion"]="failure";self.run_doc["passed"]=True;self.assertEqual(self.result()["closed_count"],0)
    def test_fixed_denominator_cannot_shrink(self):
        self.ledger["risks"].pop();self.put(self.collector,LEDGER,json.dumps(self.ledger))
        with self.assertRaises(ValueError):self.result()
    def test_successful_exit_exists_when_all_verifiers_satisfy_original_scope(self):
        # Exercise completion aggregation only, never supply synthetic results to real certification.
        a=summarize(self.ledger,{x:{"state":"CLOSED_IN_ORIGINAL_SCOPE"} for x in IDS})
        self.assertTrue(a["all_fixed_risks_closed"]);self.assertEqual(a["closed_count"],25)
