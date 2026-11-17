"""Self-test: a missing or altered predecessor cannot pass cumulative backup guard."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from diagnostics.kyoto_backup_chain_guard import verify

def zip_bytes(contents):
    s=io.BytesIO()
    with zipfile.ZipFile(s,"w",zipfile.ZIP_DEFLATED) as z:
        for name,data in contents.items():
            z.writestr(name,data)
    return s.getvalue()

def manifest_archive(contents, *, extra=None):
    obj=dict(contents)
    obj["SHA256_MANIFEST.json"]=json.dumps({
        "contents":{name:{"sha256":hashlib.sha256(b).hexdigest(),"bytes":len(b)}
                    for name,b in contents.items()}})
    if extra:obj.update(extra)
    return zip_bytes(obj)

class BackupChainGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d=Path(self.tmp.name)
        self.prior=d/"previous.zip"
        self.prior.write_bytes(manifest_archive({"old_source.py":b"historical-important-bytes"}))
        self.current=zip_bytes({"source/main/app.py":b"new"})
        self.instruction=b"Continue 12 gates"
        self.next=d/"next.zip"

    def make(self, *, previous=True, previous_bytes=None, manifest_ok=True):
        contents={"LATEST_SOURCE.zip":self.current,
                  "START_HERE.md":self.instruction}
        if previous:
            contents["PREVIOUS_COMPLETE.zip"]=previous_bytes if previous_bytes is not None else self.prior.read_bytes()
        data=manifest_archive(contents)
        if not manifest_ok:
            data=zip_bytes({**contents,"SHA256_MANIFEST.json":b"{}"})
        self.next.write_bytes(data)

    def test_complete_cumulative_passes(self):
        self.make()
        self.assertEqual(verify(self.next,self.prior)["result"],"PASS")

    def test_missing_previous_fails(self):
        self.make(previous=False)
        with self.assertRaisesRegex(ValueError,"PREVIOUS_ZIP_MISSING"):
            verify(self.next,self.prior)

    def test_modified_previous_fails(self):
        self.make(previous_bytes=manifest_archive({"old_source.py":b"replaced"}))
        with self.assertRaisesRegex(ValueError,"PREVIOUS_ZIP_MISSING"):
            verify(self.next,self.prior)

    def test_fake_manifest_fails(self):
        self.make(manifest_ok=False)
        with self.assertRaisesRegex(ValueError,"MANIFEST_EMPTY"):
            verify(self.next,self.prior)

    def test_no_latest_content_fails(self):
        self.next.write_bytes(manifest_archive({
            "PREVIOUS_COMPLETE.zip":self.prior.read_bytes(),"START_HERE.md":b"Instructions"}))
        with self.assertRaisesRegex(ValueError,"NEW_SOURCE_OR_WORK_ZIP_MISSING"):
            verify(self.next,self.prior)

    def test_builder_creates_verified_cumulative_backup(self):
        from diagnostics.kyoto_build_cumulative_migration import build
        latest=Path(self.tmp.name)/"latest.zip"
        latest.write_bytes(self.current)
        guide=Path(self.tmp.name)/"handoff.md"
        guide.write_text("Kyoto AI full data acquisition gates G01 through G12. Continue after verifying GitHub SHA and the prior archive.")
        result=build(self.prior,latest,guide,self.next)
        self.assertEqual(result["result"],"PASS")
        self.assertEqual(verify(self.next,self.prior)["result"],"PASS")
        self.assertTrue(self.next.with_name(self.next.stem+"_VERIFICATION.json").is_file())

    def test_builder_refuses_missing_previous(self):
        from diagnostics.kyoto_build_cumulative_migration import build
        latest=Path(self.tmp.name)/"latest.zip"
        latest.write_bytes(self.current)
        guide=Path(self.tmp.name)/"handoff.md"
        guide.write_text("Kyoto AI full data acquisition gates G01 through G12. Continue after verifying GitHub SHA and the prior archive.")
        with self.assertRaises(FileNotFoundError):
            build(Path(self.tmp.name)/"missing.zip",latest,guide,self.next)

    def test_previous_archive_corruption_fails(self):
        self.prior.write_bytes(b"bad")
        self.make()
        with self.assertRaisesRegex(ValueError,"NOT_ZIP"):
            verify(self.next,self.prior)

if __name__=="__main__":unittest.main()
