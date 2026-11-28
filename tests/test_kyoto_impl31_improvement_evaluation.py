import unittest,copy
from diagnostics.kyoto_impl31_improvement_evaluation import evaluate,receipt,SAT,SUN
from diagnostics.kyoto_impl30_nextday_adaptation import POLICY
MODE="MARKET_OR_ROSTER_RECOVERY"
def report(day,paired,profiles=2,horses=2):
    races={str(i):{"state":"ROSTER_VERIFIED","racecard":{"state":"SOURCE_VERIFIED"},"paired_same_slot":i<=paired,
      "horses":{str(h):{"profile":{"state":"SOURCE_VERIFIED" if h<=profiles else "MISSING"},"prior_form":{"state":"SOURCE_VERIFIED"}} for h in range(1,horses+1)}} for i in range(1,13)}
    r={"day":day,"all_run_metadata_screened":True,"github_run_listing_complete":True,"day_source_coverage":{"schema":"kyoto_impl30_day_source_coverage.v1","day":day,"race_denominator":12,"authenticated_pc_slots":4,"unassessed_pc_slots":0,"races":races,"totals":{"racecards":12,"paired_same_slot_races":paired,"registered_horses_known":12*horses,"profile":12*profiles,"prior_form":12*horses}}}
    if day==SUN:
        r["scheduled_runs"]=[{"run":{"id":i}} for i in range(1,5)]
        r["authenticated_applied_policies"]=[{"run_id":i,"channel":c,"event":"schedule","policy":{"schema":"kyoto_nextday_applied_policy.v1","day":SUN,"channel":c,"selected_policy":MODE,"reason":"AUTHENTICATED_SATURDAY_HANDOFF_42","pc_market_seconds":720,"sp_seconds":360,"observed_at_utc":"2026-11-29T02:00:00Z","source_coverage_proved":False,"improvement_proved":False}} for i in range(1,5) for c in ("PC","SP")]
    return r
class Evaluation(unittest.TestCase):
    def test_improvement_not_causality(self):
        r=evaluate(report(SAT,4),report(SUN,8),MODE,42)
        self.assertEqual(r["status"],"OBSERVED_TARGET_IMPROVEMENT")
        self.assertEqual(r["metrics"]["paired_same_slot_races"]["before"],[4,12])
        self.assertFalse(r["causal_effect_proved"]);self.assertFalse(r["automatic_code_promotion_authorized"])
    def test_regression_even_when_target_improves(self):
        self.assertEqual(evaluate(report(SAT,4),report(SUN,8,1),MODE,42)["status"],"OBSERVED_REGRESSION_OR_TRADEOFF")
    def test_horse_denominator_normalized(self):
        r=evaluate(report(SAT,4,1,2),report(SUN,8,2,4),MODE,42)
        self.assertEqual(r["metrics"]["profile"]["direction"],"UNCHANGED")
    def test_incomplete_or_wrong_counts(self):
        for field,value in (("all_run_metadata_screened",False),("github_run_listing_complete",False)):
            r=report(SUN,8);r[field]=value
            self.assertEqual(evaluate(report(SAT,4),r,MODE,42)["status"],"INSUFFICIENT_EVIDENCE")
        r=report(SUN,8);r["day_source_coverage"]["totals"]["profile"]+=1
        self.assertEqual(evaluate(report(SAT,4),r,MODE,42)["status"],"INSUFFICIENT_EVIDENCE")
    def test_mixed_or_missing_policy(self):
        r=report(SUN,8);r["authenticated_applied_policies"][0]["policy"]["reason"]="FALLBACK"
        self.assertEqual(evaluate(report(SAT,4),r,MODE,42)["status"],"MIXED_OR_UNBOUND_POLICY")
        r["authenticated_applied_policies"].pop()
        self.assertEqual(evaluate(report(SAT,4),r,MODE,42)["status"],"INSUFFICIENT_EVIDENCE")
    def test_invalid_receipt(self):
        r=report(SUN,8)["authenticated_applied_policies"][0]["policy"]
        for field,value in (("sp_seconds",999),("observed_at_utc","2026-11-28T02:00:00Z"),("improvement_proved",True)):
            x=dict(r);x[field]=value
            with self.assertRaises(ValueError):receipt(x,"PC")
    def test_dispatch_slots_and_policy_without_native_denominator(self):
        from diagnostics.kyoto_impl39_dispatch_slots import observe,PLAN
        def make(day,pairs):
            r=report(day,pairs)
            r["all_run_metadata_screened"]=False
            r["day_source_coverage"]["unassessed_pc_slots"]=2
            iso="2026-11-"+day[-2:]
            entries=[{"run":{"id":i,"event":"workflow_dispatch","head_branch":"main","status":"completed","created_at":iso+"T"+t+":01Z"},"source_assessment":{c:{"ciphertext_authenticated":True,"source_original_sha_utc_checked":True} for c in ("PC","SP")}} for i,t in enumerate(PLAN[day],1)]
            r["external_dispatch_slot_ledger"]={"morning":observe(day,entries,complete=True)}
            for x in r.get("authenticated_applied_policies",[]):
                x["event"]="workflow_dispatch";x["policy"]["reason"]="AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_42"
            return r,entries
        sat,_=make(SAT,4);sun,entries=make(SUN,8)
        result=evaluate(sat,sun,MODE,42)
        self.assertEqual(result["status"],"OBSERVED_TARGET_IMPROVEMENT")
        self.assertEqual(result["evaluated_launch_event"],"workflow_dispatch")
        self.assertFalse(sun["external_dispatch_slot_ledger"]["morning"]["provider_proved"])
        duplicate=copy.deepcopy(entries[0]);duplicate["run"]["id"]=55
        sun["external_dispatch_slot_ledger"]["morning"]=observe(SUN,entries+[duplicate],complete=True)
        self.assertEqual(evaluate(sat,sun,MODE,42)["status"],"INSUFFICIENT_EVIDENCE")
        sun["external_dispatch_slot_ledger"]["morning"]=observe(SUN,entries[:-1],complete=True)
        self.assertEqual(evaluate(sat,sun,MODE,42)["status"],"INSUFFICIENT_EVIDENCE")
    def test_no_improvement(self):
        self.assertEqual(evaluate(report(SAT,4),report(SUN,4),MODE,42)["status"],"NO_OBSERVED_TARGET_IMPROVEMENT")
if __name__=="__main__":unittest.main()
