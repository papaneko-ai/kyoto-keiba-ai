"""Regression for saved SP navigation; synthetic originals only, zero HTTP."""
import hashlib
import unittest
from diagnostics.jra_pc_sp_benchmark import observed_sp_race_links_from_saved_navigation

SOURCE = "https://sp.jra.jp/JRADB/accessD.html?CNAME=sw00meeting%2F20261115"

class ObservedSPRaceLinksTests(unittest.TestCase):
    def test_sp_anchor_with_space_before_r_is_recognized(self):
        original = ('<html><a href="/JRADB/accessD.html?CNAME=sw020aaa01%2F0120261115">'
                    '京都 1 R</a></html>').encode("cp932")
        result = observed_sp_race_links_from_saved_navigation(
            original, source_url=SOURCE,
            source_sha256=hashlib.sha256(original).hexdigest(),
            race_day="20261115")
        self.assertEqual([x["race_number"] for x in result["race_links"]], [1])
        self.assertEqual(result["network_requests"], 0)
        self.assertFalse(result["official_sp_live_capture_achieved"])
        self.assertFalse(result["dual_market_verified"])

    def test_twelve_race_anchor_is_recognized(self):
        original = ('<html><a href="/JRADB/accessD.html?CNAME=sw020aaa12%2F1220261115">'
                    '京都 12R</a></html>').encode("cp932")
        result = observed_sp_race_links_from_saved_navigation(
            original, source_url=SOURCE,
            source_sha256=hashlib.sha256(original).hexdigest(),
            race_day="20261115")
        self.assertEqual([x["race_number"] for x in result["race_links"]], [12])

    def test_unobserved_race_link_is_not_invented(self):
        original = b"<html><body>Kyoto 1 R without anchor</body></html>"
        result = observed_sp_race_links_from_saved_navigation(
            original, source_url=SOURCE,
            source_sha256=hashlib.sha256(original).hexdigest(),
            race_day="20261115")
        self.assertEqual(result["race_links"], [])

    def test_tampered_original_digest_is_rejected(self):
        original = b"<html></html>"
        with self.assertRaisesRegex(ValueError, "sp_navigation_sha_mismatch"):
            observed_sp_race_links_from_saved_navigation(
                original, source_url=SOURCE, source_sha256="0" * 64,
                race_day="20261115")

if __name__ == "__main__":
    unittest.main()
