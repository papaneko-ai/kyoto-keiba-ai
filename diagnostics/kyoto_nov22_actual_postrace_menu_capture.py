"""Follow exact official JRA result and refund MENU actions seen in saved R1.

One POST per observed menu; preserve original AES, SHA, UTC and safe navigation.
Never guess result race URLs or treat menu as final payout proof.
"""
import hashlib,io,json,os,re,shutil,tarfile,time
from datetime import datetime,timezone
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.request import Request,build_opener,HTTPCookieProcessor,HTTPRedirectHandler
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
def source_cards(key):
    root=Path("nov22_all12_source")
    cipher=(root/"originals_all12.tar.gz.aesgcm").read_bytes()
    if hashlib.sha256(cipher).hexdigest()!=(root/"ciphertext_sha256.txt").read_text().strip():
        raise ValueError("SOURCE_CIPHER_SHA_MISMATCH")
    plain=AESGCM(key).decrypt(cipher[:12],cipher[12:],b"kyoto-nov22-observed-official-all12-source-only")
    files={}
    with tarfile.open(fileobj=io.BytesIO(plain),mode="r:gz") as t:
        for m in t.getmembers():
            if not m.isfile() or "/" in m.name or ".." in m.name:raise ValueError("INVALID_SOURCE_ARCHIVE")
            files[m.name]=t.extractfile(m).read(1500001)
    receipt=json.loads(files["receipt.json"])
    original=files["r01_pc_official_racecard.html"]
    if receipt.get("day")!="20261122" or hashlib.sha256(original).hexdigest()!=receipt["races"]["1"]["PC"]["sha256"]:
        raise ValueError("R1_ORIGINAL_SHA_RACE_MISMATCH")
    return files,receipt
MENU={"results":("/JRADB/accessS.html","レース結果"),
      "payout":("/JRADB/accessH.html","払戻金")}
ACT=re.compile(r"doAction\s*\(\s*['\"](/JRADB/access[SH]\.html)['\"]\s*,\s*['\"]([^'\"]+)['\"]",re.I)
NAV=re.compile(r"doAction\s*\(\s*['\"](/JRADB/access[A-Za-z]+\.html)['\"]\s*,\s*['\"]([^'\"]+)['\"]")
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("REDIRECT_BLOCKED")
def now():return datetime.now(timezone.utc).isoformat()
def decode(raw):
    try:return raw.decode("utf8")
    except UnicodeDecodeError:return raw.decode("cp932",errors="replace")
def main():
    key=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9A-Fa-f]{64}",key):raise ValueError("NO_AES_KEY")
    files,receipt=source_cards(bytes.fromhex(key))
    raw=files["r01_pc_official_racecard.html"]
    soup=BeautifulSoup(decode(raw),"html.parser")
    rawdir=Path("result_menus/raw");rawdir.mkdir(parents=True)
    sealed=Path("result_menus/sealed");sealed.mkdir()
    report={"schema":"kyoto_nov22_observed_jra_postrace_menus.v1","race_day":"20261122",
            "source_only":True,"actual_results_verified":False,
            "actual_payouts_verified":False,"menus":{}}
    client=build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
    for idx,(keyname,(path,label)) in enumerate(MENU.items()):
        candidates=set()
        for a in soup.select("a[onclick]"):
            if a.get_text(" ",strip=True)!=label:continue
            m=ACT.search(a.get("onclick",""))
            if m and m.group(1)==path and re.fullmatch(r"pw[0-9A-Za-z]+/[0-9A-Za-z]+",m.group(2)):
                candidates.add(m.group(2))
        row={"observed_action_count":len(candidates),"state":"MENU_NOT_ATTEMPTED"}
        if len(candidates)==1:
            token=next(iter(candidates))
            path_url="https://jra.jp"+path
            time.sleep(2*int(idx>0))
            row["request_started_at_utc"]=now()
            try:
                with client.open(Request(path_url,
                    data=urlencode({"cname":token}).encode("ascii"),
                    headers={"Accept":"text/html",
                             "Content-Type":"application/x-www-form-urlencoded",
                             "Referer":receipt["races"]["1"]["PC"]["observed_official_url"],
                             "User-Agent":"Mozilla/5.0"},method="POST"),timeout=12) as resp:
                    data=resp.read(1_500_001)
                    exact=resp.geturl()
                    code=resp.status
                    mime=resp.headers.get("Content-Type","")
                if code!=200 or exact!=path_url or "html" not in mime.lower() or not 0<len(data)<=1_500_000:
                    raise ValueError("INVALID_OFFICIAL_MENU_RESPONSE")
                sha=hashlib.sha256(data).hexdigest()
                (rawdir/(keyname+"_official_menu.html")).write_bytes(data)
                doc=BeautifulSoup(decode(data),"html.parser")
                anchors=[]
                for a in doc.select("a"):
                    title=a.get_text(" ",strip=True)
                    m=NAV.search(a.get("onclick",""))
                    if m:
                        anchors.append({"label":title[:50],"action":m.group(1),
                                        "token":m.group(2)})
                row.update(state="OFFICIAL_MENU_RAW_SAVED_RESULT_NOT_PARSED",
                           sha256=sha,bytes=len(data),
                           captured_at_utc=now(),navigation=anchors[:120],
                           page_title=doc.title.get_text(" ",strip=True) if doc.title else "")
            except Exception as exc:
                row.update(state="MENU_SOURCE_FAILED",error_class=type(exc).__name__)
        report["menus"][keyname]=row
    (rawdir/"source_receipt.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    pack=io.BytesIO()
    with tarfile.open(fileobj=pack,mode="w:gz") as t:
        for f in sorted(rawdir.iterdir()):
            data=f.read_bytes()
            entry=tarfile.TarInfo(f.name);entry.size=len(data);entry.mtime=0
            t.addfile(entry,io.BytesIO(data))
    nonce=os.urandom(12)
    crypt=nonce+AESGCM(bytes.fromhex(key)).encrypt(nonce,pack.getvalue(),b"kyoto-nov22-postrace-observed-menus-v1")
    (sealed/"menus.tar.gz.aesgcm").write_bytes(crypt)
    (sealed/"cipher_sha256.txt").write_text(hashlib.sha256(crypt).hexdigest()+"\n")
    (sealed/"safe_menu_receipt.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    assert AESGCM(bytes.fromhex(key)).decrypt(nonce,crypt[12:],b"kyoto-nov22-postrace-observed-menus-v1")==pack.getvalue()
    shutil.rmtree(rawdir)
    print("POSTRACE_RESULT_MENU="+report["menus"]["results"]["state"])
    print("POSTRACE_PAYOUT_MENU="+report["menus"]["payout"]["state"])
    for keyname,info in report["menus"].items():
        print("OBSERVED_"+keyname.upper()+"_NAV="+json.dumps(info.get("navigation",[])[:35],ensure_ascii=False)[:3400])
    print("NO_FINAL_RESULT_OR_PAYOUT_SUCCESS_ASSUMED")
if __name__=="__main__":main()
