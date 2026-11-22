"""Independent SHA/UTC verification of real Nov22 JRA odds-menu and paired originals.

Uses encrypted source, never raw HTML from user / a guessed market URL.
This certifies saved byte receipts only, NOT numeric prices or pre-start status.
"""
from __future__ import annotations
import hashlib,io,json,os,re,tarfile
from datetime import datetime,timezone
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD=b"kyoto-nov22-actual-odds-source-remainder-v1"
NAMED=re.compile(r"r(0[1-9]|1[0-2])_(pc|sp)_(odds_menu|quinella_original|bracket_quinella_original)\.html")
REQUIRED=("quinella","bracket_quinella")

def check():
    base=Path("nov22_market_source")
    cipher=(base/"market_followup.tar.gz.aesgcm").read_bytes()
    digest=(base/"encrypted_sha256.txt").read_text().strip()
    if hashlib.sha256(cipher).hexdigest()!=digest:raise ValueError("MARKET_CIPHER_SHA_INVALID")
    key=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[a-fA-F0-9]{64}",key):raise ValueError("AES_KEY_INVALID")
    clear=AESGCM(bytes.fromhex(key)).decrypt(cipher[:12],cipher[12:],AAD)
    originals={}
    with tarfile.open(fileobj=io.BytesIO(clear),mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or not (NAMED.fullmatch(m.name) or m.name=="source_receipt.json") or m.name in originals:
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
            originals[m.name]=tar.extractfile(m).read(1_500_001)
    report=json.loads(originals["source_receipt.json"])
    if report.get("day")!="20261122" or set(report.get("races",{}))!={str(x) for x in range(1,13)}:
        raise ValueError("WRONG_DAY_OR_RACE_COVERAGE")
    counts={"menu_originals":0,"paired_market_originals":0,
            "separate_market_originals":0,"unverified_before_start":12}
    evidences={}
    for n in range(1,13):
        row=report["races"][str(n)]
        observed={}
        for ch in ("PC","SP"):
            item=row.get(ch,{})
            menu=item.get("odds_menu_receipt")
            if isinstance(menu,dict):
                fname=f"r{n:02d}_{ch.lower()}_odds_menu.html"
                raw=originals[fname]
                if hashlib.sha256(raw).hexdigest()!=menu.get("sha256") or len(raw)!=menu.get("bytes"):
                    raise ValueError("MENU_ORIGINAL_SHA_OR_LENGTH_MISMATCH")
                counts["menu_originals"]+=1
            ok={}
            for market in REQUIRED:
                info=item.get("market_items",{}).get(market,{})
                if info.get("state")!="RAW_ORIGINAL_SAVED_NUMERICAL_PARSER_NOT_YET_VERIFIED":
                    continue
                fname=f"r{n:02d}_{ch.lower()}_{market}_original.html"
                raw=originals[fname]
                if hashlib.sha256(raw).hexdigest()!=info.get("sha256") or len(raw)!=info.get("bytes"):
                    raise ValueError("MARKET_ORIGINAL_SHA_OR_LENGTH_MISMATCH")
                stamp=datetime.fromisoformat(info["captured_at_utc"].replace("Z","+00:00"))
                if stamp.utcoffset()!=timezone.utc.utcoffset(None):raise ValueError("MARKET_CAPTURE_TIME_NOT_UTC")
                ok[market]={"original_sha256":info["sha256"],"utc":info["captured_at_utc"],
                            "size":info["bytes"],"numeric_prices_authenticated":False}
                counts["separate_market_originals"]+=1
            if ok:observed[ch]=ok
        if any(set(x)==set(REQUIRED) for x in observed.values()):
            counts["paired_market_originals"]+=1
        evidences[str(n)]={"market_originals":observed,
                           "pre_race_phase_proven":False,
                           "numeric_matrix_certified":False}
    result={"schema":"kyoto_nov22_real_market_original_independent_verification.v1",
            "day":"20261122","source_run":44983969532,
            "counts":counts,"races":evidences,
            "pre_race_odds_certified":False,"numeric_market_prices_verified":False,
            "source_ciphertext_sha256":digest}
    out=Path("nov22_market_recheck");out.mkdir()
    (out/"market_original_independent_receipt.json").write_text(json.dumps(
        result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("INDEPENDENT_ACTUAL_MARKET_SOURCE_PAIRS="+str(counts["paired_market_originals"])+"/12")
    print("INDEPENDENT_SHA_CHECKED_MARKET_ORIGINALS="+str(counts["separate_market_originals"]))
    print("PRE_RACE_AND_PRICE_MATRIX_NOT_YET_PROVEN")
if __name__=="__main__":check()
