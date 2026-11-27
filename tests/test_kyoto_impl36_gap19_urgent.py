import unittest
from datetime import datetime,timezone
from diagnostics.kyoto_impl31_sp_gap_plan import plan_from_pc
DAY='20261129'
def pc(first='2026-11-29T00:40:00Z',pair=False,others=True):
    rows={'1':{'racecard':{'sha256':'a'*64,'utc':'2026-11-29T00:20:00Z'},'start_utc':first,'paired_same_slot':pair}}
    if others:rows['2']={'racecard':{'sha256':'b'*64,'utc':'2026-11-29T00:21:00Z'},'start_utc':'2026-11-29T01:10:00Z','paired_same_slot':False}
    return {'ciphertext_authenticated':True,'source_original_sha_utc_checked':True,'day_coverage_slot':{'day':DAY,'run_id':'42','races':rows}}
def plan(m,**kw):return plan_from_pc(pc(**kw),DAY,42,datetime(2026,11,29,0,m,tzinfo=timezone.utc))
class Urgent(unittest.TestCase):
 def test_actual_sunday_0932_missing_r1_first(self):
    p=plan(32);self.assertEqual(p['race_order'][0],1);self.assertEqual(p['urgent_prestart_missing_market_races'],[1]);self.assertNotIn('1',p['targets']);self.assertEqual(sorted(p['race_order']),list(range(1,13)))
 def test_0930_boundary(self):
    self.assertEqual(plan(30)['race_order'][0],1)
 def test_at_start_no_urgent(self):
    self.assertEqual(plan(40)['urgent_prestart_missing_market_races'],[])
 def test_after_start_no_urgent(self):
    self.assertEqual(plan(41)['urgent_prestart_missing_market_races'],[])
 def test_pc_pair_already_present_no_urgent(self):
    self.assertEqual(plan(32,pair=True)['urgent_prestart_missing_market_races'],[])
 def test_urgent_only_not_lost(self):
    p=plan(32,others=False);self.assertEqual(p['race_order'][0],1);self.assertEqual(sorted(p['race_order']),list(range(1,13)))
 def test_earlier_window_not_changed(self):
    p=plan(29);self.assertEqual(p['urgent_prestart_missing_market_races'],[]);self.assertIn('1',p['targets'])
 def test_deterministic(self):
    self.assertEqual(plan(32),plan(32))
if __name__=='__main__':unittest.main()
