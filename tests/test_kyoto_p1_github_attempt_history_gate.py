"""Never consume a trial for a provably pre-GET failure, never guess a retry."""
import unittest
from diagnostics.kyoto_p1_github_attempt_history_gate import (
    audit_previous_runs,was_proven_zero_http,AttemptLedgerRejected)
NAME="Kyoto Nov15 gated official links observation encrypted originals"
STEP="Up to TWO bounded observed official PC GET requests"
def run(id,status="completed",conclusion="failure",name=NAME):
 return {"id":id,"status":status,"conclusion":conclusion,"name":name}
def jobs(status="completed",conclusion="skipped",step=STEP):
 return [{"status":status,"steps":[{"name":step,"conclusion":conclusion}]}]
def mock_api(previous,previous_jobs):
 def get(url):
    if "/jobs?" in url:return {"jobs":previous_jobs,"total_count":len(previous_jobs)}
    if "page=1" in url:return {"workflow_runs":[run(22),previous]}
    return {"workflow_runs":[]}
 return get
class AttemptHistoryTests(unittest.TestCase):
 def audit(self,prior=None,j=None,api=None):
    return audit_previous_runs(repo="papaneko-ai/kyoto-keiba-ai",token="synthetic",
          branch="jra-html-diagnostic-20261105",current_run_id="22",
          workflow_name=NAME,http_step=STEP,
          api_fetch=api or mock_api(prior or run(11),j or jobs()))
 def test_known_zero_http_failure_retry_allowed(self):
    out=self.audit()
    self.assertEqual(out["prior_zero_http_runs"],[11])
    self.assertFalse(out["prior_HTTP_possible"])
 def test_prior_failed_http_step_consumed(self):
    with self.assertRaisesRegex(AttemptLedgerRejected,"prior_HTTP_possible"):
        self.audit(j=jobs(conclusion="failure"))
 def test_prior_success_http_step_consumed(self):
    with self.assertRaisesRegex(AttemptLedgerRejected,"prior_HTTP_possible"):
        self.audit(j=jobs(conclusion="success"))
 def test_prior_in_progress_unretriable(self):
    with self.assertRaisesRegex(AttemptLedgerRejected,"prior_HTTP_possible"):
        self.audit(prior=run(11,"in_progress",None))
 def test_prior_cancelled_before_get_safe_if_skipped(self):
    out=self.audit(prior=run(11,"completed","cancelled"))
    self.assertEqual(out["prior_zero_http_runs"],[11])
 def test_failed_no_step_unknown_must_block(self):
    with self.assertRaisesRegex(AttemptLedgerRejected,"prior_HTTP_possible"):
        self.audit(j=jobs(step="different"))
 def test_missing_job_unknown_must_block(self):
    with self.assertRaisesRegex(AttemptLedgerRejected,"prior_HTTP_possible"):
        self.audit(j=[{"status":"completed","steps":[]}])
 def test_missing_current_run_unverifiable(self):
    def get(url):
        if "page=1" in url:return {"workflow_runs":[run(11)]}
        return {"workflow_runs":[]}
    with self.assertRaisesRegex(AttemptLedgerRejected,"current_run_or_full_history"):
        self.audit(api=get)
 def test_bad_api_pagination_refuses(self):
    def get(url):
        if "/jobs?" in url:return {"jobs":jobs(),"total_count":3}
        return {"workflow_runs":[run(22),run(11)]}
    with self.assertRaisesRegex(AttemptLedgerRejected,"prior_jobs_pagination"):
        self.audit(api=get)
 def test_prior_successful_workflow_cannot_retry_even_if_skipped(self):
    with self.assertRaisesRegex(AttemptLedgerRejected,"prior_HTTP_possible"):
        self.audit(prior=run(11,"completed","success"))
 def test_run_history_undefined_refused(self):
    with self.assertRaisesRegex(AttemptLedgerRejected,"run_history_invalid"):
        self.audit(api=lambda url:{"workflow_runs":None})
 def test_replay_stability(self):
    self.assertEqual(self.audit(),self.audit())
if __name__=="__main__":unittest.main()
