import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from diagnostics.kyoto_impl33_workout_runtime import collect_primary,repair_primary_links,exact_link_map,source_record,PRIMARY_INDEX,HOST
from test_kyoto_impl33_workout_generic import sample,DAY,URL
CLOCK=lambda:datetime(2026,11,27,11,tzinfo=timezone.utc)
STAMP="2026-11-26T04:00:00Z"
class ObservedLinkRepair(unittest.TestCase):
    def test_saved_page_applied_after_index_failure(self):
        with patch("diagnostics.kyoto_impl33_workout_runtime.now",CLOCK):
            old=source_record(sample(),STAMP,URL,"PRIMARY",9)
            calls=[];proof=[]
            def fetch(url):
                calls.append(url)
                if url==PRIMARY_INDEX:raise TimeoutError()
                self.assertEqual(proof[0]["race"],9)
                return sample()
            items,_,errors=collect_primary(DAY,[old],{},fetch,CLOCK,on_repair=proof.append)
            self.assertEqual(calls,[PRIMARY_INDEX,URL])
            self.assertEqual(errors,["TimeoutError"]);self.assertEqual(len(items),2)
            self.assertEqual(proof[0]["basis"],"AUTHENTICATED_SAVED_RACE_PAGE")
            self.assertFalse(proof[0]["source_success_certified"])
    def test_saved_index_fills_missing_exact_link_without_guess(self):
        index=b'<a href="/race/20261128-kyoto-09/">9R</a><a href="/race/20261128-kyoto-08/?x=1">8R</a><a href="https://other.example/race/20261128-kyoto-07/">7R</a>'
        calls=[];proof=[]
        def fetch(url):
            calls.append(url)
            return b'<html></html>' if url==PRIMARY_INDEX else sample()
        with patch("diagnostics.kyoto_impl33_workout_runtime.now",CLOCK):
            items,_,errors=collect_primary(DAY,[],{},fetch,CLOCK,prior_indexes=[{"raw":index,"run_id":55,"stamp":STAMP}],on_repair=proof.append)
        self.assertEqual(calls,[PRIMARY_INDEX,URL]);self.assertEqual(len(items),1);self.assertFalse(errors)
        self.assertEqual(proof[0]["prior_run_id"],55);self.assertEqual(proof[0]["basis"],"AUTHENTICATED_SAVED_INDEX_DUAL_PARSER")
    def test_no_override_no_poststart_and_reject_bad_sources(self):
        with patch("diagnostics.kyoto_impl33_workout_runtime.now",CLOCK):
            old=source_record(sample(),STAMP,URL,"PRIMARY",9)
        cases=[([old],[],{9:URL},{}),([old],[],{},{9:{"start":STAMP}}),([{**old,"race":8}],[],{},{}),([], [{"raw":b'<base href="https://other.example/"><a href="/race/20261128-kyoto-09/">x</a>',"stamp":STAMP,"run_id":55}],{},{}),([], [{"raw":b'<a href="/race/20261128-kyoto-09/" href="/race/20261128-kyoto-08/">x</a>',"stamp":STAMP,"run_id":55}],{},{})]
        for items,idx,current,rosters in cases:self.assertEqual(repair_primary_links(DAY,items,idx,current,rosters,CLOCK()),{})
    def test_checkpoint_failure_prevents_repair_fetch(self):
        with patch("diagnostics.kyoto_impl33_workout_runtime.now",CLOCK):
            old=source_record(sample(),STAMP,URL,"PRIMARY",9)
            calls=[]
            def fetch(url):calls.append(url);return b'<html></html>'
            def bad(p):raise OSError()
            _,_,errors=collect_primary(DAY,[old],{},fetch,CLOCK,on_repair=bad)
        self.assertEqual(calls,[PRIMARY_INDEX]);self.assertIn("LINK_REPAIR_CHECKPOINT:OSError",errors)
