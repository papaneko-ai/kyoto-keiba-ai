"""One test-only AES-GCM artifact lifecycle across two isolated Actions jobs.

Synthetic original bytes exclusively. Never claim this is official JRA evidence.
"""
import argparse,hashlib,json,os,shutil
from pathlib import Path
from diagnostics.kyoto_weekend_capture import seal
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
DAY="20261121"
REPO="papaneko-ai/kyoto-keiba-ai"
RUN="202611180001"
KEY="ab"*32
PAYLOAD=b"OFFLINE_FIXTURE_NOT_JRA_PC_ORIGINAL_20261121\n"

def produce(root:Path):
    source=root/"source"
    source.mkdir(parents=True)
    (source/"official_selection.html").write_bytes(PAYLOAD)
    (source/"receipt.json").write_text(json.dumps({
        "schema":"mock_ci_original.v1","day":DAY,"channel":"PC",
        "state":"OFFLINE_FIXTURE","source_verified":False,
        "prediction_ready":False,"live_http_requests":0})+"\n")
    os.environ["KYOTO_TARGET_DAY"]=DAY
    encrypted=root/"artifact"/"cipher"
    encrypted.parent.mkdir(parents=True)
    seal(DAY,str(source),str(encrypted),key=KEY,repo=REPO,run_id=RUN)
    if source.exists():
        raise AssertionError("plaintext_not_destroyed_after_successful_seal")
    if (encrypted/"official_selection.html").exists():
        raise AssertionError("plaintext_in_artifact")
    if not (encrypted/"manifest.json").is_file() or not (encrypted/"originals.tar.gz.aesgcm").is_file():
        raise AssertionError("ciphertext_missing")
    manifest={"schema":"kyoto_mock_two_job_crypto_v1","plaintext_sha256":hashlib.sha256(PAYLOAD).hexdigest(),
        "ciphertext_sha256":hashlib.sha256((encrypted/"originals.tar.gz.aesgcm").read_bytes()).hexdigest(),
        "encrypted_files":["manifest.json","originals.tar.gz.aesgcm"],
        "fixture_only":True,"live_http_requests":0,"original_content_not_released":True}
    (root/"artifact"/"fixture_receipt.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("SYNTHETIC_ENCRYPTION_ARTIFACT_READY")

def consume(root:Path):
    bundle=root/"artifact"
    receipt=json.loads((bundle/"fixture_receipt.json").read_text())
    encrypted=bundle/"cipher"
    original=(encrypted/"originals.tar.gz.aesgcm").read_bytes()
    if hashlib.sha256(original).hexdigest()!=receipt["ciphertext_sha256"]:
        raise AssertionError("ciphertext_artifact_sha_mismatch")
    output=root/"recovered"
    result=decrypt_evidence(encrypted,output,key_hex=KEY,repo=REPO,run_id=RUN)
    if result["authentication_tag_verified"] is not True:
        raise AssertionError("aes_gcm_tag_not_proven")
    raw=(output/"official_selection.html").read_bytes()
    if raw!=PAYLOAD or hashlib.sha256(raw).hexdigest()!=receipt["plaintext_sha256"]:
        raise AssertionError("plaintext_restoration_sha_mismatch")
    meta=json.loads((output/"receipt.json").read_text())
    if meta["source_verified"] is not False or meta["live_http_requests"]!=0:
        raise AssertionError("synthetic_misrepresented_as_live")
    shutil.rmtree(output)
    (root/"recovered_report.json").write_text(json.dumps({
        "schema":"kyoto_mock_two_job_crypto_verified.v1","synthetic_only":True,
        "artifact_downloaded_into_second_job":True,
        "aes_gcm_tag_verified":True,"original_sha256_equal":True,
        "no_official_http":True,"plaintext_retained_after_test":False,
        "previous_capture_success_claim":False},indent=2)+"\n")
    print("SYNTHETIC_ARTIFACT_INDEPENDENT_RESTORE_SUCCESS")
    tampered=root/"damaged"
    shutil.copytree(encrypted,tampered)
    raw=bytearray((tampered/"originals.tar.gz.aesgcm").read_bytes())
    raw[-1]^=1
    (tampered/"originals.tar.gz.aesgcm").write_bytes(bytes(raw))
    try:
        decrypt_evidence(tampered,root/"should_not_recover",key_hex=KEY,repo=REPO,run_id=RUN)
    except Exception:
        print("TAMPERED_ARTIFACT_REJECTED")
    else:
        raise AssertionError("tampered_archive_was_accepted")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["produce","consume"])
    p.add_argument("--root",type=Path,required=True)
    args=p.parse_args()
    (produce if args.action=="produce" else consume)(args.root)
if __name__=="__main__":main()
