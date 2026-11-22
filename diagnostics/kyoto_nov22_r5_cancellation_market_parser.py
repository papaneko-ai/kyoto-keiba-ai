"""Strict cancellation-aware Nov22 actual 5R JRA market parser.

Preserve cancellation as nonpriced, never insert invented odds. Historic/final
status stays distinct from authenticated as-of quotations.
"""
from __future__ import annotations
import hashlib,io,json,os,re,tarfile
from decimal import Decimal,InvalidOperation
from pathlib import Path
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
AAD=b"kyoto-nov22-actual-odds-source-remainder-v1"
SELECTOR={"quinella":"table.basic.narrow-xy.umaren",
          "bracket_quinella":"table.basic.narrow-xy.waku"}
def parse_cancel_aware(raw,market):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_500_000 or market not in SELECTOR:
        raise ValueError("UNSUPPORTED_RAW_OR_MARKET")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else ""
    if ("馬連オッズ" if market=="quinella" else "枠連オッズ") not in title:
        raise ValueError("MARKET_TITLE_NOT_PROVEN")
    tables=soup.select(SELECTOR[market])
    if not tables or (market=="quinella" and len(tables)!=11) or (market=="bracket_quinella" and len(tables)!=8):
        raise ValueError("SOURCE_DIMENSION_NOT_5R_PROVEN")
    priced=[];cancelled=[];nonprice=[];seen=set()
    for i,t in enumerate(tables,1):
        tokens=t.get_text(" ",strip=True).split()
        if not tokens or tokens[0]!=str(i):
            raise ValueError("ROW_IDENTITY_MISMATCH")
        vals=tokens[1:] if market=="quinella" else (tokens if len(tokens)%2==0 else tokens[1:])
        if len(vals)%2:raise ValueError("PAIR_TOKEN_MISALIGNMENT")
        for k in range(0,len(vals),2):
            try:j=int(vals[k])
            except ValueError as e:raise ValueError("NONNUMERIC_PAIR_INDEX") from e
            if j<=i if market=="quinella" else j<i:
                raise ValueError("PAIR_ORDER_INVALID")
            key=(i,j)
            if key in seen:raise ValueError("DUPLICATE_PAIR")
            seen.add(key)
            v=vals[k+1]
            if v=="取消":
                cancelled.append([i,j])
            elif v in ("-","--","---","発売なし","対象外"):
                nonprice.append([i,j])
            else:
                try:p=Decimal(v.replace(",",""))
                except InvalidOperation as e:raise ValueError("UNRECOGNIZED_MARKET_VALUE") from e
                if not p.is_finite() or p<1:raise ValueError("INVALID_PRICE")
                priced.append({"pair":[i,j],"odds":str(p)})
    if not cancelled:raise ValueError("NO_CANCELLATION_IN_5R")
    return {"source_sha256":hashlib.sha256(raw).hexdigest(),"market":market,
            "pricable_pairs":len(priced),"cancelled_pairs":len(cancelled),
            "nonpriced_pairs":len(nonprice),"priced":priced,"cancelled":cancelled,
            "nonpriced":nonprice,"historical_final_detected":"最終オッズ" in soup.get_text(" ",strip=True),
            "pre_race_odds_verified":False,"numerical_market_complete":False,
            "classification":"VALID_PRICES_SEPARATED_FROM_OFFICIALLY_CANCELLED_PAIRS"}
def main():
    root=Path("market")
    blob=(root/"market_followup.tar.gz.aesgcm").read_bytes()
    if hashlib.sha256(blob).hexdigest()!=(root/"encrypted_sha256.txt").read_text().strip():
        raise ValueError("ENCRYPTED_SOURCE_SHA_MISMATCH")
    key=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[A-Fa-f0-9]{64}",key):raise ValueError("KEY_REQUIRED")
    clear=AESGCM(bytes.fromhex(key)).decrypt(blob[:12],blob[12:],AAD)
    files={}
    with tarfile.open(fileobj=io.BytesIO(clear),mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or "/" in m.name or ".." in m.name:raise ValueError("UNSAFE_ARCHIVE")
            if m.name in ("r05_pc_quinella_original.html","r05_pc_bracket_quinella_original.html","source_receipt.json"):
                files[m.name]=tar.extractfile(m).read(1500001)
    receipt=json.loads(files["source_receipt.json"])
    if receipt.get("day")!="20261122":raise ValueError("WRONG_DAY")
    result={}
    for market in SELECTOR:
        raw=files["r05_pc_"+market+"_original.html"]
        source=receipt["races"]["5"]["PC"]["market_items"][market]
        if hashlib.sha256(raw).hexdigest()!=source.get("sha256"):
            raise ValueError("ORIGINAL_MARKET_PROVENANCE_NOT_VERIFIED")
        parsed=parse_cancel_aware(raw,market)
        result[market]={key:value for key,value in parsed.items() if key not in ("priced",)}
    target=Path("market5_cancellation_proof");target.mkdir()
    (target/"safe_market5_cancellation.json").write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("RACE5_OFFICIAL_CANCELLATION_CLASSIFIED="+json.dumps({
        k:{p:v[p] for p in ("pricable_pairs","cancelled_pairs","nonpriced_pairs")}
        for k,v in result.items()},sort_keys=True))
    print("RACE5_NO_SYNTHETIC_QUOTES;PRE_RACE_PROVEN_FALSE")
if __name__=="__main__":main()
