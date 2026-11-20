"""R30: compressed size cannot conceal oversized aggregate source originals."""
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_g06_nested_bundle import verify_bundle, BundleError


class ExtractedBoundTests(unittest.TestCase):
    def test_compressed_small_but_unpacked_originals_over_limit_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"synthetic.tar.gz"
            originals={
                "r01/pc/quinella_original.html":b"A"*800,
                "r02/pc/bracket_quinella_original.html":b"B"*800,
            }
            manifest={"schema":"kyoto_g06_nested_bundle.v1",
                      "files":{k:{"sha256":hashlib.sha256(v).hexdigest(),"bytes":len(v)}
                               for k,v in originals.items()}}
            data=dict(originals)
            data["g06_bundle_manifest.json"]=json.dumps(manifest,sort_keys=True).encode()
            with tarfile.open(path,"w:gz") as archive:
                for name,raw in data.items():
                    info=tarfile.TarInfo(name)
                    info.size=len(raw)
                    archive.addfile(info,io.BytesIO(raw))
            # Compression hides the 1,600 bytes of actual source originals.
            self.assertLess(path.stat().st_size,1000)
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch("diagnostics.kyoto_g06_nested_bundle.MAX_TOTAL",1000):
                with self.assertRaisesRegex(BundleError,"unbounded_original_total"):
                    verify_bundle(path)
            self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=="__main__":
    unittest.main()
