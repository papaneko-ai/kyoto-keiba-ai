"""Actual Kyoto Nov22 saved 12R JRA bracket market roster-aware replay.

Correctly treats non-eligible same-frame dashes as unpriced placeholders,
but ONLY with racecard original independently SHA/UTC matched to source.
"""
import hashlib,io,json,os,re,tarfile
from pathlib import Path
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_g06_roster_aware_bracket import parse_bracket_with_roster

DAY="20261122"
AAD_MARKET=b"kyoto-nov22-actual-odds-source-remainder-v1"
AAD_CARD=b"kyoto-nov22-observed-official-all12-source-only"
KEY_RE=re.compile(r"[a-fA-F0-9]{64}")
def decrypt(folder,name,digest,aad,key):
    root=Path(folder)
    cipher=(root/name).read_bytes()
    if hashlib.sha256(cipher).hexdigest()!=(root/digest).read_text().strip():
        raise ValueError("ARCHIVE_SHA_BAD")
    data=AESGCM(key).decrypt(cipher[:12],cipher[12:],aad)
    files={}
    with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as t:
        for m in t.getmembers():
            if not m.isfile() or ".." in m.name or "/" in m.name or m.name in files:
                raise ValueError("UNSAFE_ARCHIVE")
            files[m.name]=t.extractfile(m).read(1500001)
    return files

def decode(raw):
    try:return raw.decode("utf8")
    except UnicodeDecodeError:return raw.decode("cp932",errors="replace")

def independently_saved_frame_roster(raw):
    soup=BeautifulSoup(decode(raw),"html.parser")
    tables=[x for x in soup.select("table") if x.select_one("th.num")
            and x.select_one("th.waku") and x.select_one("th.horse")]
    if len(tables)!=1:raise ValueError("RACE_FRAME_TABLE_NOT_UNIQUE")
    rows=[]
    for tr in tables[0].select("tr"):
        n=tr.select_one("td.num")
        f=tr.select_one("td.waku")
        if n is None and f is None:continue
        if n is None or f is None:raise ValueError("INCOMPLETE_HORSE_FRAME_ROW")
        a=n.get_text(" ",strip=True)
        b=f.get_text(" ",strip=True)
        if not a.isascii() or not b.isascii() or not a.isdecimal() or not b.isdecimal():
            raise ValueError("INVALID_FRAME_DIGITS:num="+repr(a[:30])+" frame="+repr(b[:30]))
        rows.append((int(a),int(b)))
    if not 2<=len(rows)<=18 or [n for n,f in rows]!=list(range(1,len(rows)+1)):
        raise ValueError("ROSTER_NUMBER_SEQUENCE_UNVERIFIED")
    if any(not 1<=f<=8 for n,f in rows):raise ValueError("INVALID_FRAME_NUMBER")
    return rows

def main():
    keyhex=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not KEY_RE.fullmatch(keyhex):raise ValueError("KEY_MISSING")
    key=bytes.fromhex(keyhex)
    markets=decrypt("market_src","market_followup.tar.gz.aesgcm",
                    "encrypted_sha256.txt",AAD_MARKET,key)
    cards=decrypt("card_src","originals_all12.tar.gz.aesgcm",
                  "ciphertext_sha256.txt",AAD_CARD,key)
    receipt=json.loads(markets["source_receipt.json"])
    source=json.loads(cards["receipt.json"])
    if receipt["day"]!=DAY or source["day"]!=DAY:raise ValueError("WRONG_DAY")
    result={"schema":"kyoto_nov22_real_roster_aware_bracket_replay.v1",
            "day":DAY,"source_only":True,"pre_race_odds_approved":False,"races":{}}
    good=0
    for race in range(1,13):
        row={}
        rname=f"r{race:02d}_pc_official_racecard.html"
        card=cards.get(rname)
        cardrec=source["races"][str(race)].get("PC",{})
        if not card or hashlib.sha256(card).hexdigest()!=cardrec.get("sha256"):
            row["state"]="NO_SHA_VERIFIED_PC_RACECARD"
            result["races"][str(race)]=row
            continue
        try:
            roster=independently_saved_frame_roster(card)
            row["actual_roster_size"]=len(roster)
            for ch in ("pc","sp"):
                marketname=f"r{race:02d}_{ch}_bracket_quinella_original.html"
                if marketname not in markets:continue
                original=markets[marketname]
                info=receipt["races"][str(race)][ch.upper()]["market_items"]["bracket_quinella"]
                if hashlib.sha256(original).hexdigest()!=info.get("sha256"):
                    raise ValueError("MARKET_RECEIPT_SHA_MISMATCH")
                try:
                    p=parse_bracket_with_roster(original,tuple(roster))
                    row.update(state="ROSTER_AWARE_NUMERIC_BRACKET_VALIDATED",
                               channel=ch.upper(),original_sha256=info["sha256"],
                               captured_at_utc=info["captured_at_utc"],
                               pair_count=p["pair_count"],
                               dimension=p["matrix_dimension"],
                               historical_final_detected=p["historical_final_detected"])
                    good+=1
                except Exception as exc:
                    row.update(state="ROSTER_AWARE_BRACKET_REJECTED",
                               error_class=type(exc).__name__,reason=str(exc)[:100])
                break
            if not row.get("state"):row["state"]="BRACKET_ORIGINAL_MISSING"
        except Exception as exc:
            row.update(state="ROSTER_SOURCE_REJECTED",
                       error_class=type(exc).__name__,reason=str(exc)[:100])
        result["races"][str(race)]=row
    out=Path("roster_aware_result");out.mkdir()
    (out/"safe_replay.json").write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("REAL_JRA_BRACKET_NUMERIC_ROSTER_AWARE="+str(good)+"/12")
    print("PRE_RACE_AS_OF_UNVERIFIED")
    print("PER_RACE_REJECTED="+json.dumps({str(k):v.get("reason","")
            for k,v in result["races"].items() if v["state"]!="ROSTER_AWARE_NUMERIC_BRACKET_VALIDATED"},
            sort_keys=True))
if __name__=="__main__":main()
