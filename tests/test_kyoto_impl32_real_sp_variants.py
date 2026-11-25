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
class SplitLayout(unittest.TestCase):
    def raw(self,cancel=False,day='28',race=1):
        h=f'<h1>出馬表</h1><h2 class="subTitle">2026年11月{day}日 京都</h2><h3 class="titleBox">{race}R</h3>'
        a='取消' if cancel else '1'
        return (h+f'<table><tr><td class="wban">1</td><td class="uban">{a}</td><td><a href="/JRADB/accessU.html">馬A</a></td></tr><tr><td class="wban">2</td><td class="uban">2</td><td><a href="/JRADB/accessU.html">馬B</a></td></tr></table>').encode('cp932')
    def test_layout_no_declared_count(self):
        from diagnostics.kyoto_impl31_sp_saved_roster_audit import inspect_observed_layout,inspect_heading
        a=inspect_observed_layout(self.raw(),DAY,1)
        self.assertEqual(a['numeric_row_count'],2);self.assertFalse(a['declared_runner_count_verified'])
        with self.assertRaises(ValueError):inspect_heading(self.raw(),DAY,1)
    def test_cancel_is_not_number_guess(self):
        from diagnostics.kyoto_impl31_sp_saved_roster_audit import inspect_observed_layout
        a=inspect_observed_layout(self.raw(True),DAY,1)
        self.assertEqual(a['state'],'SP_SPLIT_LAYOUT_PARTIAL');self.assertEqual(a['cancelled_number_unknown_count'],1);self.assertEqual(a['numeric_row_count'],1)
    def test_wrong_identity(self):
        from diagnostics.kyoto_impl31_sp_saved_roster_audit import inspect_observed_layout
        for b in (self.raw(day='29'),self.raw(race=2)):
            with self.assertRaises(ValueError):inspect_observed_layout(b,DAY,1)
    def test_partial_handoff_does_not_promote(self):
        from diagnostics.kyoto_impl31_sp_saved_roster_audit import inspect_observed_layout
        from diagnostics.kyoto_impl32_sp_handoff import aggregate
        from tests.test_kyoto_impl32_sp_handoff import entry
        e=entry(1,[1]);v=inspect_observed_layout(self.raw(True),DAY,1);v.update(source_sha256='a'*64,captured_at_utc='2026-11-28T01:00:00Z')
        e['source_assessment']['SP']['sp_saved_roster_audit']['races']['1']=v
        r=aggregate(DAY,[e])
        self.assertEqual(r['scheduled']['structural_roster_races'],0);self.assertEqual(r['scheduled']['split_layout_races'],1);self.assertFalse(r['live_acquisition_certified'])
if __name__=='__main__':unittest.main()
