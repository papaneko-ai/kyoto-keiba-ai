import hashlib
import tempfile
import unittest
from pathlib import Path
from diagnostics.jra_p1_future_evidence import verify, EvidenceRejected


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.root = Path(self.d.name)
        data = b'<html>local original</html>'
        (self.root / 'race.html').write_bytes(data)
        self.m = {'schema':'kyoto_p1_future_race_source_evidence.v1',
                  'meeting_date':'2026-11-14', 'cutoff_utc':'2026-11-14T04:00:00Z',
                  'sources':[{'kind':'racecard','race':1,'path':'race.html',
                              'captured_utc':'2026-11-13T04:00:00Z',
                              'sha256':hashlib.sha256(data).hexdigest(),
                              'official_url_observed':True}]}

    def test_consistent(self):
        r = verify(self.m, self.root)
        self.assertFalse(r['prediction_ready'])
        self.assertEqual(r['network_requests'], 0)

    def test_after_cutoff(self):
        self.m['sources'][0]['captured_utc'] = '2026-11-14T04:00:00Z'
        with self.assertRaises(EvidenceRejected): verify(self.m, self.root)

    def test_old_race(self):
        self.m['meeting_date'] = '2026-11-07'
        with self.assertRaises(EvidenceRejected): verify(self.m, self.root)

    def test_sha_conflict(self):
        self.m['sources'][0]['sha256'] = '0' * 64
        with self.assertRaises(EvidenceRejected): verify(self.m, self.root)

    def test_duplicate(self):
        self.m['sources'].append(dict(self.m['sources'][0]))
        with self.assertRaises(EvidenceRejected): verify(self.m, self.root)

    def test_path_escape(self):
        self.m['sources'][0]['path'] = '../outside.html'
        with self.assertRaises(EvidenceRejected): verify(self.m, self.root)

    def test_non_utc(self):
        self.m['sources'][0]['captured_utc'] = '2026-11-13T13:00:00+09:00'
        with self.assertRaises(EvidenceRejected): verify(self.m, self.root)

    def test_unobserved(self):
        self.m['sources'][0]['official_url_observed'] = False
        with self.assertRaises(EvidenceRejected): verify(self.m, self.root)


if __name__ == '__main__': unittest.main()
