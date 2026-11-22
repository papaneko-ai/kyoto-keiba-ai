"""Independent Nov28/29 readiness plan invariants and destructive checks."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_next_weekend_readiness_from_evidence import prepare,DAYS
from diagnostics.kyoto_evidence_complete_family_ledger import build
from tests.test_kyoto_evidence_complete_family_ledger import fixtures

class NextWeekendPreflight(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.root.joinpath("evidence/2026-11-21_22").mkdir(parents=True)
        a,b=fixtures()
        self.previous=build(a,b,day="20261122")
        files=[]
        for i in range(18):
            path=f"evidence/2026-11-21_22/synthetic_{i:02d}.aesgcm"
            data=b"synthetic-encrypted-evidence-"+bytes([i])
            self.root.joinpath(path).write_bytes(data)
            files.append({"path":path,"sha256":hashlib.sha256(data).hexdigest(),
                          "size":len(data),"kind":"ENCRYPTED_SOURCE"})
        self.manifest={"schema":"kyoto_encrypted_evidence_archive.v1",
             "source_runs":{"failure":[44848944302,44854931835,44857934629,44861934823],
                "all12":44966013490,"g03":44966654858,"ledger":44983258092},
             "files":files}
        self.write_manifest()
    def write_manifest(self):
        (self.root/"evidence/2026-11-21_22/ARCHIVE_MANIFEST.json").write_text(
            json.dumps(self.manifest),encoding="utf8")
    def test_two_days_all_nine_families_no_false_live_success(self):
        result=prepare(self.root,self.previous)
        self.assertEqual(result["days"],list(DAYS))
        self.assertEqual(len(result["target_cells"]),216)
        self.assertEqual(len({(x["race_day"],x["race"],x["family"]) for x in result["target_cells"]}),216)
        self.assertFalse(result["actual_next_weekend_data_captured"])
        self.assertFalse(result["next_week_end_to_end_GO"])
        self.assertTrue(all(x["source_url"] is None for x in result["target_cells"]))
        self.assertTrue(result["old_nov22_CNAME_REUSE_FOR_NEW_DAY_FORBIDDEN"])
        self.assertTrue(result["unreviewed_auto_patch_execution_prohibited"])
        self.assertEqual(len(result["unresolved_prior_data_families"]),7)
        self.assertEqual(sum(x["phase"]=="POST_RESULT" for x in result["target_cells"]),48)
    def test_original_archive_mutation_fails(self):
        file=self.root/self.manifest["files"][2]["path"]
        file.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError,"archived_source_byte_difference"):
            prepare(self.root,self.previous)
    def test_ledger_rewrite_without_sha_change_fails(self):
        copy_ledger=copy.deepcopy(self.previous)
        copy_ledger["records"][0]["state"]="CONFLICT"
        with self.assertRaisesRegex(ValueError,"prior_ledger_digest_mismatch"):
            prepare(self.root,copy_ledger)
    def test_archive_duplicate_or_missing_fails(self):
        self.manifest["files"][-1]["path"]=self.manifest["files"][0]["path"]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError,"archive_file_count_or_duplicates"):
            prepare(self.root,self.previous)
    def test_wrong_historic_run_fails(self):
        self.manifest["source_runs"]["failure"]=[1,2,3,4]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError,"historic_failure_runs_incomplete"):
            prepare(self.root,self.previous)
    def test_prior_12r_g03_not_success_cannot_promote(self):
        copy_ledger=copy.deepcopy(self.previous)
        copy_ledger["counts"]["roster"]["STRUCTURED_VERIFIED"]=11
        body={k:v for k,v in copy_ledger.items() if k!="content_sha256"}
        copy_ledger["content_sha256"]=hashlib.sha256(json.dumps(
            body,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,"prior_real_12_source_not_proven|prior_12_g03_not_proven|previous_family_count_inconsistent"):
            prepare(self.root,copy_ledger)

if __name__=="__main__":unittest.main()
