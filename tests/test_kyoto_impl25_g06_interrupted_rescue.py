"""No-live-HTTP failure injection: interrupted G06 originals must survive AES."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_g06_nested_bundle import (
    BundleError,bundle_interrupted_g06,verify_bundle)
from diagnostics.kyoto_weekend_capture import seal
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence

DAY="20261121"

class InterruptedOriginalRescue(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        env=patch.dict(os.environ,{"KYOTO_TARGET_DAY":DAY})
        env.start()
        self.addCleanup(env.stop)
        crypto=patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY",DAY)
        crypto.start()
        self.addCleanup(crypto.stop)

    def source(self):
        src=self.root/"raw"
        src.mkdir()
        (src/"receipt.json").write_text(
            json.dumps({"day":DAY,"state":"PC_CAPTURE_EXCEPTION",
                        "prediction_ready":False}))
        nested=src/"g06_unsealed"
        (nested/"r01"/"pc").mkdir(parents=True)
        (nested/"r01"/"pc"/"quinella_original.html").write_bytes(
            b"<html>pre-existing market original, not independently authenticated</html>")
        return src,nested

    def test_interrupted_batch_original_roundtrips_inside_aes(self):
        src,nested=self.source()
        with self.assertRaisesRegex(BundleError,"batch_receipt_missing"):
            from diagnostics.kyoto_g06_nested_bundle import bundle_g06
            bundle_g06(nested,src/"g06_source_bundle.tar.gz")
        result=bundle_interrupted_g06(nested,src/"g06_source_bundle.tar.gz")
        self.assertEqual(result["state"],"G06_INTERRUPTED_ORIGINALS_BUNDLED_UNVERIFIED")
        self.assertFalse(nested.exists())
        self.assertEqual(verify_bundle(src/"g06_source_bundle.tar.gz")["verified_file_count"],2)
        dst=self.root/"sealed"
        seal(DAY,str(src),str(dst),key="ab"*32,
             repo="papaneko-ai/kyoto-keiba-ai",run_id="101")
        self.assertFalse(src.exists())
        decoded=self.root/"decrypted"
        evidence=decrypt_evidence(dst,decoded,key_hex="ab"*32,
               repo="papaneko-ai/kyoto-keiba-ai",run_id="101")
        self.assertTrue(evidence["authentication_tag_verified"])
        from io import BytesIO
        import tarfile
        with tarfile.open(decoded/"g06_source_bundle.tar.gz","r:gz") as archive:
            saved=archive.extractfile("r01/pc/quinella_original.html").read()
            receipt=json.load(archive.extractfile("g06_batch_receipt.json"))
        self.assertIn(b"pre-existing market original",saved)
        self.assertEqual(receipt["state"],"INTERRUPTED_BATCH_PARTIAL_ORIGINALS_ONLY")
        self.assertEqual(receipt["verified_dual_market_races"],0)
        self.assertFalse(receipt["prediction_ready"])

    def test_empty_tree_cannot_invent_acquisition(self):
        source=self.root/"empty"
        source.mkdir()
        with self.assertRaisesRegex(BundleError,"no_partial_originals"):
            bundle_interrupted_g06(source,self.root/"no.tar.gz")

    def test_existing_batch_receipt_must_not_be_rewritten(self):
        source=self.root/"existing"
        source.mkdir()
        (source/"g06_batch_receipt.json").write_text('{"state":"EXISTING"}')
        with self.assertRaisesRegex(BundleError,"not_an_interrupted_batch"):
            bundle_interrupted_g06(source,self.root/"no.tar.gz")
        self.assertEqual((source/"g06_batch_receipt.json").read_text(),'{"state":"EXISTING"}')

    def test_symlink_prohibited_and_no_archive_created(self):
        src,nested=self.source()
        (nested/"r02").symlink_to(nested/"r01",target_is_directory=True)
        with self.assertRaisesRegex(BundleError,"unsafe_interrupted_entry"):
            bundle_interrupted_g06(nested,src/"g06_source_bundle.tar.gz")
        self.assertFalse((src/"g06_source_bundle.tar.gz").exists())

if __name__ == "__main__":
    unittest.main()
