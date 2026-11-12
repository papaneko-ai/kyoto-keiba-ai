"""Historic real JRA 12-race pre-race snapshot audit, destructive tests offline."""
import copy,json
import unittest
from diagnostics.kyoto_p1_saved_real_prerace_roster_reaudit import (
    DOC,file_for,inspect_day,RosterAuditRejected
)

class HistoricRealPreraceRosterTests(unittest.TestCase):
 def source(self):
    return {file_for(r):file_for(r).read_bytes() for r in range(1,13)} | {
        DOC/"JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json":
        (DOC/"JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json").read_bytes()}
 def inspected(self,change):
    source=self.source()
    path=file_for(1)
    r=json.loads(source[path])
    change(r)
    source[path]=json.dumps(r,ensure_ascii=False).encode()
    return inspect_day(read=lambda p:source[p])
 def test_original_12r_148_real_prerace_readback(self):
    r=inspect_day()
    self.assertEqual(r["races_checked"],12)
    self.assertEqual(r["runners_checked"],148)
    self.assertEqual(r["prior_race_dates_checked"],396)
    self.assertFalse(r["F03_fixed_gate_accepted"])
    self.assertFalse(r["F04_fixed_gate_accepted"])
 def test_determinism(self):
    self.assertEqual(inspect_day(),inspect_day())
 def test_unique_source_sha(self):
    r=inspect_day()
    self.assertEqual(len({x["source_sha256"] for x in r["snapshot_sources"]}),12)
 def test_original_bytes_not_misrepresented(self):
    r=inspect_day()
    self.assertFalse(r["original_html_bytes_independently_verified_here"])
 def test_real_liveness_never_forged(self):
    r=inspect_day()
    self.assertFalse(r["ready_for_prediction"])
    self.assertFalse(r["real_paper_trade_registered"])
    self.assertTrue(r["no_new_JRA_network_requests"])
 def test_wrong_race_date_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r.update(race_date="2026-11-06"))
 def test_wrong_venue_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r.update(venue="TOKYO"))
 def test_runner_drop_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r["runners"].pop())
 def test_runner_count_forge_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r.update(runner_count=11))
 def test_duplicate_runner_number_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r["runners"][1].update(horse_number=1))
 def test_duplicate_horse_name_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r["runners"][1].update(horse_name=r["runners"][0]["horse_name"]))
 def test_frame_out_of_bounds_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r["runners"][0].update(frame_number=9))
 def test_past_race_future_leakage_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r["runners"][0].update(past_race_dates=["2026-11-15"]))
 def test_fake_sha_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r.update(source_sha256="fake"))
 def test_missing_timestamp_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r.pop("captured_at_utc"))
 def test_post_off_timestamp_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r.update(captured_at_utc="2026-11-07T04:00:00+00:00"))
 def test_parser_errors_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r.update(parse_errors=["problem"]))
 def test_fake_prediction_ready_rejected(self):
    with self.assertRaises(RosterAuditRejected):self.inspected(lambda r:r.update(prediction_ready=True))
 def test_baseline_bait_detected(self):
    src=self.source();p=DOC/"JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json"
    obj=json.loads(src[p]);obj["html_bytes_independently_verified_by_ci"]=True
    src[p]=json.dumps(obj).encode()
    with self.assertRaises(RosterAuditRejected):
        inspect_day(read=lambda path:src[path])
 def test_new_horse_race_has_zero_histories(self):
    r=inspect_day()
    self.assertEqual(r["snapshot_sources"][4]["prior_dates_count"],0)
    self.assertEqual(r["snapshot_sources"][5]["prior_dates_count"],0)
if __name__=="__main__":unittest.main()
