"""Nested G06 original receipts fit the existing allowlisted AES-GCM archive."""
import json,os,tempfile,tarfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_g06_nested_bundle import bundle_g06,verify_bundle,BundleError,NAME
from diagnostics.kyoto_weekend_capture import seal
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence

class Tests(unittest.TestCase):
    def sample(self,folder):
        root=Path(folder)/"g06_unsealed"
        (root/"r11"/"pc").mkdir(parents=True)
        (root/"next_stage_inboxes").mkdir()
        (root/"r11"/"pc"/"quinella_original.html").write_bytes(b"OFFLINE_MARKET_ORIGINAL_ONLY")
        (root/"next_stage_inboxes"/"p4_market_source_intake.json").write_text("{}")
        (root/"g06_batch_receipt.json").write_text('{"prediction_ready":false}')
        return root
    def test_nested_originals_are_encryptable_and_restorable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            tree=self.sample(root)
            raw=root/"raw"
            raw.mkdir()
            (raw/"receipt.json").write_text('{"scope":"synthetic"}')
            nested=root/"raw"/NAME
            out=bundle_g06(tree,nested)
            self.assertEqual(out["source_file_count"],3)
            self.assertFalse(tree.exists())
            self.assertEqual(verify_bundle(nested)["verified_file_count"],3)
            with patch.dict(os.environ,{"KYOTO_TARGET_DAY":"20261121"}),patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY","20261121"):
                seal("20261121",str(raw),str(root/"sealed"),key="ab"*32,
                     repo="papaneko-ai/kyoto-keiba-ai",run_id="123456")
                self.assertFalse(raw.exists())
                decrypt_evidence(root/"sealed",root/"decrypted",key_hex="ab"*32,
                                 repo="papaneko-ai/kyoto-keiba-ai",run_id="123456")
            self.assertEqual(verify_bundle(root/"decrypted"/NAME)["verified_file_count"],3)
    def test_reject_symlink_without_deleting_source(self):
        with tempfile.TemporaryDirectory() as td:
            tree=self.sample(td)
            (tree/"r11"/"pc"/"link.html").symlink_to(tree/"r11"/"pc"/"quinella_original.html")
            with self.assertRaisesRegex(BundleError,"symlink"):
                bundle_g06(tree,Path(td)/NAME)
            self.assertTrue(tree.exists())
    def test_unknown_path_refused(self):
        with tempfile.TemporaryDirectory() as td:
            tree=self.sample(td)
            (tree/"../../oops") if False else None
            (tree/"unlisted.bin").write_bytes(b"junk")
            with self.assertRaisesRegex(BundleError,"unexpected"):
                bundle_g06(tree,Path(td)/NAME)
    def test_tampered_nested_manifest_refused(self):
        with tempfile.TemporaryDirectory() as td:
            tree=self.sample(td)
            archive=Path(td)/NAME
            bundle_g06(tree,archive)
            original=archive.read_bytes()
            archive.write_bytes(b"garbage")
            with self.assertRaises(Exception):
                verify_bundle(archive)
            archive.write_bytes(original)
            self.assertEqual(verify_bundle(archive)["verified_file_count"],3)
if __name__=="__main__":unittest.main()
