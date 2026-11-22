"""Independent Nov22 real-original forensic intake; zero JRA HTTP.

Inspect actual 5R price placeholders, official profile body and track heading;
reopen AES-GCM with source SHA and public safe diagnostics only.
"""
from __future__ import annotations
import hashlib,io,json,os,re,tarfile
from pathlib import Path
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DATA={
 "market":("market_followup.tar.gz.aesgcm","encrypted_sha256.txt",b"kyoto-nov22-actual-odds-source-remainder-v1"),
 "profiles":("horse_profiles.tar.gz.aesgcm","ciphertext_sha256.txt",b"kyoto-nov22-observed-profile-history-originals-v1"),
 "track":("ground_original.tar.gz.aesgcm","source_sha256.txt",b"kyoto-nov22-official-ground-source-only")}
def unpack(key,area):
    name,digest,aad=DATA[area]
    base=Path("nov22_input")/area
    blob=(base/name).read_bytes()
    if hashlib.sha256(blob).hexdigest()!=(base/digest).read_text().strip():raise ValueError("SOURCE_CIPHERTEXT_SHA_REJECT")
    plain=AESGCM(key).decrypt(blob[:12],blob[12:],aad)
    items={}
    with tarfile.open(fileobj=io.BytesIO(plain),mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile() or "/" in m.name or ".." in m.name or m.name in items:
                raise ValueError("UNSAFE_TAR_MEMBER")
            items[m.name]=tf.extractfile(m).read(1_500_001)
    return items
def txt(raw):
    try:return raw.decode("utf8")
    except UnicodeError:return raw.decode("cp932",errors="replace")
def market5(files):
    result={}
    for market in ("quinella","bracket_quinella"):
        name="r05_pc_"+market+"_original.html"
        soup=BeautifulSoup(txt(files[name]),"html.parser")
        selector="table.basic.narrow-xy.umaren" if market=="quinella" else "table.basic.narrow-xy.waku"
        rows=[]
        for idx,table in enumerate(soup.select(selector),1):
            values=table.get_text(" ",strip=True).split()
            bad=[v for v in values if not (re.fullmatch(r"[0-9,]+(?:\.[0-9]+)?",v) or v.isdecimal())]
            rows.append({"table_number":idx,"token_count":len(values),
                         "non_numeric_tokens":sorted(set(bad))[:15],
                         "first_numeric_tokens":values[:5]})
        result[market]={"table_count":len(rows),"rows":rows,
                        "visible_non_sales_markers":[v for v in
                           ("発売なし","対象外","取消","除外","中止","--","---","-","最終オッズ","未発売")
                           if v in soup.get_text(" ",strip=True)]}
    return result
def profile(files):
    receipt=json.loads(files["profile_receipt.json"])
    names=sorted(x for x in files if x.startswith("profile_") and x.endswith(".html"))
    examples=[]
    for name in names[:4]:
        raw=files[name]
        soup=BeautifulSoup(txt(raw),"html.parser")
        examples.append({"title":(soup.title.get_text(" ",strip=True) if soup.title else "")[:90],
                         "table_count":len(soup.select("table")),
                         "history_header_detected":any(k in soup.get_text(" ",strip=True)
                             for k in ("競走成績","戦績","過去成績")),
                         "dt_labels":[x.get_text(" ",strip=True)[:30] for x in soup.select("dt")[:14]]})
    return {"source_count":len(names),"receipt_count":len(receipt.get("items",[])),
            "success_count":sum(x.get("state")=="OFFICIAL_PROFILE_ORIGINAL_SAVED_HISTORY_NOT_PARSED" for x in receipt.get("items",[])),
            "sample_layout":examples}
def track(files):
    receipt=json.loads(files["source_receipt.json"])
    raw=files.get("official_kyoto_track.html",b"")
    soup=BeautifulSoup(txt(raw),"html.parser")
    s=soup.get_text(" ",strip=True)
    return {"source_state":receipt.get("state"),
            "title":(soup.title.get_text(" ",strip=True) if soup.title else "")[:120],
            "headings":[x.get_text(" ",strip=True)[:120] for x in soup.select("h1,h2,h3")[:16]],
            "kyoto_markers":s.count("京都"),"date_markers":s.count("2026年11月22日"),
            "going_keywords":[k for k in ("良","稍重","不良","芝","ダート","含水率","クッション値")
                              if k in s],"raw_sha256":hashlib.sha256(raw).hexdigest() if raw else None}
def main():
    key=os.getenv("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[A-Fa-f0-9]{64}",key):raise ValueError("KEY_MISSING")
    bundles={name:unpack(bytes.fromhex(key),name) for name in DATA}
    report={"schema":"kyoto_nov22_source_forensic_triage.v1","day":"20261122",
            "market5":market5(bundles["market"]),
            "profiles":profile(bundles["profiles"]),
            "track":track(bundles["track"]),
            "all_originals_cryptographically_checked":True,
            "prediction_ready":False,"market_prerace_certified":False,
            "network_requests":0}
    root=Path("nov22_forensic");root.mkdir()
    (root/"source_layout_evidence.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("NOV22_R5_MARKET_TOKENS="+json.dumps(report["market5"],ensure_ascii=False)[:6500])
    print("NOV22_PROFILE_LAYOUT="+json.dumps(report["profiles"],ensure_ascii=False)[:2000])
    print("NOV22_TRACK_LAYOUT="+json.dumps(report["track"],ensure_ascii=False)[:2000])
    print("JRA_HTTP_ZERO=TRUE;SOURCE_SHA_AES_CHECKED")
if __name__=="__main__":main()
