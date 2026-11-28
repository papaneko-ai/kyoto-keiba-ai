import unittest
from datetime import datetime,timezone
from diagnostics.kyoto_impl31_sp_gap_plan import plan_from_pc,feedback
DAY="20261129";NOW=datetime(2026,11,29,1,0,tzinfo=timezone.utc)
def pc():
    def row(h,m,pair):return {"racecard":{"sha256":"a"*64,"utc":"2026-11-29T00:30:00Z"},"start_utc":f"2026-11-29T{h:02d}:{m:02d}:00Z","paired_same_slot":pair}
    return {"ciphertext_authenticated":True,"source_original_sha_utc_checked":True,"day_coverage_slot":{"day":DAY,"run_id":"42","races":{"1":row(0,50,False),"2":row(1,30,True),"3":row(2,0,False),"4":row(1,45,False)}}}
class GapPlan(unittest.TestCase):
    def test_gap_first_then_unknown_then_existing_pair_and_elapsed(self):
        p=plan_from_pc(pc(),DAY,42,NOW)
        self.assertEqual(p["mode"],"GAP_FIRST");self.assertEqual(p["race_order"][:2],[4,3])
        self.assertEqual(p["race_order"][-2:],[2,1]);self.assertEqual(sorted(p["race_order"]),list(range(1,13)))
    def test_same_day_previous_failed_target_uses_start_order(self):
        prior={"day":DAY,"mode":"GAP_FIRST","window_seconds":180,"measured_targets":{"3":{"cutoff_utc":"2026-11-29T01:50:00+00:00","outcome":"NO_PAIR_WITHIN_WINDOW"}}}
        p=plan_from_pc(pc(),DAY,42,NOW,prior)
        self.assertEqual(p["mode"],"START_FIRST");self.assertEqual(p["race_order"][:3],[2,4,3])
        prior["mode"]="START_FIRST";self.assertEqual(plan_from_pc(pc(),DAY,42,NOW,prior)["mode"],"BASELINE")
        prior["day"]="20261128";self.assertEqual(plan_from_pc(pc(),DAY,42,NOW,prior)["mode"],"GAP_FIRST")
    def test_wrong_identity_not_applied(self):
        x=pc();x["ciphertext_authenticated"]=False
        self.assertIsNone(plan_from_pc(x,DAY,42,NOW))
        self.assertIsNone(plan_from_pc(pc(),DAY,99,NOW))
    def test_raw_pair_and_failure_are_bound_to_target_window(self):
        p=plan_from_pc(pc(),DAY,42,NOW)
        rows=[]
        for n,names in [(3,["racecard","quinella_odds","bracket_quinella_odds"]),(4,["racecard"])]:
            for name in names:rows.append({"filename":f"r{n:02d}_official_sp_{name}.html","captured_at_utc":"2026-11-29T01:01:00Z"})
        post={"source_rows":rows,"sp_race_integrity":{"3":{"state":"DIGEST_UTC_CHECKED_ONLY","both_market_originals_verified_bytes":True},"4":{"state":"DIGEST_UTC_CHECKED_ONLY","both_market_originals_verified_bytes":False}}}
        result=feedback(p,{"observed_http_requests_started":7},post,DAY,42)
        self.assertEqual(result["raw_pair_recovered_races"],[3]);self.assertEqual(result["comparable_failed_races"],[4])
        self.assertFalse(result["official_market_success_claimed"])
        rows[-1]["captured_at_utc"]="2026-11-29T02:10:00Z"
        result=feedback(p,{},post,DAY,42);self.assertEqual(result["unknown_races"],[4]);self.assertEqual(result["comparable_failed_races"],[])
    def test_compare_same_targets_and_window_only(self):
        p=plan_from_pc(pc(),DAY,42,NOW,{"day":DAY,"mode":"GAP_FIRST","window_seconds":180,"measured_targets":{"3":{"cutoff_utc":"2026-11-29T01:50:00+00:00","outcome":"NO_PAIR_WITHIN_WINDOW"},"4":{"cutoff_utc":"2026-11-29T01:20:00+00:00","outcome":"PAIR_WITHIN_WINDOW"}}})
        post={"source_rows":[{"filename":f"r03_official_sp_{name}.html","captured_at_utc":"2026-11-29T01:01:00Z"} for name in ("racecard","quinella_odds","bracket_quinella_odds")],"sp_race_integrity":{"3":{"state":"DIGEST_UTC_CHECKED_ONLY","both_market_originals_verified_bytes":True}}}
        r=feedback(p,{"observed_http_requests_started":9},post,DAY,42)
        self.assertEqual(r["compared_races"],[3]);self.assertEqual(r["comparison"],"OBSERVED_IMPROVEMENT")
        self.assertEqual((r["before_pairs"],r["after_pairs"]),(0,1))
        self.assertEqual(r["request_count"],9)
        self.assertFalse(r["causal_effect_proved"])
    def test_actual_sp_batch_respects_order_without_changing_links(self):
        import tempfile,hashlib,json
        from pathlib import Path
        from unittest.mock import patch,Mock
        from diagnostics.kyoto_sp_all12_observed_capture import capture_all
        from diagnostics.kyoto_weekend_sp_discovery import SEED
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);url=lambda n:f"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race{n:02d}{DAY}%2FAA"
            raw=("<html>"+''.join(f'<a href="{url(n)}">京都 {n}R</a>' for n in range(1,13))+"</html>").encode("cp932")
            (root/"official_sp_discovery_1.html").write_bytes(raw)
            (root/"sp_discovery_receipt.json").write_text(json.dumps({"day":DAY,"attempts":[{"url":SEED,"file":"official_sp_discovery_1.html","sha256":hashlib.sha256(raw).hexdigest()}]}))
            order=plan_from_pc(pc(),DAY,42,NOW)["race_order"];called=[]
            def fetch(out,*,race_number,source_url,**kw):
                self.assertEqual(source_url,url(race_number));called.append(race_number);return {"state":"CAPTURED"}
            with patch("diagnostics.kyoto_sp_all12_observed_capture.capture_verified_sp_seed",side_effect=fetch):
                capture_all(root,day=DAY,opener=object(),pacer=Mock(),race_order=order)
            self.assertEqual(called,order)
    def test_next_slot_reads_authenticated_prior_archive_and_switches(self):
        import hashlib,json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence
        from diagnostics.kyoto_weekend_day21_artifact_triage import assess_lane
        from diagnostics.kyoto_weekend_postflight import check_originals
        from diagnostics.kyoto_impl31_sp_gap_plan import get_plan
        from diagnostics.kyoto_impl25_c12_all_runs_handoff import WEEKENDS
        repo="papaneko-ai/kyoto-keiba-ai";key="ab"*32
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"raw";root.mkdir()
            raw=b"discovery";name="official_sp_discovery_1.html";(root/name).write_bytes(raw)
            stamp="2026-11-29T01:01:00Z"
            (root/"sp_discovery_receipt.json").write_text(json.dumps({"day":DAY,"not_pc_derived":True,"attempts":[{"file":name,"sha256":hashlib.sha256(raw).hexdigest(),"captured_at_utc":stamp}]}))
            raw=b"observed racecard";(root/"r04_official_sp_racecard.html").write_bytes(raw)
            (root/"r04_sp_receipt.json").write_text(json.dumps({"day":DAY,"channel":"SP","race_number":4,"local_target_race_key":"KYOTO:"+DAY+":04","racecard_fetched":True,"racecard_sha256":hashlib.sha256(raw).hexdigest(),"racecard_captured_at_utc":stamp}))
            first=plan_from_pc(pc(),DAY,42,NOW)
            (root/"receipt.json").write_text(json.dumps({"day":DAY,"channel":"SP","sp_gap_plan":first,"observed_http_requests_started":3}))
            (root/"source_verification.json").write_text(json.dumps(check_originals(root,day=DAY,channel="SP")))
            sealed=Path(tmp)/"sealed"
            with patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY",DAY):
                encrypt_evidence(root,sealed,key_hex=key,repo=repo,run_id="42")
                previous=assess_lane(sealed,day=DAY,channel="SP",key=key,repo=repo,run_id="42")
            self.assertTrue(previous["ciphertext_authenticated"]);self.assertEqual(previous["sp_gap_feedback"]["comparable_failed_races"],[4])
            current=pc();current["day_coverage_slot"]["run_id"]="43"
            workflow,filename,_=WEEKENDS[DAY]
            def run(i,when,status):
                return {"id":i,"name":workflow,"path":".github/workflows/"+filename,"head_repository":{"full_name":repo},"head_branch":"main","created_at":when,"status":status,"event":"schedule"}
            calls=[]
            def invoke(task,end):
                calls.append((task,end))
                if task[0]=="index":return {"total_count":2,"workflow_runs":[run(42,"2026-11-29T00:45:00Z","completed"),run(43,"2026-11-29T01:05:00Z","in_progress")]}
                return current if task[3]==43 else previous
            later=datetime(2026,11,29,1,10,tzinfo=timezone.utc)
            selected=get_plan(DAY,repo,43,deadline=340,clock=lambda:100,wall=lambda:later,invoke=invoke)
            self.assertEqual(selected["mode"],"START_FIRST")
            self.assertEqual(selected["previous_same_day_failed_targets"],[4])
            self.assertEqual(len(calls),3);self.assertTrue(all(end==112 for _,end in calls))
            # Replay the SAME encrypted prior evidence under actual dispatch
            # run-name metadata, without creating a second source fixture.
            calls.clear()
            def dispatch_invoke(task,end):
                if task[0]=="index":
                    rows=[run(42,"2026-11-29T00:45:00Z","completed"),run(43,"2026-11-29T01:05:00Z","in_progress")]
                    for row in rows:row.update(event="workflow_dispatch",name="workflow_dispatch")
                    calls.append((task,end))
                    return {"total_count":2,"workflow_runs":rows}
                return invoke(task,end)
            selected=get_plan(DAY,repo,43,deadline=340,clock=lambda:100,wall=lambda:later,invoke=dispatch_invoke)
            self.assertEqual(selected["mode"],"START_FIRST")
            self.assertEqual(selected["previous_same_day_failed_targets"],[4])
            self.assertEqual(len(calls),3);self.assertTrue(all(end==112 for _,end in calls))
            # A newer completed safe-stop with no original must not suppress
            # a prior authenticated dispatch. A mismatched run ID cannot vote.
            def mixed(task,end,*,wrong=False,untrusted=False):
                if task[0]=="index":
                    rows=[run(42,"2026-11-29T00:45:00Z","completed"),run(44,"2026-11-29T00:55:00Z","completed"),run(43,"2026-11-29T01:05:00Z","in_progress")]
                    for row in rows:row.update(event="workflow_dispatch",name="workflow_dispatch")
                    rows[1]["event"]="schedule";rows[1]["name"]="kyoto-native:15 0 29 11 *"
                    if untrusted:rows[0]["head_branch"]="other"
                    return {"total_count":3,"workflow_runs":rows}
                if task[3]==44:raise TimeoutError("newer native evidence unavailable")
                if task[3]==43:return current
                if wrong:return {**previous,"sp_gap_feedback":{**previous["sp_gap_feedback"],"run_id":"99"}}
                return previous
            for opts,mode in (({},"START_FIRST"),({"wrong":True},"GAP_FIRST"),({"untrusted":True},"GAP_FIRST")):
                selected=get_plan(DAY,repo,43,deadline=340,clock=lambda:100,wall=lambda:later,invoke=lambda t,e:mixed(t,e,**opts))
                self.assertEqual(selected["mode"],mode)
            # No prior lookup or artifact absence can prevent baseline SP work.
            self.assertIsNone(get_plan(DAY,repo,43,deadline=340,clock=lambda:100,wall=lambda:later,invoke=lambda t,e:{"error_class":"TIMEOUT"}))
if __name__=="__main__":unittest.main()
