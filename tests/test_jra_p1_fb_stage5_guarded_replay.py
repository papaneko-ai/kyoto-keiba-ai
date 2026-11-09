import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from diagnostics.jra_p1_fb_stage4_mock_adapter import Response
from diagnostics.jra_p1_fb_stage5_guarded_replay import (
    RosterHorse, atomic_seal, preflight, run_guarded_replay)
from diagnostics.jra_p1_fb_request_budget_policy import Attempt

NOW = datetime(2026, 11, 6, 6, 40, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 11, 7, tzinfo=timezone.utc)
PC = "https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103876/AA"
SP = "https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AA"
ROSTER = RosterHorse("2026-11-07", 11, 1, "モンドプリューム", "a"*64,
                    PC, SP, True, True)
RAW = b"<html><body>offline sample</body></html>"

def replay(channel, url):
    return Response(RAW, 200, "text/html", url)
replay.offline_replay_only = True

def valid(body, horse):
    return {"horse_name": horse, "prior_rows": [{"date": "2026-09-12", "finish_position": 1}],
            "invalid_rows": []}

def broken(body, horse):
    raise ValueError("injected_parser_failure")

class Stage5Offline(unittest.TestCase):
    def case(self, **kwargs):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        folder = Path(d.name)/"incident"
        options = dict(folder=folder, roster=ROSTER, now=NOW, cutoff=CUTOFF,
                       replay_transport=replay, parsers={"PC": broken, "SP": valid})
        options.update(kwargs)
        return run_guarded_replay(**options), folder

    def test_preflight_with_observed_links(self):
        a = preflight(roster=ROSTER, prior_attempts=(), now=NOW, cutoff=CUTOFF)
        self.assertEqual(a["status"], "DRY_RUN_ELIGIBLE_NOT_NETWORK_AUTHORIZATION")
        self.assertFalse(a["live_automatic_fallback_authorized"])

    def test_primary_parse_error_fallback_preserves_sources(self):
        result, folder = self.case()
        self.assertEqual(result["selected"], "SP")
        self.assertEqual((folder/"original_pc.html").read_bytes(), RAW)
        self.assertEqual((folder/"original_sp.html").read_bytes(), RAW)
        self.assertTrue(result["incidents"][0]["open"])
        self.assertTrue(result["stage5_offline_only"])
        self.assertEqual(result["actual_network_requests"], 0)
        self.assertEqual(json.loads((folder/"stage5_preflight.json").read_text())["number"], 1)

    def test_reverse_backup(self):
        result, _ = self.case(channels=("SP", "PC"),
                              parsers={"PC": valid, "SP": broken})
        self.assertEqual(result["selected"], "PC")

    def test_success_uses_one_channel(self):
        r, f = self.case(parsers={"PC": valid, "SP": broken})
        self.assertEqual(len(r["attempts"]), 1)
        self.assertFalse((f/"original_sp.html").exists())

    def test_no_network_capable_transport(self):
        with self.assertRaisesRegex(ValueError, "offline_replay_transport_only"):
            self.case(replay_transport=lambda ch, url: replay(ch,url))

    def test_post_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError, "prerace_cutoff_expired"):
            self.case(now=datetime(2026,11,9,tzinfo=timezone.utc))

    def test_verified_horse_rejected(self):
        attempted = Attempt("SP", "https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AB",
                            NOW-timedelta(minutes=10),11,1,"VALIDATED",True)
        with self.assertRaisesRegex(ValueError, "horse_already_verified"):
            self.case(prior_attempts=(attempted,))

    def test_attempted_url_rejected(self):
        attempted = Attempt("PC", PC, NOW-timedelta(minutes=10),10,1,"HTTP_FAILED",False)
        with self.assertRaisesRegex(ValueError, "already_attempted_official_url"):
            self.case(prior_attempts=(attempted,))

    def test_roster_not_observed_rejected(self):
        bad=RosterHorse("2026-11-07",11,1,"モンドプリューム","a"*64,PC,SP,False,True)
        with self.assertRaisesRegex(ValueError,"unverified_official_roster_link"):
            self.case(roster=bad)

    def test_bad_host_rejected(self):
        bad=RosterHorse("2026-11-07",11,1,"モンドプリューム","a"*64,
                        "https://example.com/JRADB/accessU.html?CNAME=not_official",SP,True,True)
        with self.assertRaisesRegex(ValueError,"unverified_official_roster_link"):
            self.case(roster=bad)

    def test_raw_seal_immutable(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p=Path(d.name)
        a=atomic_seal(p,"horse.html",RAW)
        self.assertEqual(a["bytes"],len(RAW))
        self.assertEqual((p/"horse.html").read_bytes(),RAW)
        with self.assertRaises(FileExistsError):
            atomic_seal(p,"horse.html",b"other")
        self.assertEqual((p/"horse.html").read_bytes(),RAW)

    def test_bad_seal_name(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with self.assertRaisesRegex(ValueError,"bad_source_destination"):
            atomic_seal(d.name,"../escape.html",RAW)

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"untrusted_utc_clock"):
            self.case(now=datetime(2026,11,6))

    def test_duplicate_folder_guard(self):
        r,f=self.case()
        with self.assertRaisesRegex(ValueError,"immutable_incident_directory_already_exists"):
            self.case(folder=f)


    def test_stage5_uses_atomic_writer_not_stage4_direct_write(self):
        from unittest.mock import patch
        with patch("pathlib.Path.write_bytes", side_effect=AssertionError("legacy_write_forbidden")):
            result, folder = self.case()
        self.assertEqual(result["selected"], "SP")
        self.assertEqual((folder/"original_pc.html").read_bytes(), RAW)
        self.assertEqual((folder/"original_sp.html").read_bytes(), RAW)

    def test_atomic_link_failure_stops_backup(self):
        from unittest.mock import patch
        with patch("os.link", side_effect=OSError("simulated_atomic_link_failure")):
            result, folder = self.case()
        self.assertEqual(result["status"], "FALLBACK_BLOCKED")
        self.assertEqual(len(result["attempts"]), 1)
        self.assertFalse((folder/"original_pc.html").exists())
        self.assertEqual(result["actual_network_requests"], 0)

if __name__ == "__main__":
    unittest.main()
