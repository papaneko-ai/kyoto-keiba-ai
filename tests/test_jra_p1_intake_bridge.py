import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.jra_p1_intake_bridge import inspect_bundle_and_snapshot, IntakeRejected

NOW='2026-11-13T05:00:00Z'


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        root=Path(self.dir.name)
        a=b'<html>racecard</html>'
        b=b'<html>odds</html>'
        (root/'a.html').write_bytes(a)
        (root/'b.html').write_bytes(b)
        self.sources=[{'kind':'racecard','race':1,'path':'a.html',
                       'captured_utc':'2026-11-13T04:00:00Z',
                       'sha256':hashlib.sha256(a).hexdigest(),'official_url_observed':True},
                      {'kind':'pre_race_odds','race':1,'path':'b.html',
                       'captured_utc':'2026-11-13T04:01:00Z',
                       'sha256':hashlib.sha256(b).hexdigest(),'official_url_observed':True}]
        self.manifest={'schema':'kyoto_p1_future_race_source_evidence.v1',
                       'meeting_date':'2026-11-14','cutoff_utc':'2026-11-14T04:50:00Z',
                       'sources':self.sources}
        self.root=root
        self.snapshot={'schema':'kyoto_p1_prerace_snapshot.v1',
                       'meeting_date':'2026-11-14','race':1,
                       'captured_utc':'2026-11-13T04:05:00Z',
                       'scheduled_start_utc':'2026-11-14T05:00:00Z',
                       'prediction_cutoff_utc':'2026-11-14T04:50:00Z',
                       'sources':{'racecard':{'sha256':self.sources[0]['sha256'],'captured_utc':self.sources[0]['captured_utc']},
                                  'odds':{'sha256':self.sources[1]['sha256'],'captured_utc':self.sources[1]['captured_utc']}},
                       'runners':[{'number':1,'horse_id':'horse0001','name':'A'},
                                  {'number':2,'horse_id':'horse0002','name':'B'}],
                       'odds':[{'first':1,'second':2,'decimal':3.5}]}

    def run_case(self, mutate_manifest=None, mutate_snapshot=None):
        manifest=copy.deepcopy(self.manifest)
        snapshot=copy.deepcopy(self.snapshot)
        if mutate_manifest:mutate_manifest(manifest)
        if mutate_snapshot:mutate_snapshot(snapshot)
        raw=export_bundle(manifest,self.root,observed_utc=NOW)
        return inspect_bundle_and_snapshot(raw,snapshot,observed_utc=NOW)

    def test_join_is_only_structural(self):
        result=self.run_case()
        self.assertEqual(result['status'],'OFFLINE_SOURCE_JOIN_ONLY')
        self.assertFalse(result['prediction_ready'])
        self.assertEqual(result['network_requests'],0)

    def test_deterministic(self):
        self.assertEqual(self.run_case(),self.run_case())

    def test_reject_cutoff_mismatch(self):
        with self.assertRaisesRegex(IntakeRejected,'cutoff_time_mismatch'):
            self.run_case(mutate_manifest=lambda m:m.update(cutoff_utc='2026-11-14T04:40:00Z'))

    def test_reject_expired_prediction_cutoff(self):
        raw=export_bundle(self.manifest,self.root,observed_utc=NOW)
        with self.assertRaisesRegex(IntakeRejected,'cutoff_already_elapsed'):
            inspect_bundle_and_snapshot(raw,self.snapshot,observed_utc='2026-11-14T04:51:00Z')

    def test_cutoff_equal_with_utc_alias(self):
        self.assertFalse(self.run_case(mutate_manifest=lambda m:m.update(cutoff_utc='2026-11-14T04:50:00+00:00'))['prediction_ready'])

    def test_wrong_race(self):
        with self.assertRaisesRegex(IntakeRejected,'race_number_mismatch'):
            self.run_case(mutate_snapshot=lambda s:s.update(race=2))

    def test_wrong_day(self):
        with self.assertRaisesRegex(IntakeRejected,'meeting_date_mismatch'):
            self.run_case(mutate_snapshot=lambda s:s.update(meeting_date='2026-11-15'))

    def test_sha_mismatch(self):
        with self.assertRaisesRegex(IntakeRejected,'original_sha_mismatch'):
            self.run_case(mutate_snapshot=lambda s:s['sources']['odds'].update(sha256='a'*64))

    def test_time_mismatch(self):
        with self.assertRaisesRegex(IntakeRejected,'capture_time_mismatch'):
            self.run_case(mutate_snapshot=lambda s:s['sources']['racecard'].update(captured_utc='2026-11-13T04:02:00Z'))

    def test_bad_runner(self):
        with self.assertRaisesRegex(IntakeRejected,'snapshot_structural_blocked'):
            self.run_case(mutate_snapshot=lambda s:s['runners'][1].update(horse_id='horse0001'))

    def test_missing_odds_original(self):
        with self.assertRaisesRegex(IntakeRejected,'requires_one_racecard_and_one_odds_original'):
            self.run_case(mutate_manifest=lambda m:m['sources'].pop())

    def test_reject_malformed_zip(self):
        with self.assertRaisesRegex(IntakeRejected,'source_bundle_invalid'):
            inspect_bundle_and_snapshot(b'not zip',self.snapshot,observed_utc=NOW)

    def test_future_timestamp(self):
        with self.assertRaisesRegex(IntakeRejected,'snapshot_structural_blocked'):
            self.run_case(mutate_snapshot=lambda s:s.update(captured_utc='2026-11-13T06:00:00Z'))

    def test_three_runner_complete_odds_join_stays_unapproved(self):
        def add(s):
            s['runners'].append({'number':3,'horse_id':'horse0003','name':'C'})
            s['odds'] += [
                {'first':1,'second':3,'decimal':4.1},
                {'first':2,'second':3,'decimal':6.3}]
        x=self.run_case(mutate_snapshot=add)
        self.assertEqual(x['expected_quinella_pairs'],3)
        self.assertEqual(x['market_coverage'],'STRUCTURAL_COMPLETE')
        self.assertFalse(x['prediction_ready'])

    def test_three_runner_partial_market_cannot_join(self):
        def add(s):
            s['runners'].append({'number':3,'horse_id':'horse0003','name':'C'})
        with self.assertRaisesRegex(IntakeRejected,'incomplete_quinella_pairs'):
            self.run_case(mutate_snapshot=add)

    def test_invalid_cutoff_is_controlled_rejection(self):
        raw=export_bundle(self.manifest,self.root,observed_utc=NOW)
        bad=copy.deepcopy(self.snapshot)
        bad['prediction_cutoff_utc']=None
        with self.assertRaisesRegex(IntakeRejected,'snapshot_structural_blocked'):
            inspect_bundle_and_snapshot(raw,bad,observed_utc=NOW)


    def dual_snapshot(self):
        s=copy.deepcopy(self.snapshot)
        s['runners'][0].update(bracket=1,status='ACTIVE')
        s['runners'][1].update(bracket=2,status='ACTIVE')
        s['bracket_odds']=[{'first':1,'second':2,'decimal':3.1}]
        s['market_states']={
            'quinella':{'sales':'OPEN','observed_utc':'2026-11-13T04:01:00Z'},
            'bracket':{'sales':'OPEN','observed_utc':'2026-11-13T04:02:00Z'}}
        return s

    def dual_case(self, modify=None, *, now=NOW):
        from diagnostics.jra_p1_intake_bridge import inspect_bundle_and_dual_snapshot
        raw=export_bundle(self.manifest,self.root,observed_utc=NOW)
        s=self.dual_snapshot()
        if modify:
            modify(s)
        return inspect_bundle_and_dual_snapshot(raw,s,observed_utc=now)

    def test_dual_offline_join_does_not_authorize_prediction(self):
        x=self.dual_case()
        self.assertEqual(x['status'],'OFFLINE_DUAL_MARKET_JOIN_ONLY')
        self.assertEqual(x['expected_bracket_pairs'],1)
        self.assertFalse(x['bracket_original_independently_verified'])
        self.assertFalse(x['prediction_ready'])
        self.assertFalse(x['actual_orders_authorized'])
        self.assertEqual(x['network_requests'],0)

    def test_dual_missing_bracket_pair_blocked(self):
        with self.assertRaisesRegex(IntakeRejected,'dual_market_not_structurally_complete'):
            self.dual_case(lambda s:s.update(bracket_odds=[]))

    def test_dual_duplicate_bracket_pair_rejected(self):
        with self.assertRaisesRegex(IntakeRejected,'dual_market_invalid:bracket_duplicate_pair'):
            self.dual_case(lambda s:s['bracket_odds'].append({'first':2,'second':1,'decimal':3.4}))

    def test_dual_sales_suspended_rejected(self):
        with self.assertRaisesRegex(IntakeRejected,'dual_market_not_structurally_complete'):
            self.dual_case(lambda s:s['market_states']['bracket'].update(sales='SUSPENDED'))

    def test_dual_false_origin_claim_never_authorized(self):
        x=self.dual_case(lambda s:s.update(official_origin_claimed=True))
        self.assertFalse(x['dual_market']['official_source_verified'])
        self.assertFalse(x['prediction_ready'])

    def test_dual_missing_market_state_rejected(self):
        with self.assertRaisesRegex(IntakeRejected,'dual_market_invalid:market_states_missing'):
            self.dual_case(lambda s:s.pop('market_states'))

    def test_dual_wrong_sha_rejected_before_market_check(self):
        with self.assertRaisesRegex(IntakeRejected,'original_sha_mismatch'):
            self.dual_case(lambda s:s['sources']['odds'].update(sha256='f'*64))

    def test_dual_expired_cutoff_rejected_before_market_check(self):
        with self.assertRaisesRegex(IntakeRejected,'cutoff_already_elapsed'):
            self.dual_case(now='2026-11-14T04:51:00Z')

    def test_dual_withdrawal_with_stale_market_fails_closed(self):
        with self.assertRaisesRegex(IntakeRejected,'snapshot_structural_blocked|dual_market_invalid'):
            self.dual_case(lambda s:s['runners'][1].update(status='WITHDRAWN'))

    def test_dual_repeatable_receipt(self):
        self.assertEqual(self.dual_case(),self.dual_case())



if __name__=='__main__':unittest.main()
