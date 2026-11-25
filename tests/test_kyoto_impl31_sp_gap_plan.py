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
if __name__=="__main__":unittest.main()
