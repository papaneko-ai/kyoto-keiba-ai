"""Parse actual isolated deployment YAML, not an approximate template."""
import unittest,re
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]/".github/workflows"
OBS="kyoto-20261128-29-two-source-production-observer.yml"
HAND="kyoto-20261128-29-result-handoff.yml"
PREF="kyoto-impl30-nov28-29-offline-preflight.yml"
EXPECTED=["15 0 28 11 *","15 1 28 11 *","5 2 28 11 *","50 2 28 11 *",
          "15 0 29 11 *","15 1 29 11 *","10 2 29 11 *","55 2 29 11 *"]

class ProductionWorkflowContract(unittest.TestCase):
    def setUp(self):
        self.raw=(ROOT/OBS).read_text()
        self.obs=yaml.load(self.raw,Loader=yaml.BaseLoader)
        self.handoff=yaml.load((ROOT/HAND).read_text(),Loader=yaml.BaseLoader)
        self.jobs=self.obs["jobs"]

    def test_actual_eight_cron_slots_and_no_pull_request_live_trigger(self):
        self.assertEqual([x["cron"] for x in self.obs["on"]["schedule"]],EXPECTED)
        self.assertEqual(set(self.obs["on"]),{"schedule","workflow_dispatch"})
        self.assertEqual(self.obs["on"]["workflow_dispatch"]["inputs"]["race_day"]["options"],["20261128","20261129"])
        self.assertEqual(self.obs["concurrency"]["cancel-in-progress"],"false")
        self.assertEqual(self.obs["concurrency"]["queue"],"max")

    def test_exact_one_pin_shared_pc_sp_and_handoff(self):
        select=self.jobs["select-collector"]
        baseline=select["env"]["DEFAULT_COLLECTOR_SHA"]
        self.assertRegex(baseline,r"^[0-9a-f]{40}$")
        self.assertEqual(self.jobs["pc-originals-independent"]["needs"],"select-collector")
        self.assertEqual(self.jobs["sp-originals-independent"]["needs"],["select-collector","pc-originals-independent"])
        for lane in ("pc-originals-independent","sp-originals-independent"):
            job=self.jobs[lane]
            self.assertEqual(job["env"]["COLLECTOR_SHA"],"${{ needs.select-collector.outputs.collector_sha }}")
            self.assertEqual(job["env"]["KYOTO_TARGET_DAY"],select["env"]["KYOTO_TARGET_DAY"])
            self.assertEqual(job["steps"][0]["with"]["ref"],"${{ env.COLLECTOR_SHA }}")
            self.assertTrue(any(baseline in x.get("run","") and "SATURDAY_SOURCE_UNEXPECTED_NO_HTTP" in x.get("run","") for x in job["steps"]))
        self.assertIn("always()",self.jobs["sp-originals-independent"]["if"])
        self.assertIn("needs.select-collector.result == 'success'",self.jobs["sp-originals-independent"]["if"])
        self.assertEqual(self.handoff["jobs"]["authenticated-handoff"]["steps"][0]["with"]["ref"],baseline)

    def test_preserves_source_protections_and_encrypted_upload(self):
        for lane,folder in (("pc-originals-independent","pc"),("sp-originals-independent","sp")):
            job=self.jobs[lane]
            commands="\n".join(x.get("run","") for x in job["steps"])
            for token in ("OUTSIDE_DAY_WINDOW_NO_HTTP","ENCRYPTION_KEY_REQUIRED_NO_HTTP","SOURCE_REVISION_MISMATCH_NO_HTTP","kyoto_weekend_retry_guard","kyoto_weekend_postflight","--seal-only"):
                self.assertIn(token,commands)
            uploads=[x for x in job["steps"] if x.get("uses","").startswith("actions/upload-artifact@")]
            self.assertEqual(len(uploads),2)
            self.assertTrue(all(x["with"]["path"]==folder+"_sealed/" for x in uploads))
            self.assertEqual(uploads[1]["with"]["overwrite"],"true")
        self.assertNotIn("KYOTO_NOV22_VERIFIED_COLLECTOR_SHA",self.raw)
        self.assertNotIn("SP_INDEPENDENT_OFFICIAL_R12_URL",self.raw)

    def test_handoff_is_evidence_only_and_scheduled_both_days(self):
        self.assertEqual([x["cron"] for x in self.handoff["on"]["schedule"]],["0 12 28 11 *","0 12 29 11 *"])
        self.assertEqual(self.handoff["jobs"]["authenticated-handoff"]["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")
        self.assertIn("kyoto_impl25_c12_all_runs_handoff",(ROOT/HAND).read_text())
        pre=yaml.load((ROOT/PREF).read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(pre["jobs"]["offline-next-week"]["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")

    def test_postrace_two_slots_per_day_share_verified_pin_and_source_lock(self):
        path=ROOT/"kyoto-20261128-29-postrace-evidence.yml"
        raw=path.read_text()
        doc=yaml.load(raw,Loader=yaml.BaseLoader)
        self.assertEqual([x["cron"] for x in doc["on"]["schedule"]],
            ["0 10 28 11 *","0 13 28 11 *","0 10 29 11 *","0 13 29 11 *"])
        self.assertEqual(set(doc["on"]),{"schedule","workflow_dispatch"})
        self.assertEqual(doc["concurrency"]["cancel-in-progress"],"false")
        self.assertEqual(doc["concurrency"]["queue"],"max")
        self.assertTrue(doc["concurrency"]["group"].startswith("kyoto-20261128-29-source-"))
        job=doc["jobs"]["postrace-source-evidence"]
        pin=self.jobs["select-collector"]["env"]["DEFAULT_COLLECTOR_SHA"]
        self.assertEqual(job["steps"][0]["with"]["ref"],pin)
        self.assertEqual(job["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")
        self.assertEqual(job["env"]["KYOTO_POSTRACE_HTTP_APPROVED"],"YES")
        self.assertIn("kyoto_impl30_postrace_runtime",raw)
        self.assertIn("postrace_sealed/",raw)
        self.assertEqual(job["steps"][-1]["with"]["retention-days"],"90")
        self.assertNotIn("TURSO",raw)

    def test_exact_python_and_dependency_versions_across_all_new_source_jobs(self):
        pin_line="python -m pip install --no-deps beautifulsoup4==4.15.0 soupsieve==4.1.3 typing-extensions==4.16.0 cryptography==46.0.7 cffi==2.1.1 pycparser==3.12"
        for path in (OBS,HAND,PREF,"kyoto-20261128-29-postrace-evidence.yml"):
            doc=yaml.load((ROOT/path).read_text(),Loader=yaml.BaseLoader)
            for job in doc["jobs"].values():
                for step in job["steps"]:
                    if step.get("uses","").startswith("actions/setup-python@"):
                        self.assertEqual(step["with"]["python-version"],"3.11.18")
                    if "pip install" in step.get("run",""):
                        self.assertEqual(step["run"],pin_line)
if __name__=="__main__":unittest.main()
