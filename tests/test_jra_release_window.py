import unittest
from datetime import date,datetime
from diagnostics.jra_release_window import publication_opportunity,certify_publication,PublicationGateError
DAY=date(2026,10,31)
def at(s):return datetime.fromisoformat(s)
def check(t,event='DRAW_NUMBERED',**kwargs):return publication_opportunity(DAY,at(t),event=event,**kwargs)
class ReleaseWindowTests(unittest.TestCase):
 def test_thursday_before(self):self.assertEqual(check('2026-10-29T15:59:00+09:00','ENTRIES_UNNUMBERED').status,'WAIT_FOR_PUBLICATION_WINDOW')
 def test_thursday_after(self):self.assertEqual(check('2026-10-29T16:01:00+09:00','ENTRIES_UNNUMBERED').status,'MAY_CHECK_PUBLICATION')
 def test_friday_before(self):self.assertEqual(check('2026-10-30T09:59:59+09:00').status,'WAIT_FOR_PUBLICATION_WINDOW')
 def test_friday_after(self):self.assertEqual(check('2026-10-30T10:01:00+09:00').status,'MAY_CHECK_PUBLICATION')
 def test_equal(self):self.assertEqual(check('2026-10-30T10:00:00+09:00').status,'WAIT_FOR_PUBLICATION_WINDOW')
 def test_sunday(self):self.assertEqual(publication_opportunity(date(2026,11,1),at('2026-10-29T17:00:00+09:00'),event='ENTRIES_UNNUMBERED').candidate_after_jst.date().isoformat(),'2026-10-29')
 def test_special_block(self):self.assertEqual(check('2026-10-30T11:00:00+09:00',exceptional_race=True).status,'EXCEPTION_NEEDS_OFFICIAL_OVERRIDE')
 def test_special_override(self):self.assertEqual(check('2026-10-29T14:01:00+09:00',exceptional_race=True,exceptional_override_jst=at('2026-10-29T14:00:00+09:00')).status,'MAY_CHECK_PUBLICATION')
 def test_monday_exception(self):self.assertEqual(publication_opportunity(date(2026,11,2),at('2026-11-01T12:00:00+09:00'),event='DRAW_NUMBERED').status,'EXCEPTION_NEEDS_OFFICIAL_OVERRIDE')
 def test_missing_source(self):self.assertFalse(certify_publication(check('2026-10-30T10:01:00+09:00'),{})['available'])
 def test_claimed_source_not_certified(self):self.assertFalse(certify_publication(check('2026-10-30T10:01:00+09:00'),{'structure_verified':True,'raw_sha256':'a'*64,'fetched_at_utc':'2026-10-30T01:01:00Z','event':'DRAW_NUMBERED'})['available'])
 def test_naive_time(self):
  with self.assertRaises(PublicationGateError):publication_opportunity(DAY,datetime(2026,10,30,10,1),event='DRAW_NUMBERED')
 def test_unapproved_override(self):
  with self.assertRaises(PublicationGateError):check('2026-10-30T10:01:00+09:00',exceptional_override_jst=at('2026-10-29T14:00:00+09:00'))
 def test_bad_event(self):
  with self.assertRaises(PublicationGateError):check('2026-10-30T10:01:00+09:00',event='WRONG')
 def test_utc_equal(self):self.assertEqual(check('2026-10-30T01:01:00Z'),check('2026-10-30T10:01:00+09:00'))
if __name__=='__main__':unittest.main()
