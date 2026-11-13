"""Encrypt a bounded full capture directory, including nested P1 receipts.

Never upload plaintext HTML artifacts on a public repository.
"""
from __future__ import annotations
import hashlib,io,json,re,secrets,tarfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from diagnostics.kyoto_nov15_encrypted_evidence import _key,_aad,EvidenceCryptoRejected

MAX_FILES=90
MAX_FILE=1_500_000
MAX_TOTAL=40_000_000

def encrypt_capture_directory(source,out,*,key_hex,repo,run_id):
    key=_key(key_hex);aad=_aad(repo,run_id)+b"|FULL_CAPTURE"
    src=Path(source);dst=Path(out)
    if (src.is_symlink() or not src.is_dir() or
        dst.exists() or not dst.parent.is_dir()):
        raise EvidenceCryptoRejected("full_capture_source_or_output_invalid")
    files=sorted(src.rglob("*"))
    if (not files or len(files)>MAX_FILES or
        any(x.is_symlink() or (not x.is_file() and not x.is_dir()) for x in files)):
        raise EvidenceCryptoRejected("full_capture_file_inventory_unsafe")
    regular=[p for p in files if p.is_file()]
    if sum(p.stat().st_size for p in regular)>MAX_TOTAL:
        raise EvidenceCryptoRejected("full_capture_size_exceeded")
    if any(not 0<p.stat().st_size<=MAX_FILE for p in regular):
        raise EvidenceCryptoRejected("full_capture_individual_size_invalid")
    names=[str(x.relative_to(src).as_posix()) for x in regular]
    if (any(not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*",n)
            or ".." in n.split("/") for n in names)
        or len(names)!=len(set(names))):
        raise EvidenceCryptoRejected("unsafe_capture_filename")
    if "nov15_preflight_receipt.json" not in names:
        raise EvidenceCryptoRejected("preflight_receipt_missing")
    buff=io.BytesIO()
    with tarfile.open(fileobj=buff,mode="w:gz") as archive:
        for path,name in zip(regular,names):
            data=path.read_bytes()
            member=tarfile.TarInfo(name)
            member.size=len(data)
            archive.addfile(member,io.BytesIO(data))
    nonce=secrets.token_bytes(12)
    sealed=AESGCM(key).encrypt(nonce,buff.getvalue(),aad)
    dst.mkdir()
    (dst/"capture.tar.gz.aesgcm").write_bytes(sealed)
    m={"schema":"kyoto_nov15_full_capture_aesgcm.v1",
       "day":"20261115","repo":repo,"run_id":str(run_id),
       "ciphertext_sha256":hashlib.sha256(sealed).hexdigest(),
       "nonce_hex":nonce.hex(),"encryption":"AES-256-GCM",
       "file_names":names,"originals_not_uploaded_plaintext":True}
    (dst/"manifest.json").write_text(json.dumps(m,sort_keys=True,indent=2)+"\n")
    return m

def decrypt_capture_directory(source,out,*,key_hex,repo,run_id):
    key=_key(key_hex);aad=_aad(repo,run_id)+b"|FULL_CAPTURE"
    src=Path(source);dst=Path(out)
    if src.is_symlink() or not src.is_dir() or dst.exists() or not dst.parent.is_dir():
        raise EvidenceCryptoRejected("encrypted_capture_input_or_output_invalid")
    try:
        m=json.loads((src/"manifest.json").read_text())
        sealed=(src/"capture.tar.gz.aesgcm").read_bytes()
    except (OSError,ValueError) as exc:
        raise EvidenceCryptoRejected("encrypted_capture_artifact_missing") from exc
    names=m.get("file_names")
    if (m.get("schema")!="kyoto_nov15_full_capture_aesgcm.v1" or
        m.get("repo")!=repo or m.get("run_id")!=str(run_id) or
        m.get("day")!="20261115" or m.get("encryption")!="AES-256-GCM" or
        m.get("originals_not_uploaded_plaintext") is not True or
        not isinstance(names,list) or len(names)>MAX_FILES or not names or
        any(type(n) is not str or not re.fullmatch(
            r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*",n) or
            ".." in n.split("/") for n in names) or
        "nov15_preflight_receipt.json" not in names or
        hashlib.sha256(sealed).hexdigest()!=m.get("ciphertext_sha256")):
        raise EvidenceCryptoRejected("capture_manifest_tampered")
    try:
        payload=AESGCM(key).decrypt(bytes.fromhex(m["nonce_hex"]),sealed,aad)
        with tarfile.open(fileobj=io.BytesIO(payload),mode="r:gz") as archive:
            members=archive.getmembers()
            if sorted(x.name for x in members)!=sorted(names):
                raise EvidenceCryptoRejected("capture_archive_inventory_mismatch")
            content={}
            for x in members:
                if not x.isfile() or x.size>MAX_FILE or x.name not in names:
                    raise EvidenceCryptoRejected("capture_unsafe_tar_member")
                content[x.name]=archive.extractfile(x).read()
    except (ValueError,tarfile.TarError,KeyError,InvalidTag) as exc:
        raise EvidenceCryptoRejected("capture_decryption_failed") from exc
    dst.mkdir()
    for name,raw in content.items():
        p=dst/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(raw)
    return {"files":sorted(content),"authenticated_encryption":True}

def main(argv=None):
    import argparse,os
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--destination",required=True)
    a=p.parse_args(argv)
    m=encrypt_capture_directory(a.source,a.destination,
        key_hex=os.environ.get("ARCHIVE_KEY",""),
        repo=os.environ["GITHUB_REPOSITORY"],run_id=os.environ["GITHUB_RUN_ID"])
    print("NOV15_FULL_CAPTURE_ENCRYPTED_FILES="+str(len(m["file_names"])))
    print("NOV15_FULL_CAPTURE_PLAINTEXT_ARTIFACT_UPLOAD=FALSE")
    return m

if __name__=="__main__":
    main()
