import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.p1_three_original_dual_intake import (
    inspect_three_original_dual_intake, ThreeOriginalRejected)

NOW = '2026-11-13T05:00:00Z'


class ThreeOriginalIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = [('racecard', 'race.html', b'<html>racecard</html>', '2026-11-13T04:00:00Z'),
                 ('pre_race_odds', 'quinella.html', b'<html>quinella market</html>', '2026-11-13T04:01:00Z'),
                 ('bracket_odds', 'bracket.html', b'<html>bracket market</html>', '2026-11-13T04:02:00Z')]
        sources = []
        refs = {}
        for kind, path, raw, captured in files:
            (self.root/path).write_bytes(raw)
            sha = hashlib.sha256(raw).hexdigest()
            sources.append({'kind':kind,'race':1,'path':path,
                            'captured_utc':captured,'sha256':sha,'official_url_observed':True})
            refs[{'racecard':'racecard','pre_race_odds':'odds','bracket_odds':'bracket_odds'}[kind]] = {
                'sha256':sha,'captured_utc':captured}
        self.manifest = {'schema':'kyoto_p1_future_race_source_evidence.v1',
                         'meeting_date':'2026-11-14',
                         'cutoff_utc':'2026-11-14T04:50:00Z',
                         'sources':sources}
        self.snapshot = {
            'schema':'kyoto_p1_prerace_snapshot.v1',
            'meeting_date':'2026-11-14','race':1,
            'captured_utc':'2026-11-13T04:05:00Z',
            'scheduled_start_utc':'2026-11-14T05:00:00Z',
            'prediction_cutoff_utc':'2026-11-14T04:50:00Z',
            'sources':refs,
            'runners':[{'number':1,'horse_id':'horse0001','name':'A',
                        'bracket':1,'status':'ACTIVE'},
                       {'number':2,'horse_id':'horse0002','name':'B',
                        'bracket':2,'status':'ACTIVE'}],
            'odds':[{'first':1,'second':2,'decimal':3.1}],
            'bracket_odds':[{'first':1,'second':2,'decimal':4.1}],
            'market_states':{'quinella':{'sales':'OPEN','observed_utc':'2026-11-13T04:01:00Z'},
                             'bracket':{'sales':'OPEN','observed_utc':'2026-11-13T04:02:00Z'}}
        }

    def run_intake(self, mutate=None, *, observed_utc=NOW):
        snapshot = copy.deepcopy(self.snapshot)
        if mutate:
            mutate(snapshot)
        bundle = export_bundle(self.manifest,self.root,observed_utc=NOW)
        return inspect_three_original_dual_intake(bundle,snapshot,observed_utc=observed_utc)

    def test_three_independent_originals_are_bound_not_authenticated(self):
        r=self.run_intake()
        self.assertEqual(r['source_count'],3)
        self.assertEqual(set(r['source_sha256']),{'racecard','odds','bracket_odds'})
        self.assertTrue(r['source_bytes_independently_bound'])
        self.assertFalse(r['official_origin_authenticated'])
        self.assertFalse(r['prediction_ready'])
        self.assertFalse(r['actual_orders_authorized'])
        self.assertEqual(r['network_requests'],0)

    def test_missing_bracket_binding_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'three_source_bindings_required'):
            self.run_intake(lambda s:s['sources'].pop('bracket_odds'))

    def test_bracket_sha_mismatch_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'bracket_odds_sha_mismatch'):
            self.run_intake(lambda s:s['sources']['bracket_odds'].update(sha256='f'*64))

    def test_bracket_time_mismatch_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'bracket_odds_time_mismatch'):
            self.run_intake(lambda s:s['sources']['bracket_odds'].update(captured_utc='2026-11-13T04:03:00Z'))

    def test_bracket_odds_missing_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'dual_market_incomplete'):
            self.run_intake(lambda s:s.update(bracket_odds=[]))

    def test_withdrawn_horse_market_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'dual_market_invalid:too_few_active_horses'):
            self.run_intake(lambda s:s['runners'][1].update(status='WITHDRAWN'))

    def test_suspended_sales_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'dual_market_incomplete'):
            self.run_intake(lambda s:s['market_states']['bracket'].update(sales='SUSPENDED'))

    def test_cutoff_expired_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'snapshot_blocked|cutoff_elapsed'):
            self.run_intake(observed_utc='2026-11-14T04:51:00Z')

    def test_wrong_race_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'race_mismatch'):
            self.run_intake(lambda s:s.update(race=2))

    def test_wrong_date_rejected(self):
        with self.assertRaisesRegex(ThreeOriginalRejected,'snapshot_blocked|meeting_date_mismatch'):
            self.run_intake(lambda s:s.update(meeting_date='2026-11-15'))

    def test_independent_source_originals_required(self):
        raw=(self.root/'quinella.html').read_bytes()
        (self.root/'bracket.html').write_bytes(raw)
        sha=hashlib.sha256(raw).hexdigest()
        self.manifest['sources'][2]['sha256']=sha
        self.snapshot['sources']['bracket_odds']['sha256']=sha
        with self.assertRaisesRegex(ThreeOriginalRejected,'source_originals_not_independent'):
            self.run_intake()

    def test_stale_bracket_original_rejected(self):
        self.manifest['sources'][2]['captured_utc']='2026-11-13T03:00:00Z'
        self.snapshot['sources']['bracket_odds']['captured_utc']='2026-11-13T03:00:00Z'
        with self.assertRaisesRegex(ThreeOriginalRejected,'bracket_odds_market_stale'):
            self.run_intake()

    def test_rogue_ready_flag_ignored(self):
        r=self.run_intake(lambda s:s.update(prediction_ready=True,actual_orders_authorized=True))
        self.assertFalse(r['prediction_ready'])
        self.assertFalse(r['actual_orders_authorized'])

    def test_deterministic_bundle_and_snapshot_receipt(self):
        self.assertEqual(self.run_intake(),self.run_intake())


if __name__ == '__main__':
    unittest.main()
