"""Regression tests for archive evidence loss and duplicate-work prevention."""
import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from diagnostics.kyoto_resume_gate import ResumeBlocked, blob_sha, check

SOURCE = Path(__file__).resolve().parents[1] / 'docs/diagnostics/jra_p1_batch14_96_profiles_20261106'

class ResumeGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        files = {
            'docs/requirements.md': b'P1-P8, ALG01-13, EVO01-08',
            'docs/prior_archive.md': b'artifact 13482994623 saved',
            'docs/diagnostics/status.json': (SOURCE / 'status.json').read_bytes(),
            'docs/diagnostics/rows.json': (SOURCE / 'feature_rows_148.json').read_bytes(),
        }
        proof={'artifact':{'artifact_id':13482994623,'workflow_run_id':42176719321,
               'outer_archive_sha256':'a'*64},
               'observed':{'pc_profile_sha_matches':84,'source_originals_missing':12,
               'valid_prior_rows_reparsed':485,'valid_prior_rows_missing_sources_registry_only':107,
               'feature_fields_independently_recomputed_and_equal':335},
               'prediction_ready':False,'training_ready':False}
        files['docs/diagnostics/replay.json'] = json.dumps(proof).encode()
        for name,data in files.items():
            dest=self.root / name
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(data)
        self.manifest={'schema':'kyoto_ai_resume_evidence_registry.v1',
            'required_files':{n:blob_sha(v) for n,v in files.items()},
            'status_path':'docs/diagnostics/status.json','registry_path':'docs/diagnostics/rows.json',
            'real_original_replay_path':'docs/diagnostics/replay.json',
            'recovery_artifact':{'id':13482994623,'run_id':42176719321,
                'sha256':'a'*64,'expires_at':'2027-02-04T06:47:55Z'},
            'portable_recovery':{'sha256':'b'*64}}
        self.metadata={'id':13482994623,'expired':False,'digest':'sha256:'+'a'*64,
                       'expires_at':'2027-02-04T06:47:55Z'}
        self.now=datetime(2026,11,9,tzinfo=timezone.utc)
    def audited(self,**kw):
        return check(self.root,self.manifest,at_utc=self.now,**kw)
    def test_blocks_resume_without_live_artifact_evidence(self):
        result=self.audited()
        self.assertEqual(result['decision'],'BLOCK_NEW_IMPLEMENTATION')
        self.assertEqual(result['preserved_recovery_artifact_id'],13482994623)
    def test_allows_resume_only_with_matching_artifact_metadata(self):
        r=self.audited(artifact_metadata=self.metadata)
        self.assertEqual(r['artifact_availability'],'CONFIRMED_BY_SUPPLIED_GITHUB_API_RESPONSE')
        self.assertEqual(r['already_reparsed_profiles'],84)
        self.assertEqual(r['original_profiles_missing'],12)
        self.assertFalse(r['live_JRA_http_authorized'])
    def test_rejects_expired_artifact(self):
        with self.assertRaisesRegex(ResumeBlocked,'live_artifact_metadata_conflict'):
            self.audited(artifact_metadata={**self.metadata,'expired':True})
    def test_rejects_wrong_archive_digest(self):
        with self.assertRaisesRegex(ResumeBlocked,'live_artifact_metadata_conflict'):
            self.audited(artifact_metadata={**self.metadata,'digest':'sha256:wrong'})
    def test_expired_at_date_blocks_even_with_stale_metadata(self):
        r=check(self.root,self.manifest,artifact_metadata=self.metadata,
                at_utc=datetime(2027,2,5,tzinfo=timezone.utc))
        self.assertEqual(r['decision'],'BLOCK_NEW_IMPLEMENTATION')
    def test_missing_original_receipt_blocks(self):
        (self.root/'docs/prior_archive.md').unlink()
        with self.assertRaisesRegex(ResumeBlocked,'source_missing_or_changed'):
            self.audited(artifact_metadata=self.metadata)
    def test_tampered_replay_receipt_blocks(self):
        p=self.root/'docs/diagnostics/replay.json'
        p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ResumeBlocked,'source_missing_or_changed'):
            self.audited(artifact_metadata=self.metadata)
    def test_wrong_84_replayed_fails_despite_rehashed_receipt(self):
        p=self.root/'docs/diagnostics/replay.json'
        obj=json.loads(p.read_text());obj['observed']['pc_profile_sha_matches']=0
        p.write_text(json.dumps(obj))
        self.manifest['required_files']['docs/diagnostics/replay.json']=blob_sha(p.read_bytes())
        with self.assertRaisesRegex(ResumeBlocked,'original_replay_receipt_conflict'):
            self.audited(artifact_metadata=self.metadata)
    def test_fabricated_prediction_ready_rejected(self):
        p=self.root/'docs/diagnostics/status.json'
        obj=json.loads(p.read_text());obj['prediction_ready']=True
        p.write_text(json.dumps(obj))
        self.manifest['required_files']['docs/diagnostics/status.json']=blob_sha(p.read_bytes())
        with self.assertRaisesRegex(ResumeBlocked,'p1_frozen_checkpoint_conflict'):
            self.audited(artifact_metadata=self.metadata)
    def test_duplicate_horse_identity_rejected(self):
        p=self.root/'docs/diagnostics/rows.json'
        obj=json.loads(p.read_text());obj[1]['race_number']=obj[0]['race_number'];obj[1]['horse_number']=obj[0]['horse_number']
        p.write_text(json.dumps(obj,ensure_ascii=False))
        self.manifest['required_files']['docs/diagnostics/rows.json']=blob_sha(p.read_bytes())
        with self.assertRaisesRegex(ResumeBlocked,'duplicated_horse_identity'):
            self.audited(artifact_metadata=self.metadata)
    def test_verified_local_recovery_allows_resume_without_api(self):
        archive=self.root/'portable.zip'
        with zipfile.ZipFile(archive,'w') as zf:
            zf.writestr('known.txt',b'held offline')
        self.manifest['portable_recovery']['sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
        r=self.audited(local_recovery=archive)
        self.assertEqual(r['artifact_availability'],'LOCAL_RECOVERY_BYTES_VERIFIED')
        self.assertFalse(r['live_JRA_http_authorized'])

    def test_portable_recovery_wrong_sha_rejected(self):
        archive=self.root/'portable.zip'
        with zipfile.ZipFile(archive,'w') as zf:
            zf.writestr('known.txt',b'held offline')
        with self.assertRaisesRegex(ResumeBlocked,'portable_recovery_sha_invalid'):
            self.audited(local_recovery=archive)

    def test_unsupported_timestamp_rejected(self):
        with self.assertRaisesRegex(ResumeBlocked,'clock_not_timezone_aware'):
            check(self.root,self.manifest,at_utc=datetime(2026,11,9))

if __name__=='__main__':unittest.main()
