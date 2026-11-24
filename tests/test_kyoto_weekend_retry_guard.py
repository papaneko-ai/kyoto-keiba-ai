"""Source-opportunity-first retry regression; prior run never a blanket veto."""
import unittest
from diagnostics.kyoto_weekend_retry_guard import evaluate,RetryGuardRejected,EARLY,PRIMARY,BACKUP

DAY="20261121"
def prior(conclusion="failure",status="completed",event="schedule",ident=100):
    return {"id":ident,"conclusion":conclusion,"status":status,"event":event}

class OpportunityFirstRetryTests(unittest.TestCase):
 def check(self,runs=None,day=DAY,cron=None,event="schedule"):
    return evaluate(day,101,event,cron if cron is not None else BACKUP[day],
                    [] if runs is None else runs,{})
 def test_all_eight_scheduled_windows_are_permitted(self):
    for day in ("20261121","20261122","20261128","20261129"):
        for cron in (*EARLY[day],PRIMARY[day],BACKUP[day]):
            with self.subTest(day=day,cron=cron):
                status=self.check(day=day,cron=cron)
                self.assertIn("ALLOWED",status)
 def test_prior_run_never_blocks_early_slots(self):
    for day in ("20261121","20261122","20261128","20261129"):
        for cron in EARLY[day]:
            with self.subTest(day=day,cron=cron):
                self.assertEqual(self.check([prior(conclusion="success")],day=day,cron=cron),
                                 "EARLY_OBSERVATION_ALLOWED_INDEPENDENT_OF_PRIOR_RUN")
 def test_primary_fires_without_prior_run(self):
    self.assertEqual(self.check(cron=PRIMARY[DAY]),"PRIMARY_ALLOWED_INDEPENDENT_OF_PRIOR_RUN")
 def test_missing_primary_does_not_block_backup(self):
    self.assertEqual(self.check(),"BACKUP_ALLOWED_MISSING_PRIMARY")
 def test_previous_pre_http_failure_allows_backup(self):
    self.assertEqual(self.check([prior()]),"BACKUP_ALLOWED_AFTER_PRIOR_RUN")
 def test_previous_attempted_http_failure_still_allows_backup(self):
    self.assertEqual(self.check([prior(conclusion="failure")]),"BACKUP_ALLOWED_AFTER_PRIOR_RUN")
 def test_previous_actions_success_without_authenticated_markets_allows_backup(self):
    self.assertEqual(self.check([prior(conclusion="success")]),"BACKUP_ALLOWED_AFTER_PRIOR_RUN")
 def test_previous_cancelled_allows_backup(self):
    self.assertEqual(self.check([prior(conclusion="cancelled")]),"BACKUP_ALLOWED_AFTER_PRIOR_RUN")
 def test_missing_jobs_metadata_does_not_waste_backup(self):
    self.assertEqual(self.check([prior()]),"BACKUP_ALLOWED_AFTER_PRIOR_RUN")
 def test_prior_manual_run_does_not_block_the_scheduled_backup(self):
    self.assertEqual(self.check([prior(event="workflow_dispatch")]),"BACKUP_ALLOWED_AFTER_PRIOR_RUN")
 def test_manual_recovery_can_use_explicit_authorization(self):
    self.assertEqual(self.check([prior()],event="workflow_dispatch",cron=""),
                     "MANUAL_AUTHORIZED_RETRY_ALLOWED")
 def test_multiple_prior_attempts_do_not_create_false_success(self):
    self.assertEqual(self.check([prior(ident=90),prior(ident=91)]),"BACKUP_ALLOWED_AFTER_PRIOR_RUN")
 def test_primary_late_arrival_does_not_misclassify_itself_as_backup(self):
    self.assertEqual(self.check([prior()],cron=PRIMARY[DAY]),"PRIMARY_ALLOWED_INDEPENDENT_OF_PRIOR_RUN")
 def test_day22_retry_does_not_depend_on_day21(self):
    self.assertEqual(self.check([prior()],day="20261122"),"BACKUP_ALLOWED_AFTER_PRIOR_RUN")
 def test_unapproved_cron_is_rejected(self):
    with self.assertRaisesRegex(RetryGuardRejected,"UNEXPECTED_CRON"):
        self.check(cron="17 1 21 11 *")
 def test_unsupported_day_rejected(self):
    with self.assertRaisesRegex(RetryGuardRejected,"RUN_HISTORY_UNVERIFIED"):
        self.check(day="20261120",cron="")
 def test_invalid_event_rejected(self):
    with self.assertRaisesRegex(RetryGuardRejected,"INVALID_EVENT"):
        self.check(event="push")
 def test_nonlist_history_rejected(self):
    with self.assertRaisesRegex(RetryGuardRejected,"RUN_HISTORY_UNVERIFIED"):
        evaluate(DAY,101,"schedule",BACKUP[DAY],None,{})
 def test_unbounded_history_rejected(self):
    with self.assertRaisesRegex(RetryGuardRejected,"SAME_DAY_HISTORY_NEEDS_PAGINATION"):
        self.check([prior(ident=i) for i in range(101)])
if __name__=="__main__":
 unittest.main()
