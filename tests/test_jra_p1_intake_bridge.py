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


if __name__=='__main__':unittest.main()
