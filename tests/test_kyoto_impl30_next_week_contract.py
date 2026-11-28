"""New-week evidence chain regressions, offline official-shaped fixtures only."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_g03_all_races import acquire_all
from diagnostics.kyoto_g05_conditions import compile_saved
from diagnostics.kyoto_impl25_c10_auxiliary_coverage import save as save_c10
from diagnostics.kyoto_impl25_c11_per_family_proof import save as save_c11
from diagnostics.kyoto_impl25_c12_all_runs_handoff import summarize,gather,WEEKENDS,HandoffRejected
from diagnostics.kyoto_weekend_retry_guard import EARLY,PRIMARY,BACKUP,evaluate
from diagnostics.kyoto_weekend_remote_claim_runtime import CRON_SLOTS
from tests.test_kyoto_g03_all_races import meeting,source_race,PARENT
from tests.test_kyoto_g05_conditions import source
from tests.test_kyoto_impl25_c12_all_runs_handoff import make

DAYS=("20261128","20261129")

def evidence(day,root):
    previous="20261121"
    stamp=f"2026-11-{day[-2:]}T00:00:00Z"
    original=root/"source"
    current=root/"saved";current.mkdir()
    old_date="2026年11月21日".encode("cp932")
    new_date=f"2026年11月{day[-2:]}日".encode("cp932")
    report=acquire_all(day=day,root=original,
        meeting_raw=meeting().replace(previous.encode(),day.encode()),meeting_url=PARENT,
        fetch=lambda url:source(source_race(url)).replace(old_date,new_date),
        captured_at_utc=lambda:stamp,allowed=True)
    if not report["complete"]:
        raise AssertionError(report["races"])
    for p in original.iterdir():p.rename(current/("g03_"+p.name))
    shutil.copyfile(current/"g03_official_meeting.html",current/"official_meeting.html")
    (current/"g03_receipt.json").write_text(json.dumps(report),encoding="utf8")
    return current

def entry(day,n):
    e=make(n)
    e["run"].update(name=WEEKENDS[day][0],created_at=f"2026-11-{day[-2:]}T02:00:00Z")
    for a in e["artifacts"]:a["name"]=a["name"].replace("20261121",day)
    return e

class NewWeekendContract(unittest.TestCase):
    def test_new_days_c10_c11_originals_and_missing_fields(self):
        for day in DAYS:
            with self.subTest(day=day),tempfile.TemporaryDirectory() as tmp:
                root=evidence(day,Path(tmp))
                compile_saved(root,day=day)
                aux=save_c10(root,day)
                self.assertEqual(aux["totals"]["weather"]["observed_with_saved_original"],12)
                self.assertEqual(aux["totals"]["workout"]["missing_or_unverified"],48)
                proof=save_c11(root,day)
                self.assertEqual(proof["g03_verified_races"],12)
                self.assertEqual(proof["g05_bound_races"],12)
                self.assertEqual(proof["g04_verified_profiles"],0)
                self.assertEqual(proof["g06_paired_market_races_locally_verified"],0)
                self.assertFalse(proof["prediction_ready"])
                self.assertFalse(proof["workout_independent_source_verified"])
    def test_old_day_original_is_not_new_day_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=evidence("20261128",Path(tmp))
            from diagnostics.kyoto_impl25_c11_per_family_proof import assess
            self.assertEqual(assess(root,"20261129")["g03_verified_races"],0)
    def test_all_eight_slots_match_turso_and_guard(self):
        for day in DAYS:
            for slot,cron in enumerate((*EARLY[day],PRIMARY[day],BACKUP[day])):
                with self.subTest(day=day,slot=slot):
                    self.assertEqual(CRON_SLOTS[day][cron],slot)
                    self.assertIn("ALLOWED",evaluate(day,123,"schedule",cron,[],{}))
    def test_next_day_all_four_runs_and_sunday_closeout(self):
        for day in DAYS:
            r=summarize(day,[entry(day,n) for n in range(1,5)],total_count=4)
            self.assertTrue(r["all_run_metadata_screened"])
            self.assertEqual(r["day"],day)
            self.assertEqual(r["next_day"],"20261129" if day==DAYS[0] else None)
            self.assertFalse(r["full_live_jra_coverage_proved"])
    def test_total_count_mismatch_never_claims_complete(self):
        r=summarize(DAYS[0],[entry(DAYS[0],n) for n in range(1,5)],total_count=5)
        self.assertFalse(r["all_run_metadata_screened"])
        self.assertFalse(r["github_run_listing_complete"])
    def test_wrong_workflow_and_day_rejected(self):
        with self.assertRaises(HandoffRejected):summarize(DAYS[1],[entry(DAYS[0],1)])
        e=entry(DAYS[0],1);e["run"]["name"]="Kyoto Nov21-22 independent encrypted original collection"
        with self.assertRaises(HandoffRejected):summarize(DAYS[0],[e])
    def test_new_day_gather_uses_new_workflow_and_exact_artifacts(self):
        day=DAYS[0];e=entry(day,99);e["artifacts"]=[{"name":"kyoto-pc-98-20261128","expired":False}]
        from diagnostics.kyoto_impl31_handoff_budget import gather_bounded,_worker
        repo="papaneko-ai/kyoto-keiba-ai"
        e["run"].update(head_repository={"full_name":repo},path=".github/workflows/"+WEEKENDS[day][1])
        calls=[]
        def api(path):
            calls.append(path)
            if "auxiliary-refresh.yml/runs?" in path:return {"total_count":0,"workflow_runs":[]}
            if "/runs?" in path:return {"total_count":1,"workflow_runs":[e["run"]]}
            if "/jobs?" in path:return {"total_count":2,"jobs":[{**j,"id":i+1} for i,j in enumerate(e["jobs"])]}
            return {"total_count":1,"artifacts":[{**a,"id":i+1} for i,a in enumerate(e["artifacts"])]}
        # Route the isolated worker through the same mocked API, retaining
        # the actual request construction and artifact-name gate.
        from subprocess import CompletedProcess
        def cli(args,**kwargs):
            self.assertEqual(args[:2],["gh","api"])
            self.assertIn("per_page=100&page=1",args[-1])
            return CompletedProcess(args,0,stdout=json.dumps(api(args[-1])),stderr="")
        with patch("diagnostics.kyoto_repair_control.subprocess.run",side_effect=cli),patch("diagnostics.kyoto_impl25_c12_all_runs_handoff._download") as download,patch("diagnostics.kyoto_impl31_handoff_budget.gather_bounded",side_effect=lambda d,r:gather_bounded(d,r,invoke=lambda task,end:_worker(*task))):
            r=gather(day,repo)
        download.assert_not_called()
        self.assertTrue(any("kyoto-20261128-29-two-source-production-observer.yml/runs?created=2026-11-28" in call for call in calls))
        self.assertFalse(r["all_run_metadata_screened"])
        self.assertEqual(r["metadata_recovery"]["main"],[{"page_size":100,"state":"COMPLETE","count":1}])
        self.assertEqual(r["scheduled_runs"][0]["lanes"]["PC"]["artifact_evidence_state"],"EXACT_ARTIFACT_NOT_FOUND_OR_AMBIGUOUS")

if __name__=="__main__":unittest.main()
