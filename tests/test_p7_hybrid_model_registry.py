"""Research-only model registry destructive and restoration regression."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.p7_hybrid_model_registry import (
    RegistryRejected, read_registry, register_model, registered_model)

H="a"*64
B="b"*64
C="c"*64

def sample(name="MODEL-A",kind="BASELINE",parents=None,weights=None,
           feature=H):
    return {"model_id":name,"kind":kind,"parents":parents or [],
            "feature_schema_sha256":feature,"code_sha256":B,
            "configuration_sha256":C,"training_end_utc":None,
            "source_scope":"LAB_RESEARCH_ONLY",
            "weights_bps":weights or []}

class HybridRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"models.jsonl"

    def base(self):
        return register_model(self.path,sample())

    def test_root_registration_is_replayable_and_unpromoted(self):
        r=self.base()
        self.assertEqual(r["registry_size"],1)
        self.assertFalse(r["auto_promote"])
        self.assertFalse(r["production_model_changed"])
        self.assertEqual(read_registry(self.path)["head"],r["event_sha256"])
        self.assertFalse(registered_model(self.path,"MODEL-A")["live_prediction_authorized"])

    def test_modify_and_add_keep_original(self):
        self.base()
        before=read_registry(self.path)["models"]["MODEL-A"]
        register_model(self.path,sample("MOD-1","MODIFY",["MODEL-A"]))
        register_model(self.path,sample("ADD-1","ADD",["MODEL-A"]))
        st=read_registry(self.path)
        self.assertEqual(len(st["models"]),3)
        self.assertEqual(st["models"]["MODEL-A"],before)

    def test_ensemble_fixed_weight_source(self):
        self.base()
        register_model(self.path,sample("MOD-1","MODIFY",["MODEL-A"]))
        register_model(self.path,sample("ADD-1","ADD",["MODEL-A"]))
        register_model(self.path,sample("ENS","ENSEMBLE",["MOD-1","ADD-1"],[6500,3500]))
        e=registered_model(self.path,"ENS")
        self.assertEqual(e["model"]["weights_bps"],[6500,3500])
        self.assertFalse(e["independently_certified"])

    def test_no_duplicate_registration(self):
        self.base()
        initial=self.path.read_bytes()
        with self.assertRaisesRegex(RegistryRejected,"duplicate"):
            self.base()
        self.assertEqual(initial,self.path.read_bytes())

    def test_ghost_parent_blocked_without_append(self):
        self.base()
        initial=self.path.read_bytes()
        with self.assertRaisesRegex(RegistryRejected,"parent_missing"):
            register_model(self.path,sample("ADD","ADD",["not-there"]))
        self.assertEqual(initial,self.path.read_bytes())

    def test_wrong_source_feature_schema_rejected(self):
        self.base()
        with self.assertRaisesRegex(RegistryRejected,"feature_schema_incompatible"):
            register_model(self.path,sample("ADD","ADD",["MODEL-A"],feature=C))

    def test_incomplete_ensemble_weights_rejected(self):
        self.base()
        register_model(self.path,sample("MOD-1","MODIFY",["MODEL-A"]))
        with self.assertRaisesRegex(RegistryRejected,"ensemble_fixed_weights_invalid"):
            register_model(self.path,sample("ENS","ENSEMBLE",["MODEL-A","MOD-1"],[9000,900]))

    def test_extra_field_claiming_real_certified_rejected(self):
        spec=sample()
        spec["independently_certified"]=True
        with self.assertRaisesRegex(RegistryRejected,"schema_invalid"):
            register_model(self.path,spec)
        self.assertFalse(self.path.exists())

    def test_live_source_cannot_be_registered_as_lab(self):
        spec=sample()
        spec["source_scope"]="JRA_OFFICIAL_AUTHENTICATED"
        with self.assertRaisesRegex(RegistryRejected,"nonlab_scope"):
            register_model(self.path,spec)

    def test_registry_history_mutation_is_detected(self):
        self.base()
        raw=self.path.read_bytes()
        forged=raw.replace(b"MODEL-A",b"MODEL-B")
        self.path.write_bytes(forged)
        with self.assertRaisesRegex(RegistryRejected,"registry_chain_corrupted"):
            read_registry(self.path)

    def test_partial_file_refused(self):
        self.base()
        self.path.write_bytes(self.path.read_bytes().rstrip(b"\n"))
        with self.assertRaisesRegex(RegistryRejected,"partial_or_empty_registry"):
            read_registry(self.path)

    def test_race_concurrent_lock_rejected(self):
        lock=Path(str(self.path)+".lock")
        lock.write_text("BUSY")
        with self.assertRaisesRegex(RegistryRejected,"concurrent_writer_lock"):
            self.base()
        self.assertEqual(lock.read_text(),"BUSY")

    def test_symlink_registry_refused(self):
        original=Path(self.tmp.name)/"original"
        original.write_text("sensitive")
        self.path.symlink_to(original)
        with self.assertRaisesRegex(RegistryRejected,"registry_parent_or_symlink_invalid"):
            self.base()
        self.assertEqual(original.read_text(),"sensitive")

    def test_stable_replay_across_restart(self):
        self.base()
        register_model(self.path,sample("MOD-1","MODIFY",["MODEL-A"]))
        before=self.path.read_bytes()
        a=read_registry(self.path)
        b=read_registry(self.path)
        self.assertEqual(a,b)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(a["models"]["MOD-1"]["parents"],["MODEL-A"])

    def test_utc_training_end_required(self):
        self.base()
        candidate=sample("MOD-1","MODIFY",["MODEL-A"])
        candidate["training_end_utc"]="2026-11-13T09:00:00+09:00"
        with self.assertRaisesRegex(RegistryRejected,"training_time_not_utc"):
            register_model(self.path,candidate)

    def test_fake_valid_self_hash_cannot_promote(self):
        self.base()
        data=json.loads(self.path.read_text().strip())
        data["event"]["model"]["source_scope"]="LIVE_PRODUCTION"
        data["event_sha256"]=hashlib.sha256(
            json.dumps({k:v for k,v in data.items() if k!="event_sha256"},
                       sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        self.path.write_text(json.dumps(data)+"\n")
        with self.assertRaisesRegex(RegistryRejected,"nonlab_scope"):
            read_registry(self.path)

if __name__=="__main__":
    unittest.main()
