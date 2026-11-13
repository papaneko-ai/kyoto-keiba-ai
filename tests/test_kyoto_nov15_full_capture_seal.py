"""Encrypted full source-only Nov15 capture: mock source, no network."""
import json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_nov15_full_capture_seal import (
    encrypt_capture_directory,decrypt_capture_directory,EvidenceCryptoRejected)
KEY="1"*64
REPO="papaneko-ai/kyoto-keiba-ai"
class FullCaptureSealTests(unittest.TestCase):
 def setUp(self):
    t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
    self.path=Path(t.name)
    self.source=self.path/"capture";self.source.mkdir()
    self.dest=self.path/"encrypted";self.restored=self.path/"restored"
    (self.source/"nov15_preflight_receipt.json").write_text('{"state":"SYNTHETIC"}')
    sub=self.source/"captured";sub.mkdir()
    (sub/"official_racecard.html").write_bytes(b"<html>fake racecard</html>")
    (sub/"quinella_original.html").write_bytes(b"<html>synthetic quinella</html>")
    (sub/"bracket_quinella_original.html").write_bytes(b"<html>synthetic bracket</html>")
 def encrypt(self):return encrypt_capture_directory(self.source,self.dest,
        key_hex=KEY,repo=REPO,run_id="2134")
 def decrypt(self,**k):return decrypt_capture_directory(self.dest,self.restored,
        key_hex=k.get("key",KEY),repo=REPO,run_id=k.get("id","2134"))
 def test_roundtrip_all_originals(self):
    m=self.encrypt();r=self.decrypt()
    self.assertTrue(r["authenticated_encryption"])
    self.assertEqual(len(r["files"]),4)
    self.assertEqual((self.restored/"captured/quinella_original.html").read_bytes(),
                     (self.source/"captured/quinella_original.html").read_bytes())
 def test_public_artifact_has_no_plaintext(self):
    self.encrypt()
    self.assertEqual({x.name for x in self.dest.iterdir()},
                     {"capture.tar.gz.aesgcm","manifest.json"})
    self.assertNotIn(b"synthetic quinella",(self.dest/"capture.tar.gz.aesgcm").read_bytes())
 def test_wrong_key_fails(self):
    self.encrypt()
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt(key="2"*64)
 def test_wrong_run_fails(self):
    self.encrypt()
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt(id="2135")
 def test_modified_archive_fails(self):
    self.encrypt()
    f=self.dest/"capture.tar.gz.aesgcm";f.write_bytes(f.read_bytes()+b"E")
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt()
 def test_missing_preflight_receipt_fails(self):
    (self.source/"nov15_preflight_receipt.json").unlink()
    with self.assertRaisesRegex(EvidenceCryptoRejected,"preflight_receipt_missing"):
        self.encrypt()
 def test_symlink_source_fails(self):
    (self.source/"captured/quinella_original.html").unlink()
    (self.source/"captured/quinella_original.html").symlink_to(self.source/"captured/official_racecard.html")
    with self.assertRaises(EvidenceCryptoRejected):self.encrypt()
 def test_unexpected_directory_outside_parent_fails(self):
    self.encrypt()
    with self.assertRaises(EvidenceCryptoRejected):self.encrypt()
 def test_replay_archive_refuses_manifest_tamper(self):
    self.encrypt();p=self.dest/"manifest.json"
    d=json.loads(p.read_text());d["file_names"]=["nov15_preflight_receipt.json"]
    p.write_text(json.dumps(d))
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt()
 def test_nested_path_not_traversable(self):
    self.encrypt()
    p=self.dest/"manifest.json"
    d=json.loads(p.read_text());d["file_names"].append("../config.py")
    p.write_text(json.dumps(d))
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt()
if __name__=="__main__": unittest.main()
