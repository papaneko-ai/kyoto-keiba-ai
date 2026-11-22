"""Strict two-request official JRA Nov22 R1 source probe, source-only encrypted.

No guessed CNAME, no redirect, no actual bet/prediction, no repeated HTTP.
Separate from frozen Sunday collector and all eight production schedule slots.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import re
import shutil
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler

PC="https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605060120261122%2F03"
SP="https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605060120261122%2F90"
LIMIT=1_500_000

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError("any_redirect_rejected")

def main():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    target=Path("nov22_direct_probe")
    raw_dir=target/"temporary_raw"
    sealed=target/"sealed"
    if target.exists():
        raise RuntimeError("fresh_probe_workspace_required")
    raw_dir.mkdir(parents=True)
    sealed.mkdir()
    key_hex=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",key_hex):
        raise RuntimeError("archive_key_missing_zero_http")
    key=bytes.fromhex(key_hex)
    client=build_opener(NoRedirect())
    findings={"schema":"kyoto_nov22_independent_direct_original_probe.v1",
              "race_day":"20261122","race_number":1,"venue":"KYOTO",
              "source_only":True,"prediction_ready":False,
              "both_markets_verified":False,"results":{}}
    accepted={}
    for i,(name,url) in enumerate((("PC",PC),("SP",SP))):
        if i:time.sleep(2)
        start=datetime.now(timezone.utc).isoformat()
        result={"source_url":url,"http_started_at_utc":start,"http_started":True,
                "original_fetched":False,"both_markets_verified":False}
        try:
            with client.open(Request(url,headers={
                "Accept":"text/html","User-Agent":"KyotoRaceAI-Private-ReadOnly/0.1"},
                method="GET"),timeout=12) as response:
                payload=response.read(LIMIT+1)
                status=response.status
                got_url=response.geturl()
                mime=response.headers.get("Content-Type","")
            if (got_url!=url or status!=200 or "html" not in mime.lower()
                    or not 0<len(payload)<=LIMIT):
                raise ValueError("official_response_not_exact_valid_html")
            sha=hashlib.sha256(payload).hexdigest()
            try:visible=payload.decode("utf-8")
            except UnicodeDecodeError:visible=payload.decode("cp932",errors="replace")
            # Deliberately does not certify roster; these are source
            # identity clues only, and are saved as independent booleans.
            result.update(original_fetched=True,bytes=len(payload),sha256=sha,
                          captured_at_utc=datetime.now(timezone.utc).isoformat(),
                          visible_kyoto="京都" in visible,
                          visible_day=("2026年11月22日" in visible or
                                       "2026/11/22" in visible),
                          race_1_heading=bool(re.search(r"1\\s*(?:R|レース)",visible,re.I)),
                          state="SAVED_OFFICIAL_HTML_NOT_ROSTER_VERIFIED")
            (raw_dir/(name.lower()+"_official_r1.html")).write_bytes(payload)
            accepted[name]=payload
        except Exception as exc:
            result.update(state="HTTP_OR_SOURCE_REJECTED",
                          error_class=type(exc).__name__)
        findings["results"][name]=result
    (raw_dir/"source_receipt.json").write_text(
        json.dumps(findings,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode="w:gz") as tar:
        for file in sorted(raw_dir.iterdir()):
            data=file.read_bytes()
            entry=tarfile.TarInfo(file.name);entry.size=len(data);entry.mtime=0
            tar.addfile(entry,io.BytesIO(data))
    nonce=os.urandom(12)
    aad=b"kyoto-nov22-direct-official-r1-source-only"
    encrypted=nonce+AESGCM(key).encrypt(nonce,archive.getvalue(),aad)
    (sealed/"originals.tar.gz.aesgcm").write_bytes(encrypted)
    (sealed/"safe_source_receipt.json").write_text(
        json.dumps(findings,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    (sealed/"encrypted_bundle_sha256.txt").write_text(
        hashlib.sha256(encrypted).hexdigest()+"\n")
    decrypted=AESGCM(key).decrypt(encrypted[:12],encrypted[12:],aad)
    if decrypted!=archive.getvalue():
        raise RuntimeError("encrypted_payload_roundtrip_failed")
    shutil.rmtree(raw_dir)
    print("OFFICIAL_DIRECT_PROBE_SOURCE_ONLY="+
          json.dumps({n:{"state":x["state"],"sha256":x.get("sha256"),
                         "visible_kyoto":x.get("visible_kyoto"),
                         "visible_day":x.get("visible_day")}
                      for n,x in findings["results"].items()},sort_keys=True))
    print("OFFICIAL_SOURCE_AES_GCM_ROUNDTRIP_PASS")
    print("NO_PREDICTION_OR_WAGER")
if __name__=="__main__":main()
