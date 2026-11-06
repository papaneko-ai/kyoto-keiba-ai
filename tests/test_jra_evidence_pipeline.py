"""Unit tests for original-byte evidence integrity, with no external network."""
import unittest
from datetime import datetime
from hashlib import sha256
from diagnostics.jra_evidence_pipeline import EvidenceError,identify_structure,verify_archived_capture
RAW=b'<html><head><title>JRA</title></head><body><table></table></body></html>'
MANIFEST={'source_url':'https://www.jra.go.jp/JRADB/accessD.html?CNAME=test',
          'source_sha256':sha256(RAW).hexdigest(),'bytes':len(RAW),
          'fetched_at_utc':'2026-11-06T02:00:00Z'}
class Tests(unittest.TestCase):
 def test_hash_verified(self):
  x=verify_archived_capture(RAW,MANIFEST)
  self.assertTrue(x['verified_raw_bytes']);self.assertFalse(x['training_ready'])
 def test_tampered_source(self):
  with self.assertRaises(EvidenceError):verify_archived_capture(RAW+b'0',MANIFEST)
 def test_missing_timestamp(self):
  m=dict(MANIFEST);m['fetched_at_utc']='2026-11-06T02:00:00'
  with self.assertRaises(EvidenceError):verify_archived_capture(RAW,m)
 def test_after_historical_race(self):
  x=verify_archived_capture(RAW,MANIFEST,'2026-10-31T06:00:00Z')
  self.assertFalse(x['captured_before_cutoff'])
 def test_wrong_source(self):
  m=dict(MANIFEST);m['source_url']='https://example.org/'
  with self.assertRaises(EvidenceError):verify_archived_capture(RAW,m)
 def test_selection_not_certified(self):
  self.assertEqual(identify_structure('<title>出馬表 開催選択　JRA</title>'.encode('cp932'))['structure'],'MEETING_SELECTION')
 def test_results_not_certified(self):
  raw=b'<table><tr><th class="place"></th><th class="num"></th><th class="waku"></th><th class="horse"></th></tr></table>'
  self.assertEqual(identify_structure(raw)['structure'],'POST_RACE_RESULT')
 def test_repeat(self):self.assertEqual(verify_archived_capture(RAW,MANIFEST),verify_archived_capture(RAW,MANIFEST))
if __name__=='__main__':unittest.main()
