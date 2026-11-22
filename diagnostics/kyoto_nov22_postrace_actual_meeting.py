"""JRA official observed 2026-11-22 Kyoto meeting results and payout ORIGINALS.

The two exact per-meeting action codes originate in independently captured
official JRA menu. No guessed tokens and no observed-result fabricated.
"""
import hashlib,io,json,os,re,tarfile,shutil,time
from datetime import datetime,timezone
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.request import Request,build_opener,HTTPCookieProcessor,HTTPRedirectHandler
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
AAD_OLD=b"kyoto-nov22-postrace-observed-menus-v1"
AAD_NEW=b"kyoto-nov22-result-payout-observed-meeting-v1"
ACTION=re.compile(r"doAction\s*\(\s*['\"](/JRADB/access[SH]\.html)['\"]\s*,\s*['\"]([^'\"]+)['\"]")
TASK={"result":("results","/JRADB/accessS.html"),
      "payout":("payout","/JRADB/accessH.html")}
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("REDIRECT_REJECTED")
def utc():return datetime.now(timezone.utc).isoformat()
def text(raw):
    try:return raw.decode("utf8")
    except UnicodeError:return raw.decode("cp932",errors="replace")
def main():
    keystr=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[a-fA-F0-9]{64}",keystr):raise ValueError("AES_KEY_MISSING")
    key=bytes.fromhex(keystr)
    base=Path("observed_menus")
    blob=(base/"menus.tar.gz.aesgcm").read_bytes()
    if hashlib.sha256(blob).hexdigest()!=(base/"cipher_sha256.txt").read_text().strip():
        raise ValueError("MENU_CIPHERTEXT_SHA_MISMATCH")
    clear=AESGCM(key).decrypt(blob[:12],blob[12:],AAD_OLD)
    files={}
    with tarfile.open(fileobj=io.BytesIO(clear),mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or "/" in m.name or ".." in m.name:raise ValueError("UNSAFE_MENU_ARCHIVE")
            files[m.name]=tar.extractfile(m).read(1500001)
    previous=json.loads(files["source_receipt.json"])
    if previous.get("race_day")!="20261122":raise ValueError("WRONG_MENU_DAY")
    root=Path("meeting_result_payout");rawdir=root/"raw";rawdir.mkdir(parents=True)
    sealed=root/"sealed";sealed.mkdir()
    report={"schema":"kyoto_nov22_actual_result_payout_meeting_origins.v1",
            "day":"20261122","source_only":True,
            "all_race_results_verified":False,"all_payouts_verified":False,
            "requires_post_finishevent_refresh":True,
            "items":{}}
    opener=build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
    for idx,(kind,(fromkey,path)) in enumerate(TASK.items()):
        orig=files[fromkey+"_official_menu.html"]
        receipt=previous["menus"][fromkey]
        if hashlib.sha256(orig).hexdigest()!=receipt.get("sha256"):
            raise ValueError("MENU_ORIGINAL_SHA_NOT_PROVEN")
        soup=BeautifulSoup(text(orig),"html.parser")
        tokens=set()
        for a in soup.select("a[onclick]"):
            if a.get_text(" ",strip=True)!="5回京都6日":continue
            m=ACTION.search(a.get("onclick",""))
            if m and m.group(1)==path and "20261122" in m.group(2) and "08" in m.group(2):
                tokens.add(m.group(2))
        row={"unique_observed_official_actions":len(tokens),
             "state":"MEETING_LINK_MISSING_OR_AMBIGUOUS"}
        if len(tokens)==1:
            token=next(iter(tokens))
            url="https://jra.jp"+path
            time.sleep(2*idx)
            row["request_started_at_utc"]=utc()
            try:
                with opener.open(Request(url,data=urlencode({"cname":token}).encode("ascii"),
                    headers={"Accept":"text/html","Content-Type":"application/x-www-form-urlencoded",
                             "User-Agent":"Mozilla/5.0",
                             "Referer":"https://jra.jp/JRADB/"+("accessS.html" if kind=="result" else "accessH.html")},
                    method="POST"),timeout=12) as res:
                    data=res.read(1500001)
                    final=res.geturl()
                    typ=res.headers.get("Content-Type","")
                    status=res.status
                if final!=url or status!=200 or "html" not in typ.lower() or not 0<len(data)<=1500000:
                    raise ValueError("OFFICIAL_MEETING_RESPONSE_NOT_AUTHENTICATED")
                (rawdir/(kind+"_meeting_original.html")).write_bytes(data)
                doc=BeautifulSoup(text(data),"html.parser")
                v=doc.get_text(" ",strip=True)
                links=[]
                for a in doc.select("a[onclick]"):
                    m=ACTION.search(a.get("onclick",""))
                    if m:
                        links.append({"label":a.get_text(" ",strip=True)[:60],
                                      "action":m.group(1),"observed_token":m.group(2)})
                row.update(state="OFFICIAL_MEETING_ORIGINAL_SAVED_RESULT_TABLE_UNVERIFIED",
                    captured_at_utc=utc(),sha256=hashlib.sha256(data).hexdigest(),
                    bytes=len(data),day_visible=("2026年11月22日" in v or "2026/11/22" in v),
                    kyoto_visible="京都" in v,
                    visible_race_labels=sorted(set(re.findall(r"(?:^|\s)(?:[1-9]|1[0-2])R",v))),
                    observed_navigation=links[:90])
            except Exception as e:
                row.update(state="MEETING_OFFICIAL_REQUEST_REJECTED",error_class=type(e).__name__)
        report["items"][kind]=row
    (rawdir/"receipt.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    tarbuf=io.BytesIO()
    with tarfile.open(fileobj=tarbuf,mode="w:gz") as t:
        for p in sorted(rawdir.iterdir()):
            b=p.read_bytes()
            e=tarfile.TarInfo(p.name);e.size=len(b);e.mtime=0
            t.addfile(e,io.BytesIO(b))
    nonce=os.urandom(12)
    encrypted=nonce+AESGCM(key).encrypt(nonce,tarbuf.getvalue(),AAD_NEW)
    assert AESGCM(key).decrypt(nonce,encrypted[12:],AAD_NEW)==tarbuf.getvalue()
    (sealed/"actual_meeting_result_payout.tar.gz.aesgcm").write_bytes(encrypted)
    (sealed/"cipher_sha256.txt").write_text(hashlib.sha256(encrypted).hexdigest()+"\n")
    (sealed/"safe_meeting_receipt.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    shutil.rmtree(rawdir)
    for kind,row in report["items"].items():
        print("ACTUAL_KYOTO_MEETING_"+kind.upper()+"="+row["state"])
        print("ACTUAL_KYOTO_"+kind.upper()+"_LINKS="+json.dumps(row.get("observed_navigation",[])[:35],ensure_ascii=False)[:4100])
    print("NO_RESULT_FINAL_CONFIRMATION_WITHOUT_RACE_LEVEL_PROOF")
if __name__=="__main__":main()
