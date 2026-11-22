"""2026-11-22 official horse profile/history original capture from real saved racecards.

No guessed JRA horse IDs; enumerate only actual saved PC racecard
anchors; prioritize later races first; one GET per unique profile URL.
AES-GCM encrypted-only archive. A saved HTML is not proof of parsed history.
"""
from __future__ import annotations
import hashlib,io,json,os,re,shutil,tarfile,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin,urlsplit,parse_qs
from urllib.request import Request,build_opener,HTTPRedirectHandler
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DAY="20261122"
AAD_SOURCE=b"kyoto-nov22-observed-official-all12-source-only"
AAD_PROFILE=b"kyoto-nov22-observed-profile-history-originals-v1"
LIMIT=1_500_000
TOKEN=re.compile(r"pw[0-9A-Za-z]+/[0-9A-Za-z]+")
FILE=re.compile(r"r(0[1-9]|1[0-2])_(pc|sp)_official_racecard.html")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("REDIRECT_REJECTED")

def utc():return datetime.now(timezone.utc).isoformat()

def decode(raw):
    try:return raw.decode("utf8")
    except UnicodeDecodeError:return raw.decode("cp932",errors="replace")

def official_profile(href):
    if not isinstance(href,str) or not href.startswith("/JRADB/accessU.html?"):
        return None
    u=urlsplit("https://jra.jp"+href)
    q=parse_qs(u.query,strict_parsing=True)
    if (u.scheme!="https" or u.hostname!="jra.jp" or u.path!="/JRADB/accessU.html"
        or u.port is not None or u.fragment or set(q)!={"CNAME"} or len(q["CNAME"])!=1
        or not TOKEN.fullmatch(q["CNAME"][0])):
        return None
    return "https://jra.jp"+href

def source_cards(key):
    root=Path("nov22_all12_source")
    blob=(root/"originals_all12.tar.gz.aesgcm").read_bytes()
    if hashlib.sha256(blob).hexdigest()!=(root/"ciphertext_sha256.txt").read_text().strip():
        raise ValueError("SOURCE_CIPHER_SHA_MISMATCH")
    clear=AESGCM(key).decrypt(blob[:12],blob[12:],AAD_SOURCE)
    files={}
    with tarfile.open(fileobj=io.BytesIO(clear),mode="r:gz") as tar:
        for info in tar.getmembers():
            if not info.isfile() or not (FILE.fullmatch(info.name) or info.name=="receipt.json"):
                raise ValueError("UNTRUSTED_ARCHIVE_ENTRY")
            files[info.name]=tar.extractfile(info).read(LIMIT+1)
    receipt=json.loads(files["receipt.json"])
    if receipt["day"]!=DAY:raise ValueError("WRONG_RACE_DAY")
    for race in range(1,13):
        name=f"r{race:02d}_pc_official_racecard.html"
        if name not in files:continue
        if hashlib.sha256(files[name]).hexdigest()!=receipt["races"][str(race)]["PC"]["sha256"]:
            raise ValueError("RACECARD_SHA_MISMATCH")
    return files,receipt

def plan(files):
    pending=[]
    seen={}
    for race in range(12,0,-1):
        name=f"r{race:02d}_pc_official_racecard.html"
        if name not in files:continue
        soup=BeautifulSoup(decode(files[name]),"html.parser")
        for a in soup.select('td.horse a[href],a[href^="/JRADB/accessU.html?"]'):
            url=official_profile(a.get("href"))
            if not url:continue
            if url in seen:
                seen[url].append(race)
                continue
            seen[url]=[race]
            pending.append({"url":url,"races":[race],
                            "horse_name_observed":a.get_text(" ",strip=True)})
    for item in pending:item["races"]=seen[item["url"]]
    return pending

