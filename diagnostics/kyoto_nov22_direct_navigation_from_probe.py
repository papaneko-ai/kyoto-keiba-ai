"""Offline inventory of exact JRA 1-12R links in independently captured Nov22 originals.

Must decrypt already authenticated AES-GCM original from one known prior Actions
artifact. NO JRA HTTP, NO guessed URL suffix, NO roster/market certification.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import re
import tarfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qs
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DAY="20261122"
AAD=b"kyoto-nov22-direct-official-r1-source-only"
TOKEN=re.compile(r"(pw|sw)01dde01(?P<venue>08)(?P<meeting>[0-9]{8})(?P<race>0[1-9]|1[0-2])"+DAY+r"/[A-Za-z0-9]{2}",re.I)
URLS={
 "PC":"https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605060120261122%2F03",
 "SP":"https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605060120261122%2F90"
}

def inventory(raw:bytes, base:str, *, channel:str)->dict:
    if not 0<len(raw)<=1_500_000:
        raise ValueError("raw_html_missing_or_excessive")
    try: decoded=raw.decode("utf8")
    except UnicodeDecodeError: decoded=raw.decode("cp932",errors="replace")
    soup=BeautifulSoup(decoded,"html.parser")
    found={str(n):set() for n in range(1,13)}
    for a in soup.select("a[href]"):
        href=a.get("href","").strip()
        if not href or href.startswith(("javascript:","#")):continue
        url=urljoin(base,href)
        u=urlsplit(url)
        host="jra.jp" if channel=="PC" else "app.jra.jp"
        if u.scheme!="https" or u.hostname!=host or u.port is not None or u.fragment or u.path!="/JRADB/accessD.html":
            continue
        try:q=parse_qs(u.query,strict_parsing=True)
        except ValueError:continue
        if set(q)!={"CNAME"} or len(q["CNAME"])!=1:continue
        m=TOKEN.fullmatch(q["CNAME"][0])
        if not m or (m.group(1)!="pw" if channel=="PC" else m.group(1)!="sw"):
            continue
        # Do not extrapolate any URL from a neighboring race.
        found[str(int(m.group("race")))].add(url)
    return {k:sorted(v) for k,v in found.items()}

def main():
    folder=Path("nov22_saved_originals")
    data=(folder/"originals.tar.gz.aesgcm").read_bytes()
    key_hex=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",key_hex):raise ValueError("key_missing")
    original=AESGCM(bytes.fromhex(key_hex)).decrypt(data[:12],data[12:],AAD)
    with tarfile.open(fileobj=io.BytesIO(original),mode="r:gz") as tar:
        files={}
        for m in tar.getmembers():
            if not m.isfile() or m.name not in ("pc_official_r1.html","sp_official_r1.html","source_receipt.json") or m.name in files:
                raise ValueError("unknown_or_duplicate_encrypted_original")
            files[m.name]=tar.extractfile(m).read(1_500_001)
    receipt=json.loads(files["source_receipt.json"])
    if receipt.get("race_day")!=DAY:raise ValueError("wrong_day")
    report={"schema":"kyoto_nov22_official_saved_anchor_inventory.v1","day":DAY,
            "source_only":True,"both_markets_verified":False,"prediction_ready":False,
            "lanes":{}}
    for ch in ("PC","SP"):
        name=ch.lower()+"_official_r1.html"
        if name not in files:
            report["lanes"][ch]={"state":"SOURCE_NOT_PRESENT","candidate_count":0}
            continue
        observed=receipt["results"][ch]
        raw=files[name]
        if hashlib.sha256(raw).hexdigest()!=observed["sha256"]:
            raise ValueError("raw_sha_mismatch")
        choices=inventory(raw,URLS[ch],channel=ch)
        report["lanes"][ch]={
            "state":"SAVED_REAL_SOURCE_NAVIGATION_AUDITED",
            "verified_raw_sha256":observed["sha256"],
            "per_race_observed_anchor_counts":{k:len(v) for k,v in choices.items()},
            "per_race_observed_exact_links":choices,
            "distinct_races_with_exact_anchor":sum(bool(x) for x in choices.values())
        }
    target=Path("nov22_navigation_inventory")
    target.mkdir()
    (target/"public_url_source_candidates.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("OFFICIAL_SAVED_NAVIGATION_COUNTS="+json.dumps({
        ch:v["per_race_observed_anchor_counts"] for ch,v in report["lanes"].items()
        if "per_race_observed_anchor_counts" in v},sort_keys=True))
    print("ZERO_JRA_HTTP;NO_URL_SYNTHESIS;SOURCE_ONLY")
if __name__=="__main__":main()
