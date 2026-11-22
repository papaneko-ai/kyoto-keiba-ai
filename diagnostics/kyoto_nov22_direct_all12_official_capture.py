"""Nov22 emergency official-source capture via URLs from actual saved JRA originals.

- Reuse the already downloaded original R1 PC and SP bytes (no re-fetch).
- For R2-R12, PC first; SP only when PC lacks an independently verified
  same-day Kyoto race heading. URLs are read ONLY from separately authenticated
  earlier GitHub original-link inventory; no token construction.
- Read-only, <=2 HTTP/sec? actual minimum is 2 seconds between requests.
- AES-256-GCM source archive; never publish plaintext or claim parsed markets.
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
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlsplit,parse_qs
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DAY="20261122"
DATE="2026年11月22日"
DATE_OTHER="2026/11/22"
AAD_ORIGINAL=b"kyoto-nov22-direct-official-r1-source-only"
AAD_BATCH=b"kyoto-nov22-observed-official-all12-source-only"
R1_SHA={
    "PC":"a6c4eb195f50d66c413c49ab00e9322439b7474b2e2aa1c857ca59ab1d8b9448",
    "SP":"e512f210c012f016d301455e2c717542bfd86fcd88171a0a70923b942b98dfaf"
}
LIMIT=1_500_000
TOKEN=re.compile(r"(pw|sw)01dde0108[0-9]{8}(0[1-9]|1[0-2])"+DAY+r"/[A-Za-z0-9]{2}",re.I)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError("any_redirect_rejected")

def _require_url(url,channel,race):
    from urllib.parse import urlsplit,parse_qs
    host="jra.jp" if channel=="PC" else "app.jra.jp"
    u=urlsplit(url)
    if u.scheme!="https" or u.hostname!=host or u.port is not None or u.username or u.password or u.fragment or u.path!="/JRADB/accessD.html":
        raise ValueError("non_official_race_url")
    q=parse_qs(u.query,strict_parsing=True)
    if set(q)!={"CNAME"} or len(q["CNAME"])!=1:raise ValueError("invalid_jra_query")
    m=TOKEN.fullmatch(q["CNAME"][0])
    if not m or m.group(1).lower()!=("pw" if channel=="PC" else "sw") or int(m.group(2))!=race:
        raise ValueError("day_venue_or_race_token_mismatch")
    return url

def _identity(raw,race):
    try:text=raw.decode("utf-8")
    except UnicodeDecodeError:text=raw.decode("cp932",errors="replace")
    soup=BeautifulSoup(text,"html.parser")
    # Prefer explicit title / top headings. Navigation links to other races
    # are not allowed to count as today's target race identity proof.
    fragments=[]
    if soup.title:fragments.append(soup.title.get_text(" ",strip=True))
    for tag in soup.select("h1,h2,h3"):
        fragments.append(tag.get_text(" ",strip=True))
        if len(fragments)>=12:break
    header=" ".join(fragments)
    identity=(("京都" in header or "京都" in text[:1200])
              and (DATE in header or DATE_OTHER in header or
                   DATE in text[:1200] or DATE_OTHER in text[:1200])
              and bool(re.search(rf"(?<![0-9])0?{race}\s*(?:R|レース)(?![0-9])",header,re.I)))
    return {"same_day_kyoto_race_heading":bool(identity),
            "has_horse_number_label":"馬番" in text,
            "has_horse_name_label":"馬名" in text}

def _old_r1(key):
    raw=(Path("nov22_saved_originals")/"originals.tar.gz.aesgcm").read_bytes()
    clear=AESGCM(key).decrypt(raw[:12],raw[12:],AAD_ORIGINAL)
    with tarfile.open(fileobj=io.BytesIO(clear),mode="r:gz") as tar:
        files={m.name:tar.extractfile(m).read(1_500_001)
               for m in tar.getmembers() if m.isfile()}
    for name in ["pc_official_r1.html","sp_official_r1.html","source_receipt.json"]:
        if name not in files:raise ValueError("saved_r1_missing")
    receipt=json.loads(files["source_receipt.json"])
    if receipt.get("race_day")!=DAY:raise ValueError("saved_r1_wrong_day")
    for ch in R1_SHA:
        if hashlib.sha256(files[ch.lower()+"_official_r1.html"]).hexdigest()!=R1_SHA[ch]:
            raise ValueError("saved_r1_sha_mismatch")
    return files,receipt

def main():
    key_hex=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",key_hex):raise ValueError("key_missing_before_http")
    key=bytes.fromhex(key_hex)
    inventory=json.loads((Path("nov22_saved_links")/"public_url_source_candidates.json").read_text())
    if inventory.get("day")!=DAY:raise ValueError("inventory_wrong_day")
    candidate={}
    for ch in ("PC","SP"):
        lane=inventory["lanes"][ch]
        if lane.get("verified_raw_sha256")!=R1_SHA[ch]:
            raise ValueError("independent_original_sha_not_bound")
        candidate[ch]={}
        for race in range(1,13):
            urls=lane["per_race_observed_exact_links"][str(race)]
            if len(urls)!=1:raise ValueError("missing_or_ambiguous_saved_official_anchor")
            candidate[ch][race]=_require_url(urls[0],ch,race)
    original,original_receipt=_old_r1(key)
    base=Path("nov22_all12_capture")
    source=base/"raw"
    sealed=base/"sealed"
    source.mkdir(parents=True,exist_ok=False)
    sealed.mkdir()
    report={"schema":"kyoto_nov22_observed_official_all12.v1",
            "day":DAY,"venue":"KYOTO","source_only":True,
            "all_twelve_rosters_parsed":False,"both_markets_verified":False,
            "prediction_ready":False,"races":{}}
    def save(race,ch,raw,when,url,*,reused=False):
        name=f"r{race:02d}_{ch.lower()}_official_racecard.html"
        (source/name).write_bytes(raw)
        return {"state":"REAL_OFFICIAL_ORIGINAL_SAVED_ROSTER_NOT_AUTHENTICATED",
                "channel":ch,"race":race,"observed_official_url":url,
                "captured_at_utc":when,"sha256":hashlib.sha256(raw).hexdigest(),
                "bytes":len(raw),"reused_existing_original":reused,
                "identity_hints":_identity(raw,race)}
    client=build_opener(NoRedirect())
    last=0.0
    deadline=time.monotonic()+470
    def fetch(url):
        nonlocal last
        if time.monotonic()>=deadline:raise TimeoutError("source_batch_budget_exhausted")
        delay=2.0-(time.monotonic()-last)
        if delay>0:time.sleep(delay)
        last=time.monotonic()
        with client.open(Request(url,headers={"Accept":"text/html",
                           "User-Agent":"KyotoRaceAI-Private-ReadOnly/0.1"},method="GET"),
                         timeout=12) as reply:
            data=reply.read(LIMIT+1)
            status=reply.status;final=reply.geturl()
            typ=reply.headers.get("Content-Type","")
        if status!=200 or final!=url or "html" not in typ.lower() or not 0<len(data)<=LIMIT:
            raise ValueError("official_response_not_exact_valid_html")
        return data,datetime.now(timezone.utc).isoformat()
    for race in range(1,13):
        entries={}
        for ch in ("PC","SP"):
            if race==1:
                raw=original[ch.lower()+"_official_r1.html"]
                prior=original_receipt["results"][ch]
                entries[ch]=save(race,ch,raw,prior["captured_at_utc"],
                                 candidate[ch][race],reused=True)
                continue
            if ch=="SP" and entries.get("PC",{}).get("identity_hints",{}).get("same_day_kyoto_race_heading"):
                entries[ch]={"state":"PC_OFFICIAL_SOURCE_PRESENT_SP_DUPLICATE_NOT_NEEDED"}
                continue
            try:
                raw,utc=fetch(candidate[ch][race])
                entries[ch]=save(race,ch,raw,utc,candidate[ch][race])
            except Exception as exc:
                entries[ch]={"state":"HTTP_OR_SOURCE_REJECTED","error_class":type(exc).__name__}
        report["races"][str(race)]=entries
    (source/"receipt.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode="w:gz") as tar:
        for file in sorted(source.iterdir()):
            data=file.read_bytes()
            entry=tarfile.TarInfo(file.name)
            entry.size=len(data);entry.mtime=0
            tar.addfile(entry,io.BytesIO(data))
    nonce=os.urandom(12)
    ciphertext=nonce+AESGCM(key).encrypt(nonce,archive.getvalue(),AAD_BATCH)
    (sealed/"originals_all12.tar.gz.aesgcm").write_bytes(ciphertext)
    if AESGCM(key).decrypt(nonce,ciphertext[12:],AAD_BATCH)!=archive.getvalue():
        raise RuntimeError("AES_GCM_BATCH_ROUNDTRIP_FAILED")
    (sealed/"source_receipts_summary.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    (sealed/"ciphertext_sha256.txt").write_text(hashlib.sha256(ciphertext).hexdigest()+"\n")
    shutil.rmtree(source)
    counted=sum(any(e.get("state")=="REAL_OFFICIAL_ORIGINAL_SAVED_ROSTER_NOT_AUTHENTICATED"
                    for e in v.values()) for v in report["races"].values())
    print(f"REAL_JRA_12R_ORIGINALS_SAVED={counted}/12")
    print("ENCRYPTED_SOURCE_AES_GCM_ROUNDTRIP_PASS")
    print("PREDICTION_READY_FALSE;PAIRED_MARKETS_NOT_YET_VERIFIED")
if __name__=="__main__":main()
