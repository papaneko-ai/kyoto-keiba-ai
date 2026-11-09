import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from diagnostics.jra_p1_fb_stage5_offline_http_envelope import (
    ScriptedResponse,ScriptedOfflineTransport,verify_envelope,
    build_live_network_transport,MAX_SOURCE_BYTES)
from diagnostics.jra_p1_fb_stage5_guarded_replay import RosterHorse
from diagnostics.jra_p1_fb_stage5_ledger_replay import run_ledger_replay
from diagnostics.jra_p1_fb_stage5_live_preflight_disabled import LiveNetworkDisabled
from diagnostics.jra_p1_fb_stage5_global_attempt_registry import GlobalAttemptRegistry

PC="https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103876/AA"
SP="https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AA"
RAW=b"<html><body>fixture</body></html>"
T=datetime(2026,11,13,6,0,tzinfo=timezone.utc)
CUT=datetime(2026,11,14,tzinfo=timezone.utc)
HORSE=RosterHorse("2026-11-14",11,1,"モンドプリューム","a"*64,PC,SP,True,True)

def fixture(url,**kwargs):
    return ScriptedResponse(url,200,"text/html; charset=utf-8",url,RAW,**kwargs)

def good(body,horse):
    return {"horse_name":horse,"prior_rows":[{"date":"2026-10-01"}],"invalid_rows":[]}

def bad(body,horse):
    raise ValueError("parser_fault")

class OfflineEnvelopeTests(unittest.TestCase):
    def test_exact_official_response(self):
        response,meta=verify_envelope("PC",PC,fixture(PC))
        self.assertEqual(response.body,RAW)
        self.assertEqual(meta["network_requests"],0)
        self.assertEqual(meta["redirect_count"],0)

    def test_sp_response(self):
        response,_=verify_envelope("SP",SP,fixture(SP))
        self.assertEqual(response.final_url,SP)

    def test_redirect_to_other_official_page_forbidden(self):
        with self.assertRaisesRegex(ValueError,"unexpected_redirect"):
            verify_envelope("PC",PC,replace(fixture(PC),final_url=SP))

    def test_historical_redirect_even_to_same_url_forbidden(self):
        with self.assertRaisesRegex(ValueError,"redirect_forbidden"):
            verify_envelope("PC",PC,replace(fixture(PC),transfer_redirect_count=1))

    def test_other_host_refused(self):
        with self.assertRaisesRegex(ValueError,"unverified_official_endpoint"):
            verify_envelope("PC","https://evil.example/JRADB/accessU.html?CNAME=pw01/AA",fixture(PC))

    def test_body_size_limit_and_empty_body(self):
        for b in (b"",b"x"*(MAX_SOURCE_BYTES+1)):
            with self.subTest(len=len(b)),self.assertRaisesRegex(ValueError,"source_body_size_invalid"):
                verify_envelope("PC",PC,replace(fixture(PC),body=b))

    def test_content_type_and_compression_refused(self):
        with self.assertRaisesRegex(ValueError,"unexpected_content_type"):
            verify_envelope("PC",PC,replace(fixture(PC),content_type="application/json"))
        with self.assertRaisesRegex(ValueError,"compressed_or_ambiguous_encoding"):
            verify_envelope("PC",PC,replace(fixture(PC),content_encoding="gzip"))

    def test_http_failure_refused(self):
        with self.assertRaisesRegex(ValueError,"http_non_success"):
            verify_envelope("PC",PC,replace(fixture(PC),status=429))

    def test_no_binary_nulls(self):
        with self.assertRaisesRegex(ValueError,"null_byte"):
            verify_envelope("PC",PC,replace(fixture(PC),body=b"<html>\x00</html>"))

    def test_missing_fixture_never_network(self):
        t=ScriptedOfflineTransport({})
        with self.assertRaisesRegex(ValueError,"no_offline_fixture_for_url"):
            t("PC",PC)
        self.assertEqual(t.audit,[])

    def test_scripted_duplicate_refused(self):
        t=ScriptedOfflineTransport({("PC",PC):fixture(PC)})
        t("PC",PC)
        with self.assertRaisesRegex(ValueError,"scripted_transport_duplicate_attempt"):
            t("PC",PC)

    def test_external_fixture_mutation_does_not_swap_content(self):
        d={("PC",PC):fixture(PC)}
        t=ScriptedOfflineTransport(d)
        d.clear()
        self.assertEqual(t("PC",PC).body,RAW)

    def test_real_http_factory_disabled(self):
        with self.assertRaises(LiveNetworkDisabled):
            build_live_network_transport()

    def test_integration_http_like_pc_sp_with_ledger_and_originals(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        folder=Path(d.name)/"case"
        db=Path(d.name)/"registry.sqlite"
        t=ScriptedOfflineTransport({("PC",PC):fixture(PC),("SP",SP):fixture(SP)})
        result=run_ledger_replay(folder=folder,roster=HORSE,now=T,cutoff=CUT,
            replay_transport=t,parsers={"PC":bad,"SP":good},ledger_path=db)
        self.assertEqual(result["selected"],"SP")
        self.assertEqual(len(t.audit),2)
        self.assertEqual((folder/"original_pc.html").read_bytes(),RAW)
        self.assertEqual((folder/"original_sp.html").read_bytes(),RAW)
        self.assertEqual(len(GlobalAttemptRegistry(db).inventory()),2)
        self.assertTrue(result["global_ledger_offline_only"])

    def test_malformed_pc_envelope_quarantined_backup_success(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        root=Path(d.name)
        t=ScriptedOfflineTransport({("PC",PC):replace(fixture(PC),status=503),("SP",SP):fixture(SP)})
        result=run_ledger_replay(folder=root/"case",roster=HORSE,now=T,cutoff=CUT,
            replay_transport=t,parsers={"PC":good,"SP":good},ledger_path=root/"ledger.sqlite")
        self.assertEqual(result["selected"],"SP")
        self.assertEqual(len(result["incidents"]),1)
        self.assertFalse((root/"case"/"original_pc.html").exists())
        self.assertTrue((root/"case"/"original_sp.html").exists())

if __name__=="__main__":
    unittest.main()
