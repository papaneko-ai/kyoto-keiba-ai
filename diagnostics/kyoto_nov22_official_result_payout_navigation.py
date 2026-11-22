"""Inspect authenticated JRA Kyoto 12R stored cards for genuine result/payout anchors.

No invented CNAME; absence is reported. No HTTP.
"""
import hashlib,io,json,os,re,tarfile
from pathlib import Path
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
AAD=b"kyoto-nov22-observed-official-all12-source-only"
def main():
    b=Path("nov22_all12_source")
    encrypted=(b/"originals_all12.tar.gz.aesgcm").read_bytes()
    if hashlib.sha256(encrypted).hexdigest()!=(b/"ciphertext_sha256.txt").read_text().strip():
        raise ValueError("SOURCE_SHA_INVALID")
    key=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[a-f0-9A-F]{64}",key):raise ValueError("NO_AES_KEY")
    clear=AESGCM(bytes.fromhex(key)).decrypt(encrypted[:12],encrypted[12:],AAD)
    files={}
    with tarfile.open(fileobj=io.BytesIO(clear),mode="r:gz") as t:
        for m in t.getmembers():
            if not m.isfile() or "/" in m.name or ".." in m.name:
                raise ValueError("UNSAFE_TAR")
            files[m.name]=t.extractfile(m).read(1500001)
    rec=json.loads(files["receipt.json"])
    d={}
    for n in range(1,13):
        lane={}
        for ch in ("pc","sp"):
            name=f"r{n:02d}_{ch}_official_racecard.html"
            if name not in files:continue
            raw=files[name]
            prior=rec["races"][str(n)][ch.upper()]
            if hashlib.sha256(raw).hexdigest()!=prior["sha256"]:
                raise ValueError("RAW_SOURCE_SHA_DIFFERENCE")
            try:html=raw.decode("utf-8")
            except UnicodeError:html=raw.decode("cp932",errors="replace")
            soup=BeautifulSoup(html,"html.parser")
            results=[]
            for a in soup.select("a"):
                label=a.get_text(" ",strip=True)
                href=a.get("href","")
                onclick=a.get("onclick","")
                if not any(word in label for word in ("結果","払戻","成績","確定","馬連","枠連")):continue
                results.append({"label":label[:35],"href":href[:180],
                                "onclick":onclick[:260]})
            lane[ch]={"related_live_navigation":results[:30]}
        d[str(n)]=lane
    out=Path("postrace_anchor_audit");out.mkdir()
    report={"schema":"kyoto_nov22_observed_result_payout_sources.v1",
            "day":"20261122","network_requests":0,
            "source_only":True,"result_data_confirmed":False,"race_navigation":d}
    (out/"official_observed_result_actions.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("OBSERVED_RESULT_ACTIONS="+json.dumps({
        race:{ch:[x for x in row["related_live_navigation"] if any(k in x["label"]
            for k in ("結果","払戻","成績","確定"))]
            for ch,row in lanes.items()} for race,lanes in d.items()},ensure_ascii=False)[:8500])
    print("NO_HTTP_NO_INFERRED_RESULTS")
if __name__=="__main__":main()