def main():
    keyhex=os.getenv("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",keyhex):
        raise ValueError("ARCHIVE_KEY_MISSING_BEFORE_JRA_GET")
    key=bytes.fromhex(keyhex)
    originals,receipt=source_cards(key)
    queue=plan(originals)
    base=Path("nov22_profile_capture")
    if base.exists():raise ValueError("FRESH_OUTPUT_REQUIRED")
    rawdir=base/"raw";rawdir.mkdir(parents=True)
    seal=base/"sealed";seal.mkdir()
    output={"schema":"kyoto_nov22_real_profile_originals.v1",
            "day":DAY,"source_only":True,"training_ready":False,
            "history_parsed":False,"permanent_horse_ids_verified":False,
            "planned_unique_horse_profiles":len(queue),
            "started_at_utc":utc(),"items":[]}
    opener=build_opener(NoRedirect())
    last=0.0
    deadline=time.monotonic()+650
    for index,item in enumerate(queue):
        r={"priority_index":index+1,"races":item["races"],
           "observed_racecard_name":item["horse_name_observed"],
           "observed_profile_url_sha256":hashlib.sha256(item["url"].encode()).hexdigest(),
           "request_started_at_utc":utc(),"state":"NOT_STARTED"}
        if time.monotonic()>deadline:
            r["state"]="BUDGET_STOP_NOT_ATTEMPTED";output["items"].append(r)
            continue
        try:
            delta=2.0-(time.monotonic()-last)
            if delta>0:time.sleep(delta)
            last=time.monotonic()
            with opener.open(Request(item["url"],headers={
                "Accept":"text/html","User-Agent":"Mozilla/5.0"},
                method="GET"),timeout=12) as response:
                data=response.read(LIMIT+1)
                status=response.status
                got=response.geturl()
                content_type=response.headers.get("Content-Type","")
            if got!=item["url"] or status!=200 or "html" not in content_type.lower() or not 0<len(data)<=LIMIT:
                raise ValueError("OFFICIAL_PROFILE_RESPONSE_REJECTED")
            fname=f"profile_{index+1:03d}.html"
            (rawdir/fname).write_bytes(data)
            r.update(state="OFFICIAL_PROFILE_ORIGINAL_SAVED_HISTORY_NOT_PARSED",
                     sha256=hashlib.sha256(data).hexdigest(),
                     captured_at_utc=utc(),bytes=len(data),encrypted_filename=fname,
                     visible_name_match=item["horse_name_observed"] in decode(data))
        except Exception as exc:
            r.update(state="PROFILE_REQUEST_OR_SOURCE_FAILED",
                     error_class=type(exc).__name__)
        output["items"].append(r)
    (rawdir/"profile_receipt.json").write_text(
        json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w:gz") as t:
        for file in sorted(rawdir.iterdir()):
            raw=file.read_bytes()
            info=tarfile.TarInfo(file.name);info.size=len(raw);info.mtime=0
            t.addfile(info,io.BytesIO(raw))
    nonce=os.urandom(12)
    blob=nonce+AESGCM(key).encrypt(nonce,buf.getvalue(),AAD_PROFILE)
    if AESGCM(key).decrypt(nonce,blob[12:],AAD_PROFILE)!=buf.getvalue():
        raise ValueError("AES_VERIFY_FAILED")
    (seal/"horse_profiles.tar.gz.aesgcm").write_bytes(blob)
    (seal/"ciphertext_sha256.txt").write_text(hashlib.sha256(blob).hexdigest()+"\n")
    (seal/"safe_profile_receipt.json").write_text(
        json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    shutil.rmtree(rawdir)
    ok=sum(x["state"]=="OFFICIAL_PROFILE_ORIGINAL_SAVED_HISTORY_NOT_PARSED"
           for x in output["items"])
    print("ACTUAL_PROFILE_ORIGINALS_SAVED="+str(ok)+"/"+str(len(queue)))
    print("HISTORY_PARSED_FALSE;AES_GCM_ENCRYPTED_SOURCE_PRESERVED")
if __name__=="__main__":main()
