"""Offline strict dual-channel acceptance, reusing established PC/SP parsers."""
import hashlib
import unittest
from unittest.mock import patch

from diagnostics.jra_pc_sp_benchmark import assess_dual_channel_experiment

PC_URL = "https://jra.jp/JRADB/accessD.html?CNAME=pw01abc0120261115%2FA1"
SP_URL = "https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01abc0120261115%2FB2"
ROWS = ((1, 1, "馬A"), (2, 1, "馬B"))
SNAPSHOT = {
    "race_number": 1,
    "race_date": "2026-11-15",
    "roster_verified": True,
    "runners": [
        {"horse_number": n, "frame_number": f, "horse_name": name}
        for n, f, name in ROWS
    ],
}
CUTOFF = "2026-11-15T07:00:00Z"
OBSERVED = "2026-11-15T02:04:00Z"


def item(channel, *, captured="2026-11-15T02:00:00Z"):
    raw = ("saved-" + channel).encode()
    return {
        "raw": raw,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "captured_utc": captured,
        "source_url": PC_URL if channel == "PC" else SP_URL,
        "official_link_independently_observed": True,
    }


class StrictDualExperimentTests(unittest.TestCase):
    def run_gate(self, channels):
        return assess_dual_channel_experiment(
            channels, SNAPSHOT, meeting_date="2026-11-15",
            race=1, cutoff_utc=CUTOFF, observed_utc=OBSERVED
        )

    def test_both_official_sources_parsed_with_existing_adapters(self):
        with patch("diagnostics.jra_pc_sp_benchmark.pc_rows", return_value=ROWS) as pc, \
             patch("diagnostics.jra_pc_sp_benchmark.sp_rows", return_value=ROWS) as sp:
            result = self.run_gate({"PC": item("PC"), "SP": item("SP")})
        self.assertTrue(result["dual_racecard_structure_parity"])
        self.assertEqual(result["state"], "DUAL_RACECARDS_OFFLINE_MATCH_MARKETS_PENDING")
        self.assertFalse(result["full_hybrid_experiment_pass"])
        self.assertFalse(result["dual_market_originals_verified"])
        self.assertEqual(result["network_requests"], 0)
        pc.assert_called_once()
        sp.assert_called_once()

    def test_pc_only_is_not_a_hybrid_pass(self):
        with patch("diagnostics.jra_pc_sp_benchmark.pc_rows", return_value=ROWS):
            result = self.run_gate({"PC": item("PC")})
        self.assertFalse(result["dual_racecard_structure_parity"])
        self.assertEqual(result["channel_links"]["SP"]["state"], "MISSING_OFFICIAL_ORIGINAL")
        self.assertFalse(result["full_hybrid_experiment_pass"])

    def test_sp_only_is_not_a_hybrid_pass(self):
        with patch("diagnostics.jra_pc_sp_benchmark.sp_rows", return_value=ROWS):
            result = self.run_gate({"SP": item("SP")})
        self.assertFalse(result["dual_racecard_structure_parity"])
        self.assertFalse(result["full_hybrid_experiment_pass"])

    def test_disagreeing_rosters_are_blocked(self):
        wrong = ((1, 1, "馬A"), (2, 2, "馬B"))
        with patch("diagnostics.jra_pc_sp_benchmark.pc_rows", return_value=ROWS), \
             patch("diagnostics.jra_pc_sp_benchmark.sp_rows", return_value=wrong):
            result = self.run_gate({"PC": item("PC"), "SP": item("SP")})
        self.assertEqual(result["channel_rosters"]["SP"]["status"], "ROSTER_MISMATCH")
        self.assertFalse(result["dual_racecard_structure_parity"])

    def test_sp_official_link_must_be_independently_observed(self):
        sp = item("SP")
        sp["official_link_independently_observed"] = False
        with patch("diagnostics.jra_pc_sp_benchmark.pc_rows", return_value=ROWS), \
             patch("diagnostics.jra_pc_sp_benchmark.sp_rows", return_value=ROWS):
            result = self.run_gate({"PC": item("PC"), "SP": sp})
        self.assertFalse(result["independently_observed_both_urls"])
        self.assertFalse(result["dual_racecard_structure_parity"])

    def test_sp_wrong_host_rejected(self):
        sp = item("SP")
        sp["source_url"] = PC_URL
        with patch("diagnostics.jra_pc_sp_benchmark.pc_rows", return_value=ROWS), \
             patch("diagnostics.jra_pc_sp_benchmark.sp_rows", return_value=ROWS):
            result = self.run_gate({"PC": item("PC"), "SP": sp})
        self.assertFalse(result["dual_racecard_structure_parity"])

    def test_more_than_fifteen_minutes_apart_rejected(self):
        with patch("diagnostics.jra_pc_sp_benchmark.pc_rows", return_value=ROWS), \
             patch("diagnostics.jra_pc_sp_benchmark.sp_rows", return_value=ROWS):
            result = self.run_gate({
                "PC": item("PC", captured="2026-11-15T01:30:00Z"),
                "SP": item("SP", captured="2026-11-15T02:00:00Z")
            })
        self.assertFalse(result["time_delta_within_15_minutes"])
        self.assertFalse(result["dual_racecard_structure_parity"])

    def test_tampered_sha_rejected_before_parser(self):
        pc = item("PC")
        pc["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source_sha_mismatch"):
            self.run_gate({"PC": pc, "SP": item("SP")})


if __name__ == "__main__":
    unittest.main()
