"""C08 global G06 budget: synthetic clock and local official-shaped originals only."""
import tempfile
import unittest
from pathlib import Path
from tests.test_kyoto_g06_all12_capture import samples,mock_collector
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.jra_one_shot_market_capture import SourceChainError


class C08DeadlineTests(unittest.TestCase):
    def run_g06(self,**kwargs):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return run_twelve(Path(temp.name)/"saved",records=samples(),
                          runner=kwargs.pop("runner",mock_collector),**kwargs)

    def test_four_saved_then_eight_skipped_with_no_extra_http(self):
        calls=[]
        def collector(path,**kwargs):
            calls.append(kwargs["race_spec"].race_number)
            return mock_collector(path,**kwargs)
        clock=iter([1.0,2.0,3.0,4.0]+[100.0]*8)
        r=self.run_g06(runner=collector,capture_deadline_monotonic=100.0,
                       monotonic_clock=lambda:next(clock))
        self.assertEqual(calls,[1,2,3,4])
        self.assertEqual(r["verified_dual_market_races"],4)
        self.assertEqual(r["time_budget_reserved_for_sealing_races"],8)
        self.assertTrue(all(x["state"]=="G06_TIME_BUDGET_RESERVED_FOR_SEALING"
                            for x in r["records"][4:]))
        self.assertFalse(r["prediction_ready"])
        self.assertFalse(r["actual_wager_authorized"])

    def test_expired_before_first_race_preserves_all_twelve_slots(self):
        calls=[]
        def collector(path,**kwargs):
            calls.append(1)
            return mock_collector(path,**kwargs)
        r=self.run_g06(runner=collector,capture_deadline_monotonic=10,
                       monotonic_clock=lambda:10)
        self.assertEqual(calls,[])
        self.assertEqual(r["time_budget_reserved_for_sealing_races"],12)
        self.assertEqual(len(r["records"]),12)
        self.assertEqual(r["verified_dual_market_races"],0)

    def test_default_unlimited_legacy_mode_is_unchanged(self):
        r=self.run_g06()
        self.assertEqual(r["verified_dual_market_races"],12)
        self.assertEqual(r["time_budget_reserved_for_sealing_races"],0)
        self.assertFalse(r["time_budget_deadline_enabled"])

    def test_invalid_clock_or_deadline_rejected_before_files_and_http(self):
        with self.assertRaisesRegex(SourceChainError,"g06_time_budget_invalid"):
            self.run_g06(capture_deadline_monotonic="bad")
        with self.assertRaisesRegex(SourceChainError,"g06_time_clock_invalid"):
            self.run_g06(monotonic_clock="bad")

    def test_saved_market_originals_survive_global_deadline(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)/"saved"
        ticks=iter([1]+[11]*11)
        r=run_twelve(root,records=samples(),runner=mock_collector,
                     capture_deadline_monotonic=10,monotonic_clock=lambda:next(ticks))
        self.assertEqual(r["verified_dual_market_races"],1)
        self.assertEqual(r["time_budget_reserved_for_sealing_races"],11)
        self.assertTrue((root/"r01"/"pc"/"quinella_original.html").is_file())
        self.assertTrue((root/"g06_batch_receipt.json").is_file())


if __name__=="__main__":
    unittest.main()
