"""Destructive tests: document-only shrink, missing source, SHA and prior backup."""
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from diagnostics.kyoto_impl25_migration_release_gate import verify

def sha(b): return hashlib.sha256(b).hexdigest()
def zipb(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_STORED) as z:
        for k,v in entries.items(): z.writestr(k,v)
    return out.getvalue()

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prev=Path(self.tmp.name)/'prior.zip'
        self.new=Path(self.tmp.name)/'new.zip'
        self.sources=zipb({'diagnostics/code%04d.py'%i:b'# source\n' for i in range(1100)})
        self.prev.write_bytes(zipb({'source.zip':self.sources,'large.bin':b'X'*2_000_000}))
        self.make()
    def make(self,**flags):
        e={'01_START_HERE.md':b'start',
           '02_MIGRATION_INSTRUCTIONS.md':b'G03 G04 G05 G06',
           '00_PREVIOUS_SOURCE.zip':self.prev.read_bytes(),
           '01_LATEST_SOURCE.zip':self.sources}
        if flags.get('remove_previous'): e.pop('00_PREVIOUS_SOURCE.zip')
        if flags.get('remove_guide'): e.pop('02_MIGRATION_INSTRUCTIONS.md')
        if flags.get('corrupt_previous'): e['00_PREVIOUS_SOURCE.zip']=e['00_PREVIOUS_SOURCE.zip'][:-1]+b'!'
        if flags.get('current'):
            e['02_LATEST_GIT_SNAPSHOT.zip']=zipb({
               'source/source/main/app.py':b'a',
               'source/source/development/module.py':b'b',
               'source/source/history/repository-all-refs.bundle':b'gitbundle'})
        if not flags.get('remove_manifest'):
            e['SHA256_MANIFEST.json']=json.dumps({'contents':{
               n:{'bytes':len(b),'sha256':sha(b)} for n,b in e.items()}}).encode()
        self.new.write_bytes(zipb(e))
    def test_valid_historical_backup(self):
        self.assertEqual(verify(self.new,self.prev)['status'],'PASS')
    def test_valid_current_snapshot(self):
        self.make(current=True)
        self.assertEqual(verify(self.new,self.prev,require_current=True)['status'],'PASS')
    def test_doc_only_49kb_type_is_blocked(self):
        self.new.write_bytes(zipb({'01_START_HERE.md':b'a','02_MIGRATION_INSTRUCTIONS.md':b'a'}))
        with self.assertRaisesRegex(ValueError,'CAPACITY_COLLAPSE'):
            verify(self.new,self.prev)
    def test_prior_zip_missing(self):
        self.make(remove_previous=True)
        with self.assertRaises(ValueError): verify(self.new,self.prev)
    def test_prior_zip_modified(self):
        self.make(corrupt_previous=True)
        with self.assertRaisesRegex(ValueError,'PREVIOUS_FULL_SOURCE'):
            verify(self.new,self.prev)
    def test_manifest_missing(self):
        self.make(remove_manifest=True)
        with self.assertRaisesRegex(ValueError,'CONTENT_MANIFEST_MISSING'):
            verify(self.new,self.prev)
    def test_guide_missing(self):
        self.make(remove_guide=True)
        with self.assertRaisesRegex(ValueError,'INSTRUCTIONS_MISSING'):
            verify(self.new,self.prev)
    def test_old_source_is_not_current_source(self):
        with self.assertRaisesRegex(ValueError,'LATEST_MAIN_DEV_GIT_BUNDLE_MISSING'):
            verify(self.new,self.prev,require_current=True)
    def test_source_count_missing(self):
        self.prev.write_bytes(zipb({'only_filler.bin':b'X'*2_000_000}))
        self.sources=zipb({'only_notes.md':b'notes'})
        self.make()
        with self.assertRaisesRegex(ValueError,'SOURCE_COUNT_COLLAPSE'):
            verify(self.new,self.prev)
    def test_zip_corruption(self):
        self.new.write_bytes(b'broken ZIP')
        with self.assertRaises(ValueError): verify(self.new,self.prev,minimum_ratio=.5)

if __name__=='__main__': unittest.main()
