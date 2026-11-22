"""One-shot observed official JRA Kyoto ground page, source-only AES preserved."""
import hashlib,io,json,os,re,shutil,tarfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
URL="https://jra.jp/keiba/baba/index2.html"
LIMIT=1500000
AAD=b"kyoto-nov22-official-ground-source-only"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("REDIRECT_FORBIDDEN")
def main():
    key=os.getenv("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[a-fA-F0-9]{64}",key):raise ValueError("KEY_MISSING_BEFORE_HTTP")
    target=Path("nov22_track");raw=target/"raw";sealed=target/"sealed"
    if target.exists():raise ValueError("UNFRESH_OUTPUT")
    raw.mkdir(parents=True);sealed.mkdir()
    receipt={"schema":"kyoto_nov22_observed_official_ground.v1","day":"20261122",
             "requested_at_utc":datetime.now(timezone.utc).isoformat(),
             "source_url":URL,"source_only":True,"same_day_ground_verified":False,
             "state":"REQUEST_NOT_COMPLETED"}
    try:
        client=build_opener(NoRedirect())
        with client.open(Request(URL,headers={"Accept":"text/html",
               "User-Agent":"Mozilla/5.0"},method="GET"),timeout=12) as response:
            data=response.read(LIMIT+1)
            response_url=response.geturl()
            status=response.status
            content_type=response.headers.get("Content-Type","")
        if response_url!=URL or status!=200 or "html" not in content_type.lower() or not 0<len(data)<=LIMIT:
            raise ValueError("OFFICIAL_TRACK_RESPONSE_REJECTED")
        (raw/"official_kyoto_track.html").write_bytes(data)
        receipt.update(state="OFFICIAL_GROUND_HTML_SAVED_FIELDS_UNVERIFIED",
                       sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),
                       captured_at_utc=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        receipt.update(state="TRACK_HTTP_FAILED",error_class=type(exc).__name__)
    (raw/"source_receipt.json").write_text(json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w:gz") as t:
        for file in sorted(raw.iterdir()):
            data=file.read_bytes()
            m=tarfile.TarInfo(file.name);m.size=len(data);m.mtime=0
            t.addfile(m,io.BytesIO(data))
    nonce=os.urandom(12)
    cipher=nonce+AESGCM(bytes.fromhex(key)).encrypt(nonce,buf.getvalue(),AAD)
    if AESGCM(bytes.fromhex(key)).decrypt(nonce,cipher[12:],AAD)!=buf.getvalue():raise ValueError("TRACK_AES_VERIFY_FAILED")
    (sealed/"ground_original.tar.gz.aesgcm").write_bytes(cipher)
    (sealed/"source_sha256.txt").write_text(hashlib.sha256(cipher).hexdigest()+"\n")
    (sealed/"safe_track_receipt.json").write_text(json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    shutil.rmtree(raw)
    print("REAL_OFFICIAL_GROUND_SOURCE_STATE="+receipt["state"])
    print("JRA_TRACK_SHA_UTC_AES_PRESERVED")
if __name__=="__main__":main()
