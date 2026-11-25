import unittest
from diagnostics.kyoto_weekend_sp_discovery import observed_kyoto_race_candidates
from diagnostics.kyoto_impl31_sp_saved_roster_audit import exact_mobile_race
DAY='20261128'
SEED='https://app.jra.jp/'
def url(prefix='01',venue='08',race=1,day=DAY,host='app.jra.jp'):
    return f'https://{host}/JRADB/accessD.html?CNAME=sw01dde{prefix}{venue}20260507{race:02d}{day}%2FAA'
def candidates(u,label='1R'):
    return observed_kyoto_race_candidates(f'<a href="{u}">{label}</a>'.encode(),SEED,DAY)
class ActualVariants(unittest.TestCase):
    def test_both_observed_forms(self):
        for prefix in ('01','10'):
            for n in range(1,13):
                u=url(prefix,race=n)
                self.assertEqual(candidates(u,f'{n}R')[str(n)],[u])
                self.assertTrue(exact_mobile_race(u,DAY,n))
    def test_other_prefix_rejected(self):
        for prefix in ('00','11','02','99'):
            u=url(prefix);self.assertEqual(candidates(u)['1'],[]);self.assertFalse(exact_mobile_race(u,DAY,1))
    def test_other_venue_day_host_or_number_rejected(self):
        for u in (url(venue='06'),url(day='20261129'),url(host='example.org'),url(race=2)):
            self.assertEqual(candidates(u)['1'],[]);self.assertFalse(exact_mobile_race(u,DAY,1))
    def test_opaque_suffix_not_rewritten(self):
        u=url('10').replace('%2FAA','%2F2e')
        self.assertEqual(candidates(u)['1'],[u])
    def test_two_observed_views_remain_ambiguous(self):
        a,b=url(),url('10')
        r=observed_kyoto_race_candidates(f'<a href="{a}">1R</a><a href="{b}">1R</a>'.encode(),SEED,DAY)
        self.assertEqual(r['1'],[a,b])
    def test_label_mismatch_and_missing(self):
        u=url('10');self.assertEqual(candidates(u,'2R')['1'],[]);self.assertEqual(candidates(u,'')['1'],[])
if __name__=='__main__':unittest.main()
