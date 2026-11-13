"""Offline encrypted JRA originals; forbidden public plaintext and archive tamper."""
import json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_nov15_encrypted_evidence import (
    encrypt_evidence,decrypt_evidence,EvidenceCryptoRejected)
KEY="a"*64
REPO="papaneko-ai/kyoto-keiba-ai"
RUN="123456"
class CryptoTests(unittest.TestCase):
 def setUp(self):
    self.t=tempfile.TemporaryDirectory()
    self.addCleanup(self.t.cleanup)
    self.root=Path(self.t.name)
    self.raw=self.root/"raw";self.raw.mkdir()
    self.enc=self.root/"sealed"
    self.decrypted=self.root/"restored"
    (self.raw/"official_selection.html").write_bytes(b"<html>selection fixture</html>")
    (self.raw/"official_meeting.html").write_bytes(b"<html>meeting fixture</html>")
    (self.raw/"receipt.json").write_text('{"state":"OFFLINE_TEST"}')
 def seal(self):
    return encrypt_evidence(self.raw,self.enc,key_hex=KEY,repo=REPO,run_id=RUN)
 def restore(self,**kw):
    return decrypt_evidence(self.enc,self.decrypted,key_hex=kw.get("key",KEY),
                            repo=kw.get("repo",REPO),run_id=kw.get("run_id",RUN))
 def test_encrypted_archive_roundtrip(self):
    r=self.seal()
    self.assertTrue(r["encrypted_only"])
    x=self.restore()
    self.assertTrue(x["authentication_tag_verified"])
    self.assertEqual((self.decrypted/"official_selection.html").read_bytes(),
                     (self.raw/"official_selection.html").read_bytes())
 def test_no_plaintext_in_uploaded_output(self):
    self.seal()
    self.assertEqual({x.name for x in self.enc.iterdir()},
                     {"manifest.json","originals.tar.gz.aesgcm"})
    self.assertNotIn(b"selection fixture",(self.enc/"originals.tar.gz.aesgcm").read_bytes())
 def test_modified_ciphertext_refused(self):
    self.seal()
    path=self.enc/"originals.tar.gz.aesgcm"
    path.write_bytes(path.read_bytes()+b"X")
    with self.assertRaisesRegex(EvidenceCryptoRejected,"manifest_inconsistent"):
        self.restore()
 def test_wrong_key_refused(self):
    self.seal()
    with self.assertRaisesRegex(EvidenceCryptoRejected,"authentication_tag_failed"):
        self.restore(key="b"*64)
 def test_wrong_run_refused(self):
    self.seal()
    with self.assertRaisesRegex(EvidenceCryptoRejected,"manifest_inconsistent"):
        self.restore(run_id="123457")
 def test_wrong_repo_refused(self):
    self.seal()
    with self.assertRaisesRegex(EvidenceCryptoRejected,"manifest_inconsistent"):
        self.restore(repo="another/repository")
 def test_missing_encryption_key_refused(self):
    with self.assertRaisesRegex(EvidenceCryptoRejected,"AES256_SECRET_REQUIRED"):
        encrypt_evidence(self.raw,self.enc,key_hex="",repo=REPO,run_id=RUN)
 def test_symlink_plaintext_refused(self):
    (self.raw/"receipt.json").unlink()
    (self.raw/"receipt.json").symlink_to(self.raw/"official_meeting.html")
    with self.assertRaisesRegex(EvidenceCryptoRejected,"unexpected_original_file"):
        self.seal()
 def test_unknown_file_refused(self):
    (self.raw/"untrusted.txt").write_text("data")
    with self.assertRaisesRegex(EvidenceCryptoRejected,"unexpected_original_file"):
        self.seal()
 def test_manifest_tamper_refused(self):
    self.seal()
    path=self.enc/"manifest.json"
    obj=json.loads(path.read_text())
    obj["run_id"]="3"
    path.write_text(json.dumps(obj))
    with self.assertRaisesRegex(EvidenceCryptoRejected,"manifest_inconsistent"):
        self.restore()
 def test_missing_original_receipt_refused(self):
    (self.raw/"receipt.json").unlink()
    with self.assertRaisesRegex(EvidenceCryptoRejected,"unexpected_original_file"):
        self.seal()
 def test_output_existing_rejected(self):
    self.seal()
    with self.assertRaisesRegex(EvidenceCryptoRejected,"unsafe_source_or_destination"):
        self.seal()
if __name__=="__main__": unittest.main()
