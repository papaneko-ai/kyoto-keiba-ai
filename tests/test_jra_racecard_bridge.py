import unittest
from diagnostics.jra_racecard_bridge import (SOURCES,EvidenceError,validate_racecard_url,
    clean_display_name,source_manifest,compare_independent_rows)
class TestBridge(unittest.TestCase):
 def test_three_official_urls(self):
  self.assertEqual(len(SOURCES),3)
  for x in SOURCES:self.assertTrue(validate_racecard_url(x.url))
 def test_nonofficial_rejected(self):
  with self.assertRaises(EvidenceError):validate_racecard_url('https://fake.example/JRADB/accessD.html?CNAME=abc')
 def test_other_endpoint_rejected(self):
  with self.assertRaises(EvidenceError):validate_racecard_url('https://www.jra.go.jp/JRADB/accessS.html?CNAME=abc')
 def test_badge(self):self.assertEqual(clean_display_name('マルガイ スリーオブスペイズ')['name'],'スリーオブスペイズ')
 def test_real_name_not_truncated(self):self.assertEqual(clean_display_name('マルガイスリーオブスペイズ')['name'],'マルガイスリーオブスペイズ')
 def test_match_no_training(self):
  a=[{'horse_number':1,'frame_number':1,'horse_name':'スリーオブスペイズ'}]
  b=[{'horse_number':1,'frame_number':1,'horse_name':'マルガイ スリーオブスペイズ'}]
  r=compare_independent_rows(a,b)
  self.assertTrue(r['full_roster_match'])
  self.assertFalse(r['ready_for_training'])
 def test_discrepancy(self):
  a=[{'horse_number':1,'frame_number':1,'horse_name':'馬A'}]
  b=[{'horse_number':1,'frame_number':1,'horse_name':'馬B'}]
  self.assertTrue(compare_independent_rows(a,b)['discrepancies'])
 def test_missing_row(self):
  a=[{'horse_number':1,'frame_number':1,'horse_name':'馬A'}]
  self.assertFalse(compare_independent_rows(a,[])['full_roster_match'])
 def test_duplicate_rejected(self):
  a={'horse_number':1,'frame_number':1,'horse_name':'馬A'}
  with self.assertRaises(EvidenceError):compare_independent_rows([a,a],[a])
 def test_no_snapshot(self):
  m=source_manifest()
  self.assertFalse(m['raw_html_captured'])
  self.assertFalse(m['ready_for_training'])
if __name__=='__main__':unittest.main()
