"""Cross-slot source union: independently parse fixture bytes and test conflicts."""
import copy,json,shutil,unittest
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
from diagnostics.kyoto_g04_all_horse_profiles import capture
from diagnostics.kyoto_impl30_day_coverage import extract_slot,combine,proof,include_postrace,digest
from diagnostics.kyoto_impl25_c12_all_runs_handoff import gather,WEEKENDS
from tests import test_kyoto_g04_all_horse_profiles as fixture

DAY=fixture.DAY
STAMP="2026-11-21T00:01:00Z"
LATER="2026-11-21T00:05:00Z"

class ActualOriginalTests(unittest.TestCase):
    setUp=fixture.AllHorseProfile.setUp
    fetch=fixture.AllHorseProfile.fetch

    def test_complementary_profile_originals_are_unioned_not_summed(self):
        other=self.root.parent/"other"
        shutil.copytree(self.root,other)
        def part(url,first):
            # One slot obtains horse 1,2; another horse 2,3.
            n=int(parse_qs(urlsplit(url).query)["CNAME"][0][-5:-3])
            if n==(3 if first else 1):raise TimeoutError("fixture_missing")
            return self.fetch(url)
        a=capture(root=self.root,day=DAY,fetch=lambda u:part(u,True),clock=lambda:STAMP,allowed=True)
        b=capture(root=other,day=DAY,fetch=lambda u:part(u,False),clock=lambda:LATER,allowed=True)
        self.assertEqual((a["profile_verified_count"],b["profile_verified_count"]),(24,24))
        first=extract_slot(self.root,DAY,101)
        second=extract_slot(other,DAY,102)
        result=combine(DAY,[first,second])
        self.assertEqual(result["totals"]["racecards"],12)
        self.assertEqual(result["totals"]["registered_horses_known"],36)
        self.assertEqual(result["totals"]["profile"],36)
        self.assertEqual(result["totals"]["prior_form"],36)
        self.assertEqual(result["totals"]["workout"],0)
        self.assertFalse(result["full_data_acquisition_certified"])
        self.assertEqual(result,combine(DAY,[second,first]))
        # Tamper with a profile original. The stored success flag is insufficient.
        p=other/"g04_profile_r01_h03.html"
        p.write_bytes(p.read_bytes()+b"tamper")
        tampered=combine(DAY,[first,extract_slot(other,DAY,102)])
        self.assertEqual(tampered["totals"]["profile"],35)
        self.assertIn("horse_3:profile:MISSING",tampered["races"]["1"]["missing"])

    def test_roster_conflict_and_two_slot_markets_never_certify_pair(self):
        slot=extract_slot(self.root,DAY,101)
        other=copy.deepcopy(slot);other["run_id"]="102"
        a,b=slot["races"]["1"],other["races"]["1"]
        a["markets"]["quinella"]={**proof("a"*64,STAMP,"Q"),"cancelled_horses":[]}
        b["markets"]["bracket_quinella"]={**proof("b"*64,LATER,"B"),"cancelled_horses":[]}
        result=combine(DAY,[slot,other])
        self.assertEqual(result["totals"]["quinella"],1)
        self.assertEqual(result["totals"]["bracket_quinella"],1)
        self.assertEqual(result["totals"]["paired_same_slot_races"],0)
        b["roster_digest"]="different"
        result=combine(DAY,[slot,other])
        self.assertEqual(result["races"]["1"]["state"],"ROSTER_OR_START_CONFLICT")
        self.assertEqual(result["totals"]["racecards"],11)
        self.assertFalse(result["horse_denominator_complete"])

    def test_same_timestamp_disagreement_is_not_selected(self):
        a=extract_slot(self.root,DAY,101)
        b=copy.deepcopy(a);b["run_id"]="102"
        a["races"]["1"]["horses"]["1"]["body_weight_kg"]=proof("a"*64,STAMP,450)
        b["races"]["1"]["horses"]["1"]["body_weight_kg"]=proof("b"*64,STAMP,452)
        r=combine(DAY,[a,b])
        self.assertEqual(r["races"]["1"]["horses"]["1"]["body_weight_kg"]["state"],"SAME_TIMESTAMP_CONFLICT")
        with self.assertRaises(ValueError):combine(DAY,[a,a])

    def test_postrace_replay_matches_exact_prerace_denominator(self):
        slot=extract_slot(self.root,DAY,101)
        coverage=combine(DAY,[slot])
        from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
        inputs=records_from_g03(self.root,day=DAY,skip_invalid_races=True)
        roster={n:item["expected_named_runners"] for n,item in inputs.items() if item}
        starts={n:item["verified_start_utc"] for n,item in inputs.items() if item}
        from datetime import timedelta
        from diagnostics.kyoto_g04_all_horse_profiles import _utc
        stamp=(_utc(starts[1])+timedelta(hours=1)).isoformat()
        obs={"state":"DUAL_PAGE_EXPLICIT_FINAL","day":DAY,"race":1,"result_utc":stamp,"payout_utc":stamp,
             "result_sha256":"a"*64,"payout_sha256":"b"*64,
             "markets":{"quinella":{"payout_per_100":{"1-2":400}},"bracket_quinella":{"payout_per_100":{"1-2":300}}}}
        replay={"schema":"kyoto_impl30_postrace_replay.v1","day":DAY,"prior_artifact_index_complete":True,
                "races":{"1":{"state":"SOURCE_REVISION_CHAIN","revisions":[{"run_id":"103","version":1,"observation":obs}]}}}
        combined=include_postrace(coverage,replay,roster=roster,starts=starts)
        self.assertEqual(combined["totals"]["official_result"],1)
        self.assertEqual(combined["totals"]["official_payout"],1)
        self.assertNotIn("official_result",combined["races"]["1"]["missing"])
        self.assertIn("official_result",coverage["races"]["1"]["missing"])
        self.assertFalse(combined["full_data_acquisition_certified"])
        replay["prior_artifact_index_complete"]=False
        pending=include_postrace(coverage,replay,roster=roster,starts=starts)
        self.assertEqual(pending["totals"]["official_result"],0)
        replay["prior_artifact_index_complete"]=True
        roster[1]=((1,1,"wrong horse"),)
        pending=include_postrace(coverage,replay,roster=roster,starts=starts)
        self.assertEqual(pending["races"]["1"]["postrace"]["state"],"ROSTER_OR_START_CONFLICT")

