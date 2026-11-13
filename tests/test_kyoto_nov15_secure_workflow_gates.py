"""No plaintext artifacts and no alternate Nov15 capture in legacy workflow."""
import unittest
from pathlib import Path
SRC=Path(".github/workflows/kyoto-nov15-encrypted-observer.yml")
LIVE=Path(".github/workflows/kyoto-nov15-second-day-observed-oneshot.yml")
LEGACY=Path(".github/workflows/jra-observed-odds-manual-oneshot.yml")
class SecureWorkflowTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    cls.a=SRC.read_text();cls.b=LIVE.read_text();cls.c=LEGACY.read_text()
 def test_observation_activation_only(self):
    self.assertIn("paths: ['diagnostics/nov15_observation_explicit_activation.txt']",self.a)
    self.assertNotIn("schedule:",self.a)
 def test_observation_requires_secret_first(self):
    self.assertLess(self.a.index("NOV15_ENCRYPTED_ARCHIVE_SECRET_MISSING_OR_INVALID_NO_HTTP"),
                    self.a.index("observe("))
 def test_observation_upload_encrypted_only(self):
    self.assertIn("path: nov15_encrypted_evidence/",self.a)
    self.assertNotIn("path: nov15_work_originals/",self.a)
 def test_live_downloads_prior_encrypted_observation(self):
    self.assertIn("gh run download",self.b)
    self.assertIn("kyoto_nov15_encrypted_evidence",self.b)
    self.assertLess(self.b.index("gh run download"),self.b.index("--authorized-live-http"))
 def test_live_upload_only_encrypted_capture(self):
    self.assertIn("path: nov15_encrypted_capture/",self.b)
    self.assertNotIn("path: nov15_pc_one_shot/",self.b)
    self.assertIn("kyoto_nov15_full_capture_seal",self.b)
 def test_missing_archive_secret_blocked_before_live_http(self):
    self.assertLess(self.b.index("NOV15_ARCHIVE_ENCRYPTION_SECRET_MISSING_NO_HTTP"),
                    self.b.index("--authorized-live-http"))
 def test_same_source_concurrency_group(self):
    group="kyoto-nov15-source-acquisition-single-coordinator"
    self.assertIn(group,self.a)
    self.assertIn(group,self.b)
    self.assertIn(group,self.c)
 def test_legacy_refuses_nov15_before_any_fetch(self):
    self.assertIn('if spec.race_day=="20261115":',self.c)
    self.assertIn("NOV15_RESERVED_FOR_DEDICATED_ENCRYPTED_CAPTURE",self.c)
    self.assertLess(self.c.index("NOV15_RESERVED_FOR_DEDICATED_ENCRYPTED_CAPTURE"),
                    self.c.index("One-shot JRA original-market diagnostic"))
 def test_nov15_no_source_hardcoding(self):
    self.assertNotIn("CNAME=pw",self.a)
    self.assertNotIn("CNAME=pw",self.b)
 def test_two_originals_are_not_market_authentication(self):
    self.assertIn("accept_observation",self.b)
    self.assertIn("NOV15_SOURCE_ONLY_NOT_LIVE_CERTIFICATION",self.b)
if __name__=="__main__":unittest.main()
