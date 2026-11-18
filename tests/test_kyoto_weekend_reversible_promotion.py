"""Destructive rollback checks; no GitHub writes or live HTTP."""
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_weekend_reversible_promotion import review,BASE,CANDIDATE,SCHEDULES
def fixture():
    return ("name: source\non:\n  schedule:\n"+
         "".join("    - cron: '"+c+"'\n" for c in SCHEDULES)+
         "jobs:\n  pc-originals-independent:\n  sp-originals-independent:\n"+
         "concurrency:\n  cancel-in-progress: false\n"+
         "env:\n  KEY: KYOTO_JRA_ARCHIVE_AES256_HEX\n"+
         "".join("  source"+str(i)+": "+BASE+"\n" for i in range(6)))
class TestReversibleProductionPromotion(unittest.TestCase):
    def check(self,source=None,reviewed=None):
        a=source if source is not None else fixture()
        b=reviewed if reviewed is not None else a.replace(BASE,CANDIDATE)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"main.yml";q=Path(td)/"review.yml"
            p.write_text(a);q.write_text(b)
            return review(p,q)
    def test_exact_replay_and_rollback(self):
        result=self.check()
        self.assertTrue(result["reversible_byte_identical"])
        self.assertEqual(result["production_main_workflow_sha256"],
                         result["restored_workflow_sha256"])
        self.assertEqual(result["preserved_observation_slots"],8)
        self.assertEqual(result["pinned_replacements"],6)
    def test_refuse_extra_changes(self):
        with self.assertRaisesRegex(ValueError,"nonpin"):
            self.check(reviewed=fixture().replace(BASE,CANDIDATE)+"\nextra: true\n")
    def test_refuse_missing_pin(self):
        with self.assertRaisesRegex(ValueError,"main_source_pin"):
            self.check(source=fixture().replace(BASE,"a"*40,1))
    def test_refuse_candidate_changed_pin_count(self):
        b=fixture().replace(BASE,CANDIDATE).replace(CANDIDATE,"f"*40,1)
        with self.assertRaisesRegex(ValueError,"candidate_pin"):
            self.check(reviewed=b)
    def test_refuse_removed_early_slot(self):
        a=fixture().replace("    - cron: '15 0 21 11 *'\n","")
        with self.assertRaisesRegex(ValueError,"8_windows"):
            self.check(source=a)
    def test_refuse_loss_of_encryption(self):
        a=fixture().replace("KYOTO_JRA_ARCHIVE_AES256_HEX","MISSING")
        with self.assertRaisesRegex(ValueError,"operational_safety"):
            self.check(source=a)
    def test_refuse_loss_of_concurrency(self):
        a=fixture().replace("cancel-in-progress: false","cancel-in-progress: true")
        with self.assertRaisesRegex(ValueError,"operational_safety"):
            self.check(source=a)
    def test_original_data_unchanged(self):
        self.assertEqual(fixture().count(BASE),6)
        self.assertFalse(self.check()["future_production_merge_performed"])
if __name__=="__main__":unittest.main()
