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
 def _replace_encrypted_tar(self, members):
    import io,tarfile,hashlib
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from diagnostics.kyoto_nov15_encrypted_evidence import _aad
    self.encrypt()
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode="w:gz") as archive:
        for name,data in members:
            entry=tarfile.TarInfo(name);entry.size=len(data)
            archive.addfile(entry,io.BytesIO(data))
    manifest_path=self.dest/"manifest.json"
    manifest=json.loads(manifest_path.read_text())
    cipher=AESGCM(bytes.fromhex(KEY)).encrypt(bytes.fromhex(manifest["nonce_hex"]),
       raw.getvalue(),_aad(REPO,"2134")+b"|FULL_CAPTURE")
    (self.dest/"capture.tar.gz.aesgcm").write_bytes(cipher)
    manifest["ciphertext_sha256"]=hashlib.sha256(cipher).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
 def test_duplicate_archive_member_is_rejected(self):
    names=["nov15_preflight_receipt.json","captured/official_racecard.html",
           "captured/quinella_original.html","captured/bracket_quinella_original.html"]
    self._replace_encrypted_tar([(names[0],b"1"),(names[0],b"2"),
                                (names[2],b"3"),(names[3],b"4")])
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt()
 def test_decompression_total_overflow_is_rejected(self):
    names=["nov15_preflight_receipt.json","captured/official_racecard.html",
           "captured/quinella_original.html","captured/bracket_quinella_original.html"]
    self._replace_encrypted_tar([(n,b"0"*11_000_000) for n in names])
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt()
 def test_symlink_ciphertext_is_rejected(self):
    self.encrypt()
    p=self.dest/"capture.tar.gz.aesgcm";p.unlink();p.symlink_to(self.source/"captured/official_racecard.html")
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt()
 def test_duplicate_manifest_name_is_rejected(self):
    self.encrypt();p=self.dest/"manifest.json";m=json.loads(p.read_text())
    m["file_names"].append(m["file_names"][0]);p.write_text(json.dumps(m))
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt()
 def test_invalid_nonce_is_rejected(self):
    self.encrypt();p=self.dest/"manifest.json";m=json.loads(p.read_text())
    m["nonce_hex"]="z"*24;p.write_text(json.dumps(m))
    with self.assertRaises(EvidenceCryptoRejected):self.decrypt()
if __name__=="__main__": unittest.main()
