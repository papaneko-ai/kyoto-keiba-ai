import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from diagnostics.jra_p1_offline_handoff import export_bundle, import_bundle, EvidenceRejected

NOW = datetime(2026, 11, 13, 5, 0, tzinfo=timezone.utc)

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        raw = b'<html>offline test bytes</html>'
        (self.root/'race.html').write_bytes(raw)
        self.manifest = {'schema':'kyoto_p1_future_race_source_evidence.v1',
            'meeting_date':'2026-11-14','cutoff_utc':'2026-11-14T04:00:00Z',
            'sources':[{'kind':'racecard','race':1,'path':'race.html',
                'captured_utc':'2026-11-13T04:00:00Z',
                'sha256':hashlib.sha256(raw).hexdigest(), 'official_url_observed':True}]}
    def bundle(self):
        return export_bundle(self.manifest,self.root,observed_utc=NOW)
    def repack(self,bundle,change):
        with zipfile.ZipFile(io.BytesIO(bundle)) as z:
            items={n:z.read(n) for n in z.namelist()}
        change(items)
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_STORED) as z:
            for name,raw in items.items():z.writestr(name,raw)
        return b.getvalue()
    def test_round_trip(self):
        r=import_bundle(self.bundle(), observed_utc=NOW)
        self.assertFalse(r['prediction_ready'])
        self.assertEqual(r['network_requests'],0)
    def test_deterministic(self): self.assertEqual(self.bundle(),self.bundle())
    def test_zip_metadata_fixed_for_every_member(self):
        one=self.bundle()
        with zipfile.ZipFile(io.BytesIO(one)) as z:
            for info in z.infolist():
                self.assertEqual(info.date_time,(1980,1,1,0,0,0))
                self.assertEqual((info.external_attr >> 16)&0o777,0o600)
        self.assertEqual(hashlib.sha256(one).hexdigest(),
                         hashlib.sha256(self.bundle()).hexdigest())
    def test_read_old_valid_archive_with_variable_zip_dates(self):
        source=self.bundle()
        with zipfile.ZipFile(io.BytesIO(source)) as z:
            members={name:z.read(name) for name in z.namelist()}
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
            for name,content in members.items():
                info=zipfile.ZipInfo(name,date_time=(2026,11,10,15,30,2))
                info.compress_type=zipfile.ZIP_STORED
                z.writestr(info,content)
        old=output.getvalue()
        self.assertNotEqual(source,old)
        self.assertEqual(import_bundle(old,observed_utc=NOW)['source_count'],1)
    def test_modified_raw(self):
        b=self.repack(self.bundle(),lambda x:x.__setitem__('originals/source_01.html',b'tampered'))
        with self.assertRaises(EvidenceRejected):import_bundle(b,observed_utc=NOW)
    def test_unexpected_member(self):
        b=self.repack(self.bundle(),lambda x:x.__setitem__('extra.txt',b'x'))
        with self.assertRaises(EvidenceRejected):import_bundle(b,observed_utc=NOW)
    def test_manifest_mutation(self):
        b=self.repack(self.bundle(),lambda x:x.__setitem__('manifest.json',b'{}'))
        with self.assertRaises(EvidenceRejected):import_bundle(b,observed_utc=NOW)
    def test_receipt_ready_tampering(self):
        def f(x):
            r=json.loads(x['receipt.json']);r['prediction_ready']=True
            x['receipt.json']=json.dumps(r).encode()
        with self.assertRaises(EvidenceRejected):import_bundle(self.repack(self.bundle(),f),observed_utc=NOW)
    def test_future_receipt(self):
        with self.assertRaises(EvidenceRejected):import_bundle(self.bundle(),observed_utc='2026-11-13T04:30:00Z')
    def test_source_post_cutoff(self):
        self.manifest['sources'][0]['captured_utc']='2026-11-14T04:00:00Z'
        with self.assertRaises(EvidenceRejected):self.bundle()
    def test_bad_hash_before_export(self):
        self.manifest['sources'][0]['sha256']='0'*64
        with self.assertRaises(EvidenceRejected):self.bundle()
    def test_archive_too_large(self):
        with self.assertRaises(EvidenceRejected):import_bundle(b'x'*12000001,observed_utc=NOW)
    def test_corrupt_archive(self):
        with self.assertRaises(EvidenceRejected):import_bundle(b'notzip',observed_utc=NOW)
    def test_non_utc_observation(self):
        with self.assertRaises(EvidenceRejected):import_bundle(self.bundle(),observed_utc='2026-11-13T14:00:00+09:00')

if __name__=='__main__':unittest.main()
