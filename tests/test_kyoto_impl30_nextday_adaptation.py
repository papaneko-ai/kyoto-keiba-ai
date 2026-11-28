import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_impl30_nextday_adaptation import derive,make,accept,recover,budgets,SOURCE_DAY,TARGET_DAY,NAME,WORKFLOW
REPO="papaneko-ai/kyoto-keiba-ai";SHA="a"*40;KEY="b"*64
def saturday(*,paired=12,profiles=36,roster=12):
    races={}
    for n in range(1,13):
        horses={}
        for h in range(1,4):
            state="SOURCE_VERIFIED" if (n-1)*3+h<=profiles else "MISSING"
            horses[str(h)]={k:{"state":state} for k in ("profile","prior_form")}
        races[str(n)]={"state":"ROSTER_VERIFIED","racecard":{"state":"SOURCE_VERIFIED"},"paired_same_slot":n<=paired,"horses":horses} if n<=roster else {"state":"NO_VERIFIED_ROSTER"}
    return {"day":SOURCE_DAY,"next_day":TARGET_DAY,"all_run_metadata_screened":True,"github_run_listing_complete":True,
        "day_source_coverage":{"schema":"kyoto_impl30_day_source_coverage.v1","day":SOURCE_DAY,"race_denominator":12,
          "authenticated_pc_slots":4,"races":races,"totals":{"racecards":roster,"paired_same_slot_races":min(paired,roster),
            "registered_horses_known":roster*3,"profile":min(profiles,roster*3),"prior_form":min(profiles,roster*3)}}}
