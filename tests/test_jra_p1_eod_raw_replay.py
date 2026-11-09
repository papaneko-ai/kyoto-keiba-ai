"""End-to-end validation against the recovered real 2026-11-06 ZIP, if supplied."""
import copy
import json
import os
import unittest
from pathlib import Path
from diagnostics.jra_p1_eod_raw_replay import replay

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json'

class EODRealOriginalReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=os.getenv('KYOTO_P1_RECOVERY_ARCHIVE')
        if not path or not Path(path).is_file():
            raise unittest.SkipTest('Recovered GitHub original artifact not supplied; no fabricated replacement')
        cls.archive=Path(path).read_bytes()
        cls.rows=json.loads(REGISTRY.read_text(encoding='utf-8'))

    def test_84_original_profiles_and_485_prior_runs(self):
        r=replay(self.archive,self.rows)
        self.assertEqual(r['html_originals'],86)
        self.assertEqual(r['registered_profiles'],96)
        self.assertEqual(r['statuses'],{'REPARSE_MATCH':84,'ORIGINAL_NOT_IN_RECOVERY':12})
        self.assertEqual(r['reparsed_valid_prior_rows'],485)
        self.assertEqual(r['verified_feature_fields'],335)
        self.assertFalse(r['prediction_ready'])
        self.assertEqual(r['new_jra_http_requests'],0)

    def test_identity_registry_lock_rejects_tampered_horse(self):
        rows=copy.deepcopy(self.rows)
        rows[1]['horse_name']='TAMPERED'
        with self.assertRaisesRegex(ValueError,'registry_does_not_match_locked_snapshot'):
            replay(self.archive,rows)

    def test_registry_truncation_refused(self):
        with self.assertRaisesRegex(ValueError,'expected_148_horse_registry'):
            replay(self.archive,self.rows[:-1])

    def test_nonzip_refused(self):
        with self.assertRaises(Exception):
            replay(b'not zip at all',self.rows)

if __name__=='__main__':
    unittest.main()
