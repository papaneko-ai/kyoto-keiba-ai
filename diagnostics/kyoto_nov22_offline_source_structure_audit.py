"""Independent offline scan of archived actual Nov22 JRA 1-12R HTML originals.

No HTTP and no decryption key disclosure. Separates raw source capture from
structured roster certification and observed odds navigation.
"""
from __future__ import annotations
import hashlib,io,json,os,re,tarfile
from pathlib import Path
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD=b"kyoto-nov22-observed-official-all12-source-only"

def scan(raw):
    try:txt=raw.decode("utf8")
    except UnicodeError:txt=raw.decode("cp932",errors="replace")
    soup=BeautifulSoup(txt,"html.parser")
    anchors=soup.select("a")
    odds=[a for a in anchors if "オッズ" in a.get_text(" ",strip=True)]
    tables=soup.select("table")
    # Candidate counts only; not formal roster authentication.
    candidates=[]
    for table in tables:
        header=" ".join(t.get_text(" ",strip=True) for t in table.select("th"))
        if "馬番" in header and "馬名" in header:
            candidates.append({
                "header_present":True,
                "row_count":max(0,len(table.select("tr"))-1),
                "named_horse_links":sum(
                    bool(re.search(r"馬",a.get_text(" ",strip=True)))
                    for a in table.select("a"))
            })
    forms=[f for f in soup.select("form")
           if "accessO.html" in (f.get("action") or "")]
    return {
        "horse_table_candidate_count":len(candidates),
        "horse_table_row_counts":[x["row_count"] for x in candidates],
        "horse_link_counts":[x["named_horse_links"] for x in candidates],
        "visible_odds_anchor_count":len(odds),
        "odds_anchor_onclick_count":sum(bool(a.get("onclick")) for a in odds),
        "odds_anchor_href_count":sum(bool(a.get("href")) for a in odds),
        "observed_odds_forms_count":len(forms),
        "visible_quinella_text":"馬連" in txt,
        "visible_bracket_quinella_text":"枠連" in txt,
        "contains_race_start_label":"発走" in txt,
        "contains_bodyweight_label":"馬体重" in txt,
    }

def main():
    folder=Path("nov22_all12_source")
    blob=(folder/"originals_all12.tar.gz.aesgcm").read_bytes()
    key_hex=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",key_hex):
        raise RuntimeError("source_decryption_key_missing")
    expected_sha=(folder/"ciphertext_sha256.txt").read_text().strip()
    if hashlib.sha256(blob).hexdigest()!=expected_sha:
        raise RuntimeError("ciphertext_digest_mismatch")
    raw=AESGCM(bytes.fromhex(key_hex)).decrypt(blob[:12],blob[12:],AAD)
    files={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not (re.fullmatch(
                    r"r(0[1-9]|1[0-2])_(pc|sp)_official_racecard.html",member.name)
                    or member.name=="receipt.json"):
                raise RuntimeError("unknown_source_archive_member")
            if member.name in files:raise RuntimeError("duplicate_archive_member")
            files[member.name]=tar.extractfile(member).read(1_500_001)
    manifest=json.loads(files["receipt.json"])
    if manifest.get("day")!="20261122":raise RuntimeError("wrong_source_day")
    report={"schema":"kyoto_nov22_real_all12_source_offline_inventory.v1",
            "day":"20261122","source_only":True,"prediction_ready":False,
            "rosters_formally_verified":False,"paired_market_prices_verified":False,
            "races":{}}
    for n in range(1,13):
        row={}
        for ch in ("PC","SP"):
            m=manifest["races"][str(n)].get(ch,{})
            name=f"r{n:02d}_{ch.lower()}_official_racecard.html"
            if name not in files:
                row[ch]={"state":m.get("state","NOT_CAPTURED")}
                continue
            original=files[name]
            if hashlib.sha256(original).hexdigest()!=m.get("sha256"):
                raise RuntimeError("source_receipt_sha_disagrees")
            row[ch]={"state":"REAL_ORIGINAL_SHA_AUTHENTICATED",
                     "source_sha256":m["sha256"],
                     "captured_at_utc":m["captured_at_utc"],
                     "source_header_identity_hint":m["identity_hints"],
                     "html_structure":scan(original)}
        report["races"][str(n)]=row
    saved=sum(any(v.get("state")=="REAL_ORIGINAL_SHA_AUTHENTICATED"
                  for v in x.values()) for x in report["races"].values())
    table=sum(any(v.get("html_structure",{}).get("horse_table_candidate_count",0)
                  for v in x.values()) for x in report["races"].values())
    odds=sum(any(v.get("html_structure",{}).get("visible_odds_anchor_count",0)
                  or v.get("html_structure",{}).get("observed_odds_forms_count",0)
                  for v in x.values()) for x in report["races"].values())
    out=Path("nov22_all12_analysis")
    out.mkdir()
    (out/"safe_structured_source_inventory.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("ACTUAL_JRA_RACE_ORIGINALS_SHA_VERIFIED="+str(saved)+"/12")
    print("RACES_WITH_CANDIDATE_ROSTER_TABLE="+str(table)+"/12")
    print("RACES_WITH_OBSERVED_ODDS_NAVIGATION="+str(odds)+"/12")
    print("ONLY_SOURCE_STRUCTURE;MARKET_PRICES_NOT_CERTIFIED;NO_JRA_HTTP")
if __name__=="__main__":main()
