"""R01 offline byte/time provenance acceptance, reusing established P1 intake."""
import copy, hashlib, io, unittest, zipfile
from pathlib import Path
from tests import test_jra_p1_intake_bridge as fixture
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.jra_p1_intake_bridge import inspect_bundle_and_snapshot, IntakeRejected
from diagnostics.jra_p1_future_evidence import EvidenceRejected
NOW=fixture.NOW
class R01Acceptance(unittest.TestCase):
    setUp=fixture.IntakeTests.setUp
    def join(self,man=None,snap=None,now=NOW):
        m=copy.deepcopy(self.manifest); s=copy.deepcopy(self.snapshot)
        if man: man(m)
        if snap: snap(s)
        return inspect_bundle_and_snapshot(export_bundle(m,self.root,observed_utc=NOW),s,observed_utc=now)
    def test_r01_structural_not_official(self):
        x=self.join()
        self.assertEqual(x['status'],'OFFLINE_SOURCE_JOIN_ONLY')
        self.assertFalse(x['prediction_ready'])
        self.assertEqual(x['network_requests'],0)
        self.assertIn('JRA_source_authenticity',x['unverified'])
    def test_r01_repeat(self): self.assertEqual(self.join(),self.join())
    def test_r01_missing_original(self):
        with self.assertRaises(IntakeRejected):self.join(man=lambda m:m['sources'].pop())
    def test_r01_duplicate_original(self):
        with self.assertRaises(EvidenceRejected):self.join(man=lambda m:m['sources'][1].update(kind='racecard'))
    def test_r01_wrong_sha(self):
        with self.assertRaises(IntakeRejected):self.join(snap=lambda s:s['sources']['odds'].update(sha256='a'*64))
    def test_r01_unobserved_url(self):
        with self.assertRaises(EvidenceRejected):self.join(man=lambda m:m['sources'][0].update(official_url_observed=False))
    def test_r01_missing_utc(self):
        with self.assertRaises(EvidenceRejected):self.join(man=lambda m:m['sources'][0].pop('captured_utc'))
    def test_r01_non_utc(self):
        with self.assertRaises(EvidenceRejected):self.join(man=lambda m:m['sources'][0].update(captured_utc='2026-11-13T13:00:00+09:00'))
    def test_r01_capture_time_mismatch(self):
        with self.assertRaises(IntakeRejected):self.join(snap=lambda s:s['sources']['odds'].update(captured_utc='2026-11-13T04:03:00Z'))
    def test_r01_other_race(self):
        with self.assertRaises(IntakeRejected):self.join(snap=lambda s:s.update(race=2))
    def test_r01_duplicate_runner(self):
        with self.assertRaises(IntakeRejected):self.join(snap=lambda s:s['runners'][1].update(number=1))
    def test_r01_future_capture(self):
        with self.assertRaises(EvidenceRejected):self.join(man=lambda m:m['sources'][0].update(captured_utc='2026-11-15T00:00:00Z'))
    def test_r01_cutoff_mismatch(self):
        with self.assertRaises(IntakeRejected):self.join(man=lambda m:m.update(cutoff_utc='2026-11-14T04:40:00Z'))
    def test_r01_corrupt_bytes(self):
        raw=export_bundle(self.manifest,self.root,observed_utc=NOW)
        with zipfile.ZipFile(io.BytesIO(raw)) as z: d={n:z.read(n) for n in z.namelist()}
        d['originals/source_01.html']=b'tampered'
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            for n,v in d.items(): z.writestr(n,v)
        with self.assertRaises(IntakeRejected):inspect_bundle_and_snapshot(b.getvalue(),self.snapshot,observed_utc=NOW)
    def test_r01_expired_cutoff(self):
        with self.assertRaises(IntakeRejected):self.join(now='2026-11-14T04:51:00Z')
