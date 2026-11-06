import unittest
from datetime import datetime,timezone,timedelta
from diagnostics.jra_p1_fb_request_budget_policy import Attempt,decision
T=datetime(2026,11,6,7,0,tzinfo=timezone.utc)
C=datetime(2026,11,7,tzinfo=timezone.utc)
PC="https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103507/A5"
SP="https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AA"
def make(primary="PC",status="PARSER_FAILED",saved=True):
    u=PC if primary=="PC" else SP
    return [Attempt(primary,u,T-timedelta(seconds=3),11,1,status,saved)]
def check(primary="PC",**changes):
    data={"failed_channel":primary,"failed_url":PC if primary=="PC" else SP,
      "backup_channel":"SP" if primary=="PC" else "PC",
      "backup_url":SP if primary=="PC" else PC,
      "race":11,"horse_number":1,"horse_name":"試験馬","roster_sha256":"a"*64,
      "observed_backup_link":True,"attempts":make(primary),
      "asof_utc":T,"cutoff_utc":C,"simulate_authorized":True}
    data.update(changes)
    return decision(**data)
class Budget(unittest.TestCase):
    def test_pc_to_sp_dry_run(self):self.assertEqual(check()["status"],"DRY_RUN_ELIGIBLE")
    def test_sp_to_pc_dry_run(self):self.assertEqual(check("SP")["status"],"DRY_RUN_ELIGIBLE")
    def test_never_live(self):self.assertFalse(check()["live_auto_fallback_authorized"])
    def test_disabled_by_default(self):self.assertEqual(check(simulate_authorized=False)["reason"],"experimental_only_not_authorized")
    def test_unproven_link(self):self.assertEqual(check(observed_backup_link=False)["reason"],"backup_link_not_proven_in_official_roster")
    def test_cutoff(self):self.assertEqual(check(asof_utc=C)["reason"],"prediction_cutoff_passed")
    def test_minimum_spacing(self):self.assertEqual(check(asof_utc=T-timedelta(seconds=2))["reason"],"minimum_two_seconds_not_elapsed")
    def test_saved_original_required(self):self.assertEqual(check(attempts=make(saved=False))["reason"],"primary_failure_not_preserved")
    def test_no_failed_http_repeat(self):
        attempts=make()+[Attempt("SP",SP,T-timedelta(seconds=2),11,1,"HTTP_FAILED",True)]
        self.assertEqual(check(attempts=attempts)["status"],"BLOCKED")
    def test_no_same_channel(self):self.assertEqual(check(backup_channel="PC")["reason"],"channel_not_distinct")
    def test_no_guessed_host(self):self.assertEqual(check(backup_url="https://example.com/JRADB/accessU.html?CNAME=guessed")["reason"],"not_verified_official_endpoint")
    def test_clock_without_timezone(self):self.assertEqual(check(asof_utc=datetime(2026,11,6))["reason"],"naive_clock")
    def test_no_successful_source_refetch(self):self.assertEqual(check(attempts=make(status="VALIDATED"))["reason"],"primary_failure_not_preserved")
    def test_http_failure_without_html_can_fallback_if_error_receipt_saved(self):
        self.assertEqual(check(attempts=make(status="HTTP_FAILED",saved=False))["status"],"DRY_RUN_ELIGIBLE")
    def test_http_failure_without_evidence_cannot_fallback(self):
        bad=Attempt("PC",PC,T-timedelta(seconds=3),11,1,"HTTP_FAILED",False,False)
        self.assertEqual(check(attempts=[bad])["reason"],"primary_failure_not_preserved")
    def test_roster_sha_must_be_hex(self):
        self.assertEqual(check(roster_sha256="z"*64)["reason"],"identity_provenance_missing")
if __name__=="__main__":unittest.main()
