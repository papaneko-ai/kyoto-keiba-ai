"""Deterministic tests: never substitute byte size for measured speed."""
import unittest
from diagnostics.jra_source_router import (
    SourceEvidence, decide, source_bytes_comparison, SourceRoutingError
)

ROWS=((1,1,"モンドプリューム"),(2,1,"エティエンヌ"),(3,2,"エコロレーヴ"))
FIELDS=frozenset(("race_id","horse_number","horse_name","frame_number","profile_link"))
SHA="a"*64

def evidence(channel="PC", **updates):
    d=dict(channel=channel,race_key="2026-11-07-KYOTO-11R",
      captured_at_utc="2026-11-06T03:47:00Z",content_sha256=SHA,
      rows=ROWS,fields_verified=FIELDS,parse_errors=(),scratches_verified=False,
      independent_checks=0,latency_ms_samples=(),observed_bytes=232708,
      response_verified=True)
    d.update(updates)
    return SourceEvidence(**d)

class TestRouting(unittest.TestCase):
    def test_only_pc_baseline(self):
        r=decide(evidence(),None)
        self.assertEqual((r["state"],r["preferred_source"]),("CANDIDATE","PC"))
    def test_no_unverified_source(self):
        r=decide(None,None)
        self.assertEqual(r["state"],"BLOCK")
    def test_sp_one_comparison_not_enough(self):
        r=decide(evidence(),evidence("SP",observed_bytes=128691))
        self.assertEqual(r["preferred_source"],"PC")
    def test_smaller_html_not_proof_of_speed(self):
        r=source_bytes_comparison(232708,128691)
        self.assertEqual(r["sp_reduction_pct"],44.7)
        self.assertFalse(r["latency_improvement_proven"])
    def test_sp_wins_only_with_timing_and_repeat_evidence(self):
        pc=evidence(latency_ms_samples=(220,220,220,250,230))
        sp=evidence("SP",latency_ms_samples=(120,130,140,125,145),
            independent_checks=3,observed_bytes=128691)
        r=decide(pc,sp,successful_sp_crosschecks=3)
        self.assertEqual((r["state"],r["preferred_source"]),("CANDIDATE","SP"))
    def test_latency_insufficient(self):
        pc=evidence(latency_ms_samples=(100,)*5)
        sp=evidence("SP",latency_ms_samples=(92,)*5,independent_checks=3)
        self.assertEqual(decide(pc,sp,successful_sp_crosschecks=3)["preferred_source"],"PC")
    def test_names_conflict_blocks(self):
        sp=evidence("SP",rows=((1,1,"別馬"),)+ROWS[1:])
        self.assertEqual(decide(evidence(),sp)["state"],"RECHECK")
    def test_race_conflict_blocks(self):
        sp=evidence("SP",race_key="2026-11-07-KYOTO-10R")
        self.assertEqual(decide(evidence(),sp)["state"],"BLOCK")
    def test_time_gap_recheck(self):
        sp=evidence("SP",captured_at_utc="2026-11-06T05:00:00Z")
        self.assertEqual(decide(evidence(),sp)["state"],"RECHECK")
    def test_bad_sp_does_not_poison_pc(self):
        sp=evidence("SP",response_verified=False)
        self.assertEqual(decide(evidence(),sp)["preferred_source"],"PC")
    def test_sp_only_requires_crosschecks(self):
        sp=evidence("SP",independent_checks=3)
        self.assertEqual(decide(None,sp,successful_sp_crosschecks=0)["state"],"RECHECK")
        self.assertEqual(decide(None,sp,successful_sp_crosschecks=3)["state"],"PROVISIONAL")
    def test_cancellation_gate(self):
        p=evidence(scratches_verified=False)
        s=evidence("SP",scratches_verified=False)
        self.assertEqual(decide(p,s,require_scratches=True)["state"],"RECHECK")
    def test_prediction_always_blocked(self):
        for a,b in ((evidence(),None),(None,evidence("SP")),(evidence(),evidence("SP"))):
            r=decide(a,b,successful_sp_crosschecks=99)
            self.assertFalse(r["prediction_ready"])
            self.assertFalse(r["training_ready"])
    def test_reject_duplicate_and_noncontiguous_numbers(self):
        self.assertFalse(evidence(rows=(ROWS[0],ROWS[0])).valid())
        self.assertFalse(evidence(rows=(ROWS[0],ROWS[2])).valid())
    def test_invalid_channel(self):
        with self.assertRaises(SourceRoutingError):
            decide(evidence("SP"),None)
    def test_nondeterministic_clock_excluded(self):
        a=decide(evidence(),evidence("SP"))
        self.assertEqual(a,decide(evidence(),evidence("SP")))
if __name__=="__main__":
    unittest.main()
