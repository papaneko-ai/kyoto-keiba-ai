import copy
import unittest
from diagnostics.jra_p1_snapshot_gate import evaluate

NOW = '2026-11-13T04:30:00Z'
SHA = 'a'*64
BASE = {'schema':'kyoto_p1_prerace_snapshot.v1','meeting_date':'2026-11-14','race':1,
        'captured_utc':'2026-11-13T04:00:00Z', 'scheduled_start_utc':'2026-11-14T05:00:00Z',
        'prediction_cutoff_utc':'2026-11-14T04:55:00Z',
        'sources':{'racecard':{'sha256':SHA,'captured_utc':'2026-11-13T03:50:00Z'},
                   'odds':{'sha256':SHA,'captured_utc':'2026-11-13T03:59:00Z'}},
        'runners':[{'number':1,'horse_id':'horse001','name':'A'},
                   {'number':2,'horse_id':'horse002','name':'B'}],
        'odds':[{'first':1,'second':2,'decimal':4.1}]}

class GateTests(unittest.TestCase):
    def case(self, modify):
        d=copy.deepcopy(BASE)
        modify(d)
        return evaluate(d, observed_utc=NOW)
    def test_base_is_only_structural(self):
        x=self.case(lambda x:None)
        self.assertEqual(x['status'],'STRUCTURAL_CHECK_ONLY')
        self.assertFalse(x['prediction_ready'])
    def test_future_data(self):
        self.assertIn('future_capture',self.case(lambda x:x.update(captured_utc='2026-11-15T00:00:00Z'))['reasons'])
    def test_wrong_day(self):
        self.assertIn('start_meeting_date_mismatch',self.case(lambda x:x.update(meeting_date='2026-11-15'))['reasons'])
    def test_post_cutoff(self):
        self.assertIn('prerace_time_order_invalid',self.case(lambda x:x.update(captured_utc='2026-11-14T04:56:00Z'))['reasons'])
    def test_bad_sha(self):
        self.assertIn('odds_sha_invalid',self.case(lambda x:x['sources']['odds'].update(sha256='0'))['reasons'])
    def test_after_snapshot(self):
        self.assertIn('odds_later_than_snapshot',self.case(lambda x:x['sources']['odds'].update(captured_utc='2026-11-13T04:01:00Z'))['reasons'])
    def test_duplicate_horse(self):
        self.assertIn('runner_identity_duplicate',self.case(lambda x:x['runners'][1].update(horse_id='horse001'))['reasons'])
    def test_pair_mismatch(self):
        self.assertIn('odds_pair_unknown_runner',self.case(lambda x:x['odds'][0].update(first=3))['reasons'])
    def test_duplicate_pair(self):
        self.assertIn('odds_pair_duplicate',self.case(lambda x:x['odds'].append({'first':2,'second':1,'decimal':2.2}))['reasons'])
    def test_missing_market(self):
        self.assertIn('odds_missing',self.case(lambda x:x.update(odds=[]))['reasons'])
    def test_missing_source(self):
        self.assertIn('source_pair_missing',self.case(lambda x:x['sources'].pop('odds'))['reasons'])
    def test_bad_race(self):
        self.assertIn('race_invalid',self.case(lambda x:x.update(race=13))['reasons'])
    def test_idempotence(self):
        self.assertEqual(evaluate(BASE,observed_utc=NOW),evaluate(BASE,observed_utc=NOW))
    def test_never_ready_even_with_all_pairs(self):
        x=self.case(lambda x:None)
        self.assertFalse(x['prediction_ready'])
    def test_naive_observed_clock(self):
        x=evaluate(BASE,observed_utc='2026-11-13T04:30:00')
        self.assertEqual(x['status'],'BLOCKED')

if __name__=='__main__':unittest.main()
