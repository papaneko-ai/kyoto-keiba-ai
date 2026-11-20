"""One horse's bad observed link cannot cancel other verified G04 profiles."""
import json
import unittest
from unittest.mock import patch
from tests.test_kyoto_g04_all_horse_profiles import AllHorseProfile
from diagnostics.kyoto_g04_all_horse_profiles import capture, G04Rejected

class HorsewiseIsolation(unittest.TestCase):
    def setUp(self):
        # Reuse the existing 12-race official-shaped fixture; never real HTTP.
        AllHorseProfile.setUp(self)

    def _modified(self, which, value):
        path=self.root/"g03_receipt.json"
        receipt=json.loads(path.read_text())
        receipt["races"]["1"]["runners"][which]["profile_navigation"]=value
        path.write_text(json.dumps(receipt))

    def _capture(self, **kwargs):
        with patch("diagnostics.kyoto_g03_independent_partial.verify_partial",
                   return_value={"verified_race_numbers":list(range(1,13))}):
            return capture(root=self.root,day="20261121",fetch=self.fetch,
                clock=lambda:"2026-11-21T00:01:00Z",allowed=True,
                allow_partial=True,**kwargs)

    def test_invalid_one_horse_preserves_other_35(self):
        self._modified(0,"https://untrusted.invalid/fake")
        result=self._capture(isolate_invalid_links=True)
        self.assertEqual(result["expected_horses"],36)
        self.assertEqual(result["profile_verified_count"],35)
        self.assertEqual(result["invalid_profile_navigation_count"],1)
        self.assertEqual(len(self.calls),35)
        self.assertEqual(result["profiles"][0]["state"],
                         "INVALID_OR_DUPLICATE_PROFILE_NAVIGATION")
        self.assertEqual(result["profiles"][0]["source_url"],None)
        self.assertEqual(len(result["missing_profiles"]),1)
        self.assertFalse(result["prediction_ready"])

    def test_duplicate_horse_link_quarantines_later_horse(self):
        receipt=json.loads((self.root/"g03_receipt.json").read_text())
        first=receipt["races"]["1"]["runners"][0]["profile_navigation"]
        self._modified(1,first)
        result=self._capture(isolate_invalid_links=True)
        self.assertEqual(result["profile_verified_count"],35)
        self.assertEqual(result["invalid_profile_navigation_count"],1)
        self.assertEqual(len(set(self.calls)),35)

    def test_default_strict_path_does_not_bypass_link_validation(self):
        self._modified(0,"https://untrusted.invalid/fake")
        with self.assertRaises((ValueError,G04Rejected)):
            self._capture()
        self.assertEqual(self.calls,[])

    def test_bad_isolation_type_rejected_without_network(self):
        with self.assertRaisesRegex(G04Rejected,"invalid_link_isolation_mode"):
            self._capture(isolate_invalid_links="yes")
        self.assertEqual(self.calls,[])

    def test_independent_g03_proof_must_still_precede_fetch(self):
        self._modified(0,"https://untrusted.invalid/fake")
        with patch("diagnostics.kyoto_g03_independent_partial.verify_partial",
                   side_effect=ValueError("tampered_g03")):
            with self.assertRaisesRegex(ValueError,"tampered_g03"):
                capture(root=self.root,day="20261121",fetch=self.fetch,
                    clock=lambda:"2026-11-21T00:01:00Z",allowed=True,
                    allow_partial=True,isolate_invalid_links=True)
        self.assertEqual(self.calls,[])

if __name__=="__main__":
    unittest.main()
