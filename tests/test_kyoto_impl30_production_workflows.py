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
    def test_exact_native_slot_run_names_on_all_five_workflows(self):
        expected = "${{ github.event_name == 'schedule' && format('kyoto-native:{0}', github.event.schedule) || github.event_name }}"
        for path in (OBS,HAND,"kyoto-20261128-29-postrace-evidence.yml","kyoto-20261128-29-auxiliary-refresh.yml","kyoto-20261128-29-workout-source.yml"):
            doc=yaml.load((ROOT/path).read_text(),Loader=yaml.BaseLoader)
            self.assertEqual(doc["run-name"],expected)
            self.assertNotIn("schedule",doc["on"])
            self.assertIn("workflow_dispatch",doc["on"])
    def setUp(self):
        self.raw=(ROOT/OBS).read_text()
        self.obs=yaml.load(self.raw,Loader=yaml.BaseLoader)
        self.handoff=yaml.load((ROOT/HAND).read_text(),Loader=yaml.BaseLoader)
        self.jobs=self.obs["jobs"]

    def test_actual_eight_cron_slots_and_no_pull_request_live_trigger(self):
        self.assertNotIn("schedule",self.obs["on"])
        self.assertEqual(set(self.obs["on"]),{"workflow_dispatch"})
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
            self.assertEqual(job["steps"][0]["name"],"Record monotonic runner start for source preservation reserve")
            self.assertEqual(job["steps"][0]["run"],'echo "KYOTO_JOB_START_SECONDS=$(cut -d. -f1 /proc/uptime)" >> "$GITHUB_ENV"')
            self.assertEqual(job["steps"][1]["uses"],"actions/checkout@v4")
            self.assertEqual(job["steps"][1]["with"]["ref"],"${{ env.COLLECTOR_SHA }}")
            self.assertTrue(any(baseline in x.get("run","") and "SATURDAY_SOURCE_UNEXPECTED_NO_HTTP" in x.get("run","") for x in job["steps"]))
        self.assertIn("always()",self.jobs["sp-originals-independent"]["if"])
        self.assertIn("needs.select-collector.result == 'success'",self.jobs["sp-originals-independent"]["if"])
        sunday=select["env"]["SUNDAY_OVERRIDE_SHA"]
        self.assertRegex(sunday,r"^[0-9a-f]{40}$")
        self.assertEqual(self.handoff["jobs"]["authenticated-handoff"]["steps"][0]["with"]["ref"],"c289c5ec4e6ad322a7e08acf173da3352ed23dba")
        self.assertNotEqual(self.handoff["jobs"]["authenticated-handoff"]["steps"][0]["with"]["ref"],sunday)
        self.assertEqual(baseline,"3f4b3d77357745ead05a9f78db34eb6ac2d78637")

    def test_preserves_source_protections_and_encrypted_upload(self):
        for lane,folder in (("pc-originals-independent","pc"),("sp-originals-independent","sp")):
            job=self.jobs[lane]
            commands="\n".join(x.get("run","") for x in job["steps"])
            for token in ("OUTSIDE_DAY_WINDOW_NO_HTTP","ENCRYPTION_KEY_REQUIRED_NO_HTTP","SOURCE_REVISION_MISMATCH_NO_HTTP","kyoto_weekend_retry_guard","kyoto_weekend_postflight","--seal-only"):
                self.assertIn(token,commands)
            uploads=[x for x in job["steps"] if x.get("uses","").startswith("actions/upload-artifact@")]
            self.assertEqual(len(uploads),2)
            self.assertEqual(uploads[0]["continue-on-error"],"true")
            self.assertNotIn("continue-on-error",uploads[1])
            self.assertIn("outcome == \'failure\'",uploads[1]["if"])
            self.assertTrue(all(x["with"]["path"]==folder+"_sealed/" for x in uploads))
            self.assertEqual(uploads[1]["with"]["overwrite"],"true")
        self.assertNotIn("KYOTO_NOV22_VERIFIED_COLLECTOR_SHA",self.raw)
        self.assertNotIn("SP_INDEPENDENT_OFFICIAL_R12_URL",self.raw)

    def test_handoff_is_evidence_only_and_scheduled_both_days(self):
        self.assertNotIn("schedule",self.handoff["on"])
        self.assertEqual(self.handoff["jobs"]["authenticated-handoff"]["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")
        self.assertIn("kyoto_impl25_c12_all_runs_handoff",(ROOT/HAND).read_text())
        pre=yaml.load((ROOT/PREF).read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(pre["jobs"]["offline-next-week"]["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")

    def test_postrace_two_slots_per_day_share_verified_pin_and_source_lock(self):
        path=ROOT/"kyoto-20261128-29-postrace-evidence.yml"
        raw=path.read_text()
        doc=yaml.load(raw,Loader=yaml.BaseLoader)
        self.assertNotIn("schedule",doc["on"])
        self.assertEqual(set(doc["on"]),{"workflow_dispatch"})
        self.assertEqual(doc["concurrency"]["cancel-in-progress"],"false")
        self.assertEqual(doc["concurrency"]["queue"],"max")
        self.assertIn("kyoto-20261128-29-source-{0}",doc["concurrency"]["group"])
        job=doc["jobs"]["postrace-source-evidence"]
        pin=self.jobs["select-collector"]["env"]["DEFAULT_COLLECTOR_SHA"]
        expected_postrace_pin="b800308169173d9e82cf93db9bf7b381e361cc76"
        self.assertEqual(job["steps"][0]["with"]["ref"],expected_postrace_pin)
        self.assertNotEqual(expected_postrace_pin,pin)
        self.assertIn('test "$(git rev-parse HEAD)" = '+repr(expected_postrace_pin),raw)
        self.assertNotIn(pin,raw)
        self.assertEqual(job["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")
        self.assertEqual(job["env"]["KYOTO_POSTRACE_HTTP_APPROVED"],"YES")
        self.assertIn("kyoto_impl30_postrace_runtime",raw)
        self.assertIn("postrace_sealed/",raw)
        uploads=[x for x in job["steps"] if x.get("uses","").startswith("actions/upload-artifact@")]
        self.assertEqual(len(uploads),2)
        self.assertEqual(uploads[0]["continue-on-error"],"true")
        self.assertNotIn("continue-on-error",uploads[1])
        self.assertEqual(uploads[1]["with"]["overwrite"],"true")
        self.assertIn("outcome == \'failure\'",uploads[1]["if"])
        self.assertEqual(uploads[0]["with"]["name"],uploads[1]["with"]["name"])
        self.assertTrue(all(x["with"]["retention-days"]=="90" for x in uploads))
        self.assertNotIn("TURSO",raw)

    def test_auxiliary_refresh_preserves_morning_slots_and_shared_source_lock(self):
        path=ROOT/"kyoto-20261128-29-auxiliary-refresh.yml"
        raw=path.read_text()
        doc=yaml.load(raw,Loader=yaml.BaseLoader)
        self.assertEqual(doc["name"],"Kyoto Nov28-29 afternoon auxiliary refresh")
        self.assertNotIn("schedule",doc["on"])
        self.assertNotIn("schedule",self.obs["on"])
        self.assertEqual(set(doc["on"]),{"workflow_dispatch"})
        self.assertEqual(doc["concurrency"]["cancel-in-progress"],"false")
        self.assertEqual(doc["concurrency"]["queue"],"max")
        self.assertIn("kyoto-20261128-29-source-{0}",doc["concurrency"]["group"])
        job=doc["jobs"]["afternoon-auxiliary-source"]
        pin=self.jobs["select-collector"]["env"]["DEFAULT_COLLECTOR_SHA"]
        expected_aux_pin="c289c5ec4e6ad322a7e08acf173da3352ed23dba"
        self.assertEqual(job["steps"][0]["with"]["ref"],expected_aux_pin)
        self.assertNotEqual(expected_aux_pin,pin)
        self.assertIn('test "$(git rev-parse HEAD)" = '+repr(expected_aux_pin),raw)
        self.assertEqual(job["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")
        self.assertEqual(job["env"]["KYOTO_AUX_HTTP_APPROVED"],"YES")
        self.assertIn("kyoto_impl30_auxiliary_refresh --day",raw)
        self.assertIn("NOV28-29-AUXILIARY-SOURCE-ONLY",job["if"])
        self.assertNotIn("TURSO",raw)
        uploads=[x for x in job["steps"] if x.get("uses","").startswith("actions/upload-artifact@")]
        self.assertEqual(len(uploads),2)
        self.assertTrue(all(x["with"]["path"]=="auxiliary_sealed/" for x in uploads))
        self.assertTrue(all(x["with"]["name"].startswith("kyoto-auxiliary-") for x in uploads))
        self.assertIn("outcome == 'failure'",uploads[1]["if"])
        self.assertEqual(uploads[1]["with"]["overwrite"],"true")

    def test_exact_python_and_dependency_versions_across_all_new_source_jobs(self):
        pin_line="python -m pip install --no-deps beautifulsoup4==4.15.0 soupsieve==4.1.3 typing-extensions==4.16.0 cryptography==46.0.7 cffi==2.1.1 pycparser==3.12"
        for path in (OBS,HAND,PREF,"kyoto-20261128-29-postrace-evidence.yml","kyoto-20261128-29-auxiliary-refresh.yml"):
            doc=yaml.load((ROOT/path).read_text(),Loader=yaml.BaseLoader)
            for job in doc["jobs"].values():
                for step in job["steps"]:
                    if step.get("uses","").startswith("actions/setup-python@"):
                        self.assertEqual(step["with"]["python-version"],"3.11.18")
                    if "pip install" in step.get("run",""):
                        self.assertEqual(step["run"],pin_line)
    def test_live_slots_do_not_reexecute_historical_regressions(self):
        # Nov21 failure mode: test clock blocked real source capture.
        # Every old suite is in the exact candidate CI before activation.
        pre=(ROOT/PREF).read_text()
        for module in ("test_kyoto_g03_weekend_bridge","test_kyoto_g05_weekend_bridge",
                       "test_kyoto_g04_all_horse_profiles","test_kyoto_predictable_failure_gate",
                       "test_kyoto_impl23_claim_preflight","test_kyoto_sp_observed_source"):
            self.assertIn(module,pre)
        for lane in ("pc-originals-independent","sp-originals-independent"):
            commands="\n".join(x.get("run","") for x in self.jobs[lane]["steps"])
            self.assertNotIn("python -m unittest",commands)
            self.assertLess(commands.index("SOURCE_REVISION_MISMATCH_NO_HTTP"),
                            commands.index("python -m diagnostics.kyoto_weekend_capture"))
            self.assertLess(commands.index("python -m diagnostics.kyoto_weekend_postflight"),
                            commands.index("--seal-only"))
    def test_saturday_handoff_authenticates_policy_for_sunday(self):
        steps=self.handoff["jobs"]["authenticated-handoff"]["steps"]
        signed=[x for x in steps if "kyoto_impl30_nextday_adaptation" in x.get("run","")]
        self.assertEqual(len(signed),1)
        self.assertIn("20261128",signed[0]["if"])
        self.assertEqual(signed[0]["continue-on-error"],"true")
        self.assertIn("--report handoff/report.json --out handoff/nextday_policy.json",signed[0]["run"])
        self.assertLess(steps.index(signed[0]),next(i for i,x in enumerate(steps) if x.get("uses","").startswith("actions/upload-artifact@")))
    def test_sunday_improvement_evaluation_is_evidence_only_before_upload(self):
        steps=self.handoff["jobs"]["authenticated-handoff"]["steps"]
        found=[x for x in steps if "kyoto_impl31_improvement_evaluation" in x.get("run","")]
        self.assertEqual(len(found),1)
        step=found[0]
        self.assertIn("20261129",step["if"])
        self.assertEqual(step["continue-on-error"],"true")
        self.assertEqual(step["timeout-minutes"],"1")
        self.assertIn("--report handoff/report.json --out handoff/improvement_evaluation.json",step["run"])
        self.assertLess(steps.index(step),next(i for i,x in enumerate(steps) if x.get("uses","").startswith("actions/upload-artifact@")))
    def test_handoff_upload_retry_preserves_signed_policy_and_does_not_hide_second_failure(self):
        steps=self.handoff["jobs"]["authenticated-handoff"]["steps"]
        uploads=[x for x in steps if x.get("uses","").startswith("actions/upload-artifact@")]
        self.assertEqual(len(uploads),2)
        first,retry=uploads
        self.assertEqual(first["id"],"upload_handoff_primary")
        self.assertEqual(first["if"],"always()")
        self.assertEqual(first["continue-on-error"],"true")
        self.assertEqual(retry["if"],"${{ always() && steps.upload_handoff_primary.outcome == 'failure' }}")
        self.assertNotIn("continue-on-error",retry)
        self.assertEqual(retry["with"],dict(first["with"],overwrite="true"))
        self.assertEqual(first["with"]["path"],"handoff/")
        self.assertEqual(first["with"]["if-no-files-found"],"error")
if __name__=="__main__":unittest.main()
