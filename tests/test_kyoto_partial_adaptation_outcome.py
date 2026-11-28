import unittest,copy
from diagnostics.kyoto_partial_adaptation_outcome import review,partial_adoption,observed_counts,SAT,SUN,MODE,SOURCE_RUN,TIMES
def source(day):
    return {"state":"SOURCE_VERIFIED","sha256":"a"*64,"run_id":"42","utc":day[:4]+"-"+day[4:6]+"-"+day[6:]+"T01:00:00Z"}
def report(day,n):
    start=day[:4]+"-"+day[4:6]+"-"+day[6:]+"T03:00:00Z"
    races={str(r):{"state":"NO_VERIFIED_ROSTER"} for r in range(1,13)}
    for r in range(1,n+1):
        p=source(day)
        races[str(r)]={"state":"ROSTER_VERIFIED","start_utc":start,"racecard":p,"horses":{"1":{"profile":p},"2":{}},
            "paired_same_slot":True,"markets":{k:{**p,"cancelled_horses":[]} for k in ("quinella","bracket_quinella")}}
    return {"day":day,"day_source_coverage":{"schema":"kyoto_impl30_day_source_coverage.v1","day":day,"race_denominator":12,"authenticated_pc_slots":0,
        "races":races,"totals":{"racecards":n,"paired_same_slot_races":n,"registered_horses_known":2*n,"profile":n,"prior_form":0}}}
def policy(lane):
    return {"schema":"kyoto_nextday_applied_policy.v1","day":SUN,"channel":lane,"selected_policy":MODE,
        "reason":"AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_"+str(SOURCE_RUN),"pc_market_seconds":720,"sp_seconds":360,
        "observed_at_utc":"2026-11-29T00:18:00Z","source_coverage_proved":False,"improvement_proved":False}
def sunday():
    v=report(SUN,5)
    slots=[{"planned_utc":"2026-11-29T"+x+":00+00:00","state":"NOT_OBSERVED","matching_run_ids":[]} for x in TIMES]
    slots[0].update(state="COMPLETED",run_id=42,matching_run_ids=[42],pc_authenticated=True,sp_authenticated=True)
    v["external_dispatch_slot_ledger"]={"morning":{"schema":"kyoto_external_dispatch_observations.v1","day":SUN,"family":"morning","index_complete":True,"slots":slots}}
    v["authenticated_applied_policies"]=[{"run_id":42,"event":"workflow_dispatch","channel":lane,"policy":policy(lane)} for lane in ("PC","SP")]
    return v
class PartialOutcome(unittest.TestCase):
    def test_partial_adoption_and_coverage_without_pc_requirement(self):
        s=sunday();v=review(report(SAT,2),s,SOURCE_RUN,MODE)
        self.assertEqual(v["adoption"]["exact_bound_lanes"],2)
        self.assertEqual(v["adoption"]["expected_lanes"],8)
        self.assertEqual(v["observed_metrics"]["racecards"]["observed_delta"],3)
        self.assertEqual(v["after"]["counts"]["racecards"],5)
        self.assertNotIn("profile",v["observed_metrics"])
        self.assertFalse(v["full_acquisition_certified"]);self.assertFalse(v["causal_effect_proved"])
        self.assertEqual(v,review(report(SAT,2),s,SOURCE_RUN,MODE))
    def test_wrong_source_fallback_and_missing_are_distinct(self):
        s=sunday();s["authenticated_applied_policies"][0]["policy"]["reason"]="PRIMARY_TIMEOUT__NOV28_AUTHENTICATED_SOURCE_GAP_INCIDENT_141"
        s["authenticated_applied_policies"].pop()
        v=partial_adoption(s,SOURCE_RUN,MODE)
        self.assertEqual([r["state"] for r in v["rows"][:2]],["OTHER_OR_FALLBACK_POLICY","APPLIED_RECEIPT_NOT_VERIFIED"])
        self.assertEqual(v["exact_bound_lanes"],0)
    def test_duplicate_and_wrong_time_rejected(self):
        s=sunday();s["authenticated_applied_policies"].append(copy.deepcopy(s["authenticated_applied_policies"][0]))
        s["authenticated_applied_policies"][1]["policy"]["observed_at_utc"]="2026-11-29T00:16:00Z"
        v=partial_adoption(s,SOURCE_RUN,MODE)
        self.assertEqual([r["state"] for r in v["rows"][:2]],["APPLIED_RECEIPT_NOT_VERIFIED","APPLIED_RECEIPT_REJECTED"])
    def test_wrong_sha_time_and_counts_not_zero(self):
        for change in ("sha","time","count"):
            r=report(SUN,2)
            if change=="sha":r["day_source_coverage"]["races"]["1"]["racecard"]["sha256"]="bad"
            elif change=="time":r["day_source_coverage"]["races"]["1"]["racecard"]["utc"]="2026-11-29T03:00:00Z"
            else:r["day_source_coverage"]["totals"]["racecards"]=12
            self.assertIsNone(observed_counts(r,SUN)["counts"])
    def test_slot_collision_does_not_grant_credit(self):
        s=sunday();s["external_dispatch_slot_ledger"]["morning"]["slots"][1].update(state="COMPLETED",run_id=42,matching_run_ids=[42],pc_authenticated=True,sp_authenticated=True)
        self.assertEqual(partial_adoption(s,SOURCE_RUN,MODE)["exact_bound_lanes"],0)
