"""AES-GCM encrypted JRA originals, safe for public GitHub Actions artifacts.

Secret is provided only at runtime. Neither key nor plaintext gets committed.
This is not source authenticity; original claims remain separately audited.
"""
from __future__ import annotations
import hashlib,io,json,re,secrets,tarfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FILES={"official_selection.html","official_meeting.html","official_racecard.html","official_odds_menu.html","official_odds_navigation_1.html","official_odds_navigation_2.html","official_quinella_odds.html","official_bracket_quinella_odds.html","observed_race_links.json","receipt.json"}
class EvidenceCryptoRejected(ValueError):pass

def _key(s):
    if type(s) is not str or not re.fullmatch(r"[0-9a-fA-F]{64}",s):
        raise EvidenceCryptoRejected("AES256_SECRET_REQUIRED")
    return bytes.fromhex(s)

def _aad(repo,run_id):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo) or not str(run_id).isdigit():
        raise EvidenceCryptoRejected("repo_or_run_invalid")
    return (repo+"|"+str(run_id)+"|20261115").encode("ascii")

def encrypt_evidence(source,out,*,key_hex,repo,run_id):
    key=_key(key_hex);aad=_aad(repo,run_id)
    src=Path(source);out=Path(out)
    if not src.is_dir() or src.is_symlink() or out.exists() or not out.parent.is_dir():
        raise EvidenceCryptoRejected("unsafe_source_or_destination")
    files=list(src.iterdir())
    if (not files or "receipt.json" not in {p.name for p in files}
        or any(p.is_symlink() or not p.is_file() or p.name not in FILES
               or p.stat().st_size>1_500_000 for p in files)):
        raise EvidenceCryptoRejected("unexpected_original_file")
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode="w:gz") as archive:
        for p in sorted(files):
            data=p.read_bytes()
            item=tarfile.TarInfo(p.name)
            item.size=len(data)
            archive.addfile(item,io.BytesIO(data))
    nonce=secrets.token_bytes(12)
    sealed=AESGCM(key).encrypt(nonce,payload.getvalue(),aad)
    out.mkdir()
    (out/"originals.tar.gz.aesgcm").write_bytes(sealed)
    manifest={"schema":"kyoto_nov15_encrypted_artifact.v1",
              "repo":repo,"run_id":str(run_id),"day":"20261115",
              "nonce_hex":nonce.hex(),"ciphertext_sha256":hashlib.sha256(sealed).hexdigest(),
              "file_names":sorted(p.name for p in files),
              "encryption":"AES-256-GCM","plaintext_uploaded":False}
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    return {"manifest":manifest,"encrypted_only":True}

def decrypt_evidence(source,out,*,key_hex,repo,run_id):
    key=_key(key_hex);aad=_aad(repo,run_id)
    src=Path(source);out=Path(out)
    if not src.is_dir() or src.is_symlink() or out.exists() or not out.parent.is_dir():
        raise EvidenceCryptoRejected("unsafe_encrypted_source_or_destination")
    try:
        m=json.loads((src/"manifest.json").read_text(encoding="utf8"))
        sealed=(src/"originals.tar.gz.aesgcm").read_bytes()
    except (OSError,ValueError,UnicodeError) as exc:
        raise EvidenceCryptoRejected("encrypted_artifact_missing") from exc
    if (m.get("schema")!="kyoto_nov15_encrypted_artifact.v1"
        or m.get("repo")!=repo or m.get("run_id")!=str(run_id)
        or m.get("day")!="20261115" or m.get("encryption")!="AES-256-GCM"
        or m.get("plaintext_uploaded") is not False
        or not isinstance(m.get("file_names"),list)
        or not set(m["file_names"])<=FILES
        or "receipt.json" not in m["file_names"]
        or not re.fullmatch(r"[0-9a-f]{24}",str(m.get("nonce_hex")))
        or hashlib.sha256(sealed).hexdigest()!=m.get("ciphertext_sha256")):
        raise EvidenceCryptoRejected("manifest_inconsistent_or_tampered")
    try: plaintext=AESGCM(key).decrypt(bytes.fromhex(m["nonce_hex"]),sealed,aad)
    except Exception as exc: raise EvidenceCryptoRejected("authentication_tag_failed") from exc
    contents={}
    try:
        with tarfile.open(fileobj=io.BytesIO(plaintext),mode="r:gz") as archive:
            members=archive.getmembers()
            if (len(members)!=len(m["file_names"]) or
                sorted(x.name for x in members)!=sorted(m["file_names"])):
                raise EvidenceCryptoRejected("archive_member_mismatch")
            for x in members:
                if not x.isfile() or x.name not in FILES or x.size>1_500_000:
                    raise EvidenceCryptoRejected("unsafe_archive_member")
                contents[x.name]=archive.extractfile(x).read()
    except (tarfile.TarError,OSError) as exc:
        raise EvidenceCryptoRejected("archive_invalid") from exc
    out.mkdir()
    for name,data in contents.items():
        (out/name).write_bytes(data)
    return {"files":sorted(contents),"source_run_id":str(run_id),
            "authentication_tag_verified":True,"independent_JRA_provenance_verified":False}

def main(argv=None):
    import argparse,os
    p=argparse.ArgumentParser()
    p.add_argument("--decrypt",action="store_true",required=True)
    p.add_argument("--source",required=True)
    p.add_argument("--destination",required=True)
    p.add_argument("--source-run-id",required=True)
    args=p.parse_args(argv)
    report=decrypt_evidence(
        args.source,args.destination,
        key_hex=os.environ.get("ARCHIVE_KEY",""),
        repo=os.environ.get("GITHUB_REPOSITORY",""),
        run_id=args.source_run_id)
    # Never print source bytes, secret or URL query.
    print("NOV15_OBSERVED_ORIGINALS_AUTHENTICATED_ENCRYPTION=TRUE")
    print("NOV15_OFFICIAL_PROVENANCE_STILL_UNVERIFIED=TRUE")
    return report

if __name__=="__main__":
    main()