def sign(r):return make(r,repo=REPO,run_id=101,collector_sha=SHA,key=KEY)
class NextDay(unittest.TestCase):
    def test_automatic_policy_options(self):
        for report,want,b in [(saturday(),"BASELINE",(720,240)),(saturday(paired=2),"MARKET_OR_ROSTER_RECOVERY",(720,360)),
                (saturday(profiles=20),"PROFILE_RECOVERY",(600,360)),(saturday(roster=9),"MARKET_OR_ROSTER_RECOVERY",(720,360))]:
            self.assertEqual(derive(report)["mode"],want)
            self.assertEqual(budgets(want),b)
            self.assertEqual(sign(report),sign(copy.deepcopy(report)))
    def test_not_trusting_summary_without_matching_per_item_counts(self):
        r=saturday(paired=2)
        r["day_source_coverage"]["totals"]["paired_same_slot_races"]=12
        self.assertEqual(derive(r)["mode"],"BASELINE")
        r=saturday(paired=2);r["all_run_metadata_screened"]=False
        self.assertEqual(derive(r)["mode"],"BASELINE")
    def test_tamper_wrong_run_wrong_release_and_wrong_report(self):
        r=saturday(paired=2);d=sign(r)
        for field,v in [("repo","other/repo"),("run_id",102),("collector_sha","c"*40),("key","d"*64)]:
            kw=dict(repo=REPO,run_id=101,collector_sha=SHA,key=KEY);kw[field]=v
            with self.assertRaises(ValueError):accept(d,r,**kw)
        with self.assertRaises(ValueError):accept(d,saturday(),repo=REPO,run_id=101,collector_sha=SHA,key=KEY)
        d["body"]["decision"]["mode"]="PROFILE_RECOVERY"
        with self.assertRaises(ValueError):accept(d,r,repo=REPO,run_id=101,collector_sha=SHA,key=KEY)
    def test_saturday_to_sunday_artifact_to_applied_budget(self):
        # End-to-end contract through signed handoff bytes, exact GitHub run
        # identity, bounded download, verification and real runtime budget table.
        r=saturday(paired=2,profiles=20);doc=sign(r)
        run={"id":101,"name":NAME,"created_at":"2026-11-28T12:00:00Z","event":"schedule",
            "status":"completed","conclusion":"success","head_repository":{"full_name":REPO},"path":".github/workflows/"+WORKFLOW}
        def api(args,**kwargs):
            self.assertLessEqual(kwargs["timeout"],5)
            return json.dumps({"total_count":1,"workflow_runs":[run]} if "/workflows/" in args[-1] else
                {"total_count":1,"artifacts":[{"name":"kyoto-handoff-101-20261128","expired":False}]})
        def download(args,**kwargs):
            self.assertLessEqual(kwargs["timeout"],10)
            root=Path(args[-1]);(root/"report.json").write_text(json.dumps(r));(root/"nextday_policy.json").write_text(json.dumps(doc))
        with patch("diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output",side_effect=api),patch("diagnostics.kyoto_impl30_nextday_adaptation.subprocess.run",side_effect=download):
            mode,reason=recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY)
            self.assertEqual(reason,"AUTHENTICATED_SATURDAY_HANDOFF_101")
            self.assertEqual(budgets(mode),(720,360))
            self.assertEqual(recover(SOURCE_DAY,repo=REPO,collector_sha=SHA,key=KEY)[0],"BASELINE")
            r["day_source_coverage"]["totals"]["profile"]=1
            self.assertEqual(recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY)[0],"BASELINE")
    def test_exact_saturday_signer_survives_verified_sunday_upgrade(self):
        from diagnostics.kyoto_impl30_nextday_adaptation import SATURDAY_HANDOFF_COLLECTOR
        r=saturday(paired=2)
        run={"id":101,"name":NAME,"created_at":"2026-11-28T12:00:00Z","event":"schedule","status":"completed","conclusion":"success","head_repository":{"full_name":REPO},"path":".github/workflows/"+WORKFLOW}
        def api(args,**kw):
            ep=args[-1]
            if WORKFLOW in ep:return json.dumps({"total_count":1,"workflow_runs":[run]})
            if "/artifacts?" in ep:return json.dumps({"total_count":1,"artifacts":[{"name":"kyoto-handoff-101-20261128","expired":False}]})
            return json.dumps({"total_count":0,"workflow_runs":[]})
        for signer,expected in ((SATURDAY_HANDOFF_COLLECTOR,"MARKET_OR_ROSTER_RECOVERY"),("c"*40,"BASELINE")):
            doc=make(r,repo=REPO,run_id=101,collector_sha=signer,key=KEY)
            def download(args,**kw):
                root=Path(args[-1]);(root/"report.json").write_text(json.dumps(r));(root/"nextday_policy.json").write_text(json.dumps(doc))
            with patch("diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output",side_effect=api),patch("diagnostics.kyoto_impl30_nextday_adaptation.subprocess.run",side_effect=download):
                self.assertEqual(recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY)[0],expected)
    def test_real_zero_coverage_incident_not_masked_by_green_job_status(self):
        from diagnostics.kyoto_impl30_nextday_adaptation import recover_from_metadata,NOV28_INCIDENT_RUN_IDS,OBSERVER,OBSERVER_NAME
        rows=[{"id":i,"name":"workflow_dispatch","created_at":"2026-11-28T03:00:00Z","event":"workflow_dispatch","head_branch":"main","status":"completed","conclusion":"success","head_repository":{"full_name":REPO},"path":".github/workflows/"+OBSERVER} for i in NOV28_INCIDENT_RUN_IDS]
        def api(ep):
            if "/workflows/" in ep:return {"total_count":len(rows),"workflow_runs":rows}
            return {"total_count":0,"jobs":[]}
        self.assertEqual(recover_from_metadata(api,REPO),("MARKET_OR_ROSTER_RECOVERY","NOV28_AUTHENTICATED_SOURCE_GAP_INCIDENT_141"))
        rows.pop()
        self.assertEqual(recover_from_metadata(api,REPO)[0],"BASELINE")
    def test_actual_run_names_and_wrong_identity(self):
        from diagnostics.kyoto_impl25_c12_all_runs_handoff import run_name_matches
        from diagnostics.kyoto_impl30_nextday_adaptation import OBSERVER,OBSERVER_NAME
        from diagnostics.kyoto_impl31_handoff_budget import _index
        base={"id":46087080554,"name":"workflow_dispatch","event":"workflow_dispatch","head_branch":"main","created_at":"2026-11-28T00:17:22Z","head_repository":{"full_name":REPO},"path":".github/workflows/"+OBSERVER}
        self.assertTrue(run_name_matches(base,OBSERVER_NAME,OBSERVER,SOURCE_DAY))
        self.assertTrue(_index({"total_count":1,"workflow_runs":[base]},SOURCE_DAY,REPO,OBSERVER_NAME,OBSERVER)[1])
        native={**base,"event":"schedule","name":"kyoto-native:15 0 28 11 *"}
        self.assertTrue(run_name_matches(native,OBSERVER_NAME,OBSERVER,SOURCE_DAY))
        for change in ({"head_branch":"other"},{"path":"other"},{"event":"push"},{"name":"kyoto-native:15 0 29 11 *"},{"created_at":"2026-11-29T00:17:22Z"}):
            self.assertFalse(run_name_matches({**base,**change},OBSERVER_NAME,OBSERVER,SOURCE_DAY))
        handoff={**base,"name":"kyoto-native:0 12 28 11 *","event":"schedule","path":".github/workflows/"+WORKFLOW}
        self.assertTrue(run_name_matches(handoff,NAME,WORKFLOW,SOURCE_DAY))
    def test_unavailable_github_does_not_veto(self):
        with patch("diagnostics.kyoto_impl30_nextday_adaptation.subprocess.check_output",side_effect=OSError):
            self.assertEqual(recover(TARGET_DAY,repo=REPO,collector_sha=SHA,key=KEY)[0],"BASELINE")
    def test_actual_capture_uses_selected_budgets(self):
        import inspect
        from diagnostics.kyoto_weekend_capture import capture
        src=inspect.getsource(capture)
        self.assertIn('if live and day=="20261129":',src)
        self.assertIn("market_seconds,sp_seconds=budgets(policy)",src)
        self.assertIn("g06_sealing_reserve_deadline=pc_capture_start_monotonic+market_seconds",src)
        self.assertIn("deadline=time.monotonic()+sp_seconds",src)
        self.assertIn("deadline_monotonic=deadline,**opts",src)
        self.assertIn("deadline=deadline)",src)
        self.assertIn("g04_market_reserve_deadline=pc_capture_start_monotonic+1020.0",src)
    def test_actual_sunday_sp_entrypoint_uses_recovered_budget(self):
        import os
        from diagnostics.kyoto_weekend_capture import capture
        def discover(root,**kwargs):
            root.mkdir()
            (root/"sp_discovery_receipt.json").write_text("{}")
            return {"network_requests_started":0,"racecard_url":"observed-fixture"}
        for mode,want in [("BASELINE",240),("MARKET_OR_ROSTER_RECOVERY",360)]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{
                "KYOTO_TARGET_DAY":TARGET_DAY,"KYOTO_WEEKEND_HTTP_APPROVED":"YES",
                "GITHUB_EVENT_NAME":"schedule","ARCHIVE_KEY":KEY,"GITHUB_REPOSITORY":REPO,"COLLECTOR_SHA":SHA
            }),patch("diagnostics.kyoto_weekend_capture.validate_day"),patch("diagnostics.kyoto_weekend_capture.time.monotonic",return_value=1000),patch(
                "diagnostics.kyoto_impl30_nextday_adaptation.recover",return_value=(mode,"fixture_verified")),patch(
                "diagnostics.kyoto_weekend_sp_discovery.discover",side_effect=discover),patch(
                "diagnostics.kyoto_sp_all12_observed_capture.capture_all",return_value={"races":{}}) as live_capture:
                capture(TARGET_DAY,"SP",str(Path(temp)/"source"),live=True,opener=object())
                live_capture.assert_called_once()
                self.assertEqual(live_capture.call_args.kwargs["deadline_monotonic"],1000+want)

if __name__=="__main__":unittest.main()
