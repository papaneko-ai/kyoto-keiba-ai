"""No-JRA network destructive tests for backup schedule and replay protection."""
import unittest
from diagnostics.kyoto_weekend_retry_guard import evaluate,RetryGuardRejected,PRIMARY,BACKUP
DAY="20261121"
def prior(ident=100,conclusion="failure",status="completed",event="schedule"):
    return {"id":ident,"status":status,"conclusion":conclusion,"event":event}
def jobs(pc="skipped",sp="skipped"):
    return [{"status":"completed","steps":[
        {"name":"Offline regression mandatory before any live HTTP","conclusion":"failure"},
        {"name":"Capture official PC observed originals (bounded no guessed URLs)","conclusion":pc}]},
        {"status":"completed","steps":[
        {"name":"Independently verified SP link, otherwise record zero-request stop","conclusion":sp}]}]
class BackupGuardTests(unittest.TestCase):
 def check(self,runs=None,lookup=None,event="schedule",cron=None,day=DAY):
    return evaluate(day,101,event,cron or BACKUP[day],runs if runs is not None else [],
                    lookup if lookup is not None else {})
 def test_primary_first_run(self):
    self.assertEqual(self.check(cron=PRIMARY[DAY]),"PRIMARY_ALLOWED")
 def test_backup_if_primary_never_started(self):
    self.assertEqual(self.check(),"BACKUP_ALLOWED_NO_PRIMARY_RUN")
 def test_backup_after_failed_pre_http_primary(self):
    self.assertEqual(self.check([prior()],{100:jobs()}),"BACKUP_ALLOWED_VERIFIED_PRE_HTTP_STOP")
 def test_backup_after_cancelled_before_capture(self):
    self.assertEqual(self.check([prior(conclusion="cancelled")],{100:jobs()}),
                     "BACKUP_ALLOWED_VERIFIED_PRE_HTTP_STOP")
 def test_backup_after_failed_pc_capture_blocked(self):
    with self.assertRaisesRegex(RetryGuardRejected,"PREVIOUS_CAPTURE_ATTEMPTED"):
        self.check([prior()],{100:jobs(pc="failure")})
 def test_backup_after_any_sp_capture_blocked(self):
    with self.assertRaisesRegex(RetryGuardRejected,"PREVIOUS_CAPTURE_ATTEMPTED"):
        self.check([prior()],{100:jobs(sp="success")})
 def test_running_primary_blocked(self):
    with self.assertRaisesRegex(RetryGuardRejected,"PREVIOUS_WORKFLOW_RUN"):
        self.check([prior(status="in_progress",conclusion=None)],{100:jobs()})
 def test_previous_success_blocked(self):
    with self.assertRaisesRegex(RetryGuardRejected,"PREVIOUS_WORKFLOW_RUN"):
        self.check([prior(conclusion="success")],{100:jobs()})
 def test_manual_previous_run_not_automatically_replayed(self):
    with self.assertRaisesRegex(RetryGuardRejected,"PREVIOUS_WORKFLOW_RUN"):
        self.check([prior(event="workflow_dispatch")],{100:jobs()})
 def test_second_manual_attempt_blocked(self):
    with self.assertRaisesRegex(RetryGuardRejected,"PREVIOUS_WORKFLOW_RUN"):
        self.check([prior()],{100:jobs()},event="workflow_dispatch")
 def test_primary_not_retried_by_extra_run(self):
    with self.assertRaisesRegex(RetryGuardRejected,"PREVIOUS_WORKFLOW_RUN"):
        self.check([prior()],{100:jobs()},cron=PRIMARY[DAY])
 def test_missing_job_evidence_is_not_assumed_pre_http(self):
    with self.assertRaisesRegex(RetryGuardRejected,"RUN_HISTORY_UNVERIFIED"):
        self.check([prior()],{})
 def test_missing_step_list_blocks(self):
    with self.assertRaisesRegex(RetryGuardRejected,"RUN_HISTORY_UNVERIFIED"):
        self.check([prior()],{100:[{"status":"completed"}]})
 def test_unknown_capture_conclusion_blocks(self):
    with self.assertRaisesRegex(RetryGuardRejected,"PREVIOUS_CAPTURE_ATTEMPTED"):
        self.check([prior()],{100:jobs(pc=None)})
 def test_wrong_schedule_expression_blocks(self):
    with self.assertRaisesRegex(RetryGuardRejected,"UNEXPECTED_CRON"):
        self.check(cron="0 1 21 11 *")
 def test_day22_backup_is_independent(self):
    self.assertEqual(self.check(day="20261122"),"BACKUP_ALLOWED_NO_PRIMARY_RUN")
    self.assertEqual(self.check(day="20261122",runs=[prior()],lookup={100:jobs()}),
                     "BACKUP_ALLOWED_VERIFIED_PRE_HTTP_STOP")
 def test_capture_not_reached_even_if_runner_failed_during_setup(self):
    self.assertEqual(self.check([prior()],{100:[{"status":"completed","steps":[
        {"name":"Setup Python","conclusion":"failure"}]}]}),
        "BACKUP_ALLOWED_VERIFIED_PRE_HTTP_STOP")
if __name__=="__main__":
 unittest.main()