class HandoffConnection(unittest.TestCase):
    def test_only_authenticated_slot_is_aggregated_in_next_week_handoff(self):
        from diagnostics.kyoto_impl31_handoff_budget import gather_bounded,_worker
        day="20261128";workflow,filename,_=WEEKENDS[day];repo="papaneko-ai/kyoto-keiba-ai"
        def api(path):
            if "auxiliary-refresh.yml/runs?" in path:return {"total_count":0,"workflow_runs":[]}
            if "/runs?" in path:return {"total_count":1,"workflow_runs":[{"id":101,"event":"schedule","name":workflow,"created_at":"2026-11-28T00:15:00Z","status":"completed","conclusion":"success","head_repository":{"full_name":repo},"path":".github/workflows/"+filename}]}
            if "/jobs?" in path:return {"total_count":2,"jobs":[{"id":201,"name":"pc-originals-independent","conclusion":"success","steps":[]},{"id":202,"name":"sp-originals-independent","conclusion":"success","steps":[]}]}
            return {"total_count":1,"artifacts":[{"id":301,"name":"kyoto-pc-101-20261128","expired":False}]}
        from subprocess import CompletedProcess
        def cli(args,**kwargs):
            self.assertEqual(args[:2],["gh","api"])
            self.assertIn("per_page=100&page=1",args[-1])
            return CompletedProcess(args,0,stdout=json.dumps(api(args[-1])),stderr="")
        result={"state":"SOURCE_ONLY","ciphertext_authenticated":True,"source_original_sha_utc_checked":True,"day_coverage_slot":{"day":day,"run_id":"101","races":{}}}
        with patch("diagnostics.kyoto_repair_control.subprocess.run",side_effect=cli),patch("diagnostics.kyoto_impl25_c12_all_runs_handoff._download"),patch("diagnostics.kyoto_weekend_day21_artifact_triage.assess_lane",return_value=result),patch("diagnostics.kyoto_impl31_handoff_budget.gather_bounded",side_effect=lambda d,r:gather_bounded(d,r,invoke=lambda task,end:_worker(*task))):
            report=gather(day,repo)
        self.assertEqual(report["day_source_coverage"]["authenticated_pc_slots"],1)
        self.assertEqual(report["day_source_coverage"]["race_denominator"],12)
        self.assertFalse(report["day_source_coverage"]["full_data_acquisition_certified"])
        result["ciphertext_authenticated"]=False
        with patch("diagnostics.kyoto_repair_control.subprocess.run",side_effect=cli),patch("diagnostics.kyoto_impl25_c12_all_runs_handoff._download"),patch("diagnostics.kyoto_weekend_day21_artifact_triage.assess_lane",return_value=result),patch("diagnostics.kyoto_impl31_handoff_budget.gather_bounded",side_effect=lambda d,r:gather_bounded(d,r,invoke=lambda task,end:_worker(*task))):
            rejected=gather(day,repo)
        self.assertEqual(rejected["day_source_coverage"]["authenticated_pc_slots"],0)

from tests.test_kyoto_impl31_auxiliary_priority import Aux
from tests.test_kyoto_impl31_independent_track_union import TrackUnion

if __name__=="__main__":unittest.main()
