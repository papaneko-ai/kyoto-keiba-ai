"""JRA Nov22 12R followup: genuine odds originals from saved racecard actions.

Uses independently captured/hashed R1-R12 official HTML; extracts exact
doAction(... CNAME) from HTML. PC first and SP only when captured SP racecard
is present. Never synthesize CNAME, never calls odds final 'pre-race'.
Archives every HTTP response as AES-GCM; preserve errors and per-race state.
"""
from __future__ import annotations
import argparse,hashlib,io,json,os,re,shutil,tarfile,time
from datetime import datetime,timezone
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,build_opener,HTTPCookieProcessor,HTTPRedirectHandler
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DAY="20261122"
AAD_SOURCE=b"kyoto-nov22-observed-official-all12-source-only"
AAD_NEW=b"kyoto-nov22-actual-odds-source-remainder-v1"
LIMIT=1_500_000
ACTION=re.compile(r"doAction\s*\(\s*['\"](/JRADB/accessO\.html)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",re.I)
MARKET={"馬連":"quinella","枠連":"bracket_quinella"}
DATE_MARKERS=("2026年11月22日","2026/11/22")
TOKEN=re.compile(r"(pw|sw)[A-Za-z0-9]+/[A-Za-z0-9]+")
SAFE_NAME=re.compile(r"r(0[1-9]|1[0-2])_(pc|sp)_official_racecard\.html")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError("REDIRECT_REJECTED")

def utc():
    return datetime.now(timezone.utc).isoformat()

def decode(raw):
    try:return raw.decode("utf8")
    except UnicodeError:return raw.decode("cp932",errors="replace")

def actions(raw,*,label,channel,day,race):
    soup=BeautifulSoup(decode(raw),"html.parser")
    tokens=set()
    for a in soup.select("a[onclick]"):
        if a.get_text(" ",strip=True)!=label:continue
        m=ACTION.search(a.get("onclick",""))
        if not m:continue
        token=m.group(2)
        if not TOKEN.fullmatch(token):continue
        if not token.startswith("pw" if channel=="PC" else "sw"):continue
        if f"{race:02d}{day}" not in token:continue
        tokens.add(token)
    return sorted(tokens)

def fetch(opener,channel,token,pacer,*,referer):
    if not TOKEN.fullmatch(token) or not token.startswith("pw" if channel=="PC" else "sw"):
        raise ValueError("UNOBSERVED_OR_INVALID_CNAME")
    host="jra.jp" if channel=="PC" else "app.jra.jp"
    endpoint=f"https://{host}/JRADB/accessO.html"
    if urlsplit(referer).hostname!=host:raise ValueError("CROSS_ORIGIN_REFERER")
    now=time.monotonic()
    delay=2.0-(now-pacer[0])
    if delay>0:time.sleep(delay)
    pacer[0]=time.monotonic()
    request=Request(endpoint,data=urlencode({"cname":token}).encode("ascii"),
        headers={"Accept":"text/html","Content-Type":"application/x-www-form-urlencoded",
                 "User-Agent":"Mozilla/5.0","Referer":referer},method="POST")
    began=utc()
    try:
        with opener.open(request,timeout=12) as response:
            raw=response.read(LIMIT+1)
            final=response.geturl()
            status=response.status
            ctype=response.headers.get("Content-Type","")
        if final!=endpoint or status!=200 or "html" not in ctype.lower() or not 0<len(raw)<=LIMIT:
            raise ValueError("OFFICIAL_RESPONSE_NOT_ACCEPTED")
        return {"raw":raw,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
                "captured_at_utc":utc(),"requested_at_utc":began,
                "official_post_url":endpoint,"http_status":status}
    except Exception:
        raise

def stored_originals(path,key):
    blob=(path/"originals_all12.tar.gz.aesgcm").read_bytes()
    expected=(path/"ciphertext_sha256.txt").read_text().strip()
    if hashlib.sha256(blob).hexdigest()!=expected:
        raise ValueError("ARCHIVED_SOURCE_CIPHER_SHA_MISMATCH")
    clear=AESGCM(key).decrypt(blob[:12],blob[12:],AAD_SOURCE)
    objects={}
    with tarfile.open(fileobj=io.BytesIO(clear),mode="r:gz") as tar:
        for item in tar.getmembers():
            if not item.isfile() or not (item.name=="receipt.json" or SAFE_NAME.fullmatch(item.name)) or item.name in objects:
                raise ValueError("INVALID_OR_DUPLICATE_ARCHIVE_MEMBER")
            objects[item.name]=tar.extractfile(item).read(LIMIT+1)
    receipt=json.loads(objects["receipt.json"])
    if receipt.get("day")!=DAY:raise ValueError("SOURCE_DAY_MISMATCH")
    for race in range(1,13):
        for ch in ("PC","SP"):
            item=receipt["races"][str(race)].get(ch,{})
            filename=f"r{race:02d}_{ch.lower()}_official_racecard.html"
            if filename not in objects:continue
            if hashlib.sha256(objects[filename]).hexdigest()!=item.get("sha256"):
                raise ValueError("SAVED_RACECARD_RECEIPT_SHA_MISMATCH")
    return objects,receipt

def store(root,filename,result):
    raw=result.pop("raw")
    path=root/filename
    with path.open("xb") as f:f.write(raw)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=result["sha256"]:
        raise ValueError("SAVE_DIGEST_MISMATCH")
    return result

def main():
    key_hex=os.getenv("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",key_hex):
        raise ValueError("AES_KEY_MISSING_BEFORE_NETWORK")
    key=bytes.fromhex(key_hex)
    sources,receipt=stored_originals(Path("nov22_all12_source"),key)
    base=Path("nov22_market_followup")
    if base.exists():raise ValueError("FRESH_WORKSPACE_REQUIRED")
    raw_dir=base/"raw";raw_dir.mkdir(parents=True)
    sealed=base/"sealed";sealed.mkdir()
    report={"schema":"kyoto_nov22_real_odds_followup.v1",
            "day":DAY,"captured_batch_at_utc":utc(),
            "source_only":True,"pre_race_odds_certified":False,
            "prediction_ready":False,"actual_wager_authorized":False,
            "races":{}}
    pacer=[0.0]
    opens={ch:build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
           for ch in ("PC","SP")}
    # Late-starting runs continue through all races: they are never counted
    # as pre-race market snapshots merely because the source is available.
    for race in range(12,0,-1):
        row={"PC":{},"SP":{}}
        for channel in ("PC","SP"):
            ch=channel.lower()
            fname=f"r{race:02d}_{ch}_official_racecard.html"
            if fname not in sources:
                row[channel]={"state":"SAVED_RACECARD_ABSENT"}
                continue
            racecard=sources[fname]
            odds=actions(racecard,label="オッズ",channel=channel,day=DAY,race=race)
            if len(odds)!=1:
                row[channel]={"state":"OFFICIAL_ODDS_NAV_NOT_UNIQUE_OR_MISSING",
                              "observed_action_count":len(odds)}
                continue
            referer=receipt["races"][str(race)][channel]["observed_official_url"]
            entry={"state":"RACECARD_NAV_OBSERVED",
                   "odds_menu_action_sha256":hashlib.sha256(odds[0].encode()).hexdigest(),
                   "market_items":{}}
            try:
                response=fetch(opens[channel],channel,odds[0],pacer,referer=referer)
                raw=response["raw"]
                store(raw_dir,f"r{race:02d}_{ch}_odds_menu.html",response)
                entry["odds_menu_receipt"]=response
                entry["state"]="OFFICIAL_ODDS_MENU_RAW_SAVED"
                if "最終オッズ" in decode(raw):
                    entry["market_phase"]="FINAL_ODDS_OR_POST_START"
                else:
                    entry["market_phase"]="TIMING_UNVERIFIED_REQUIRE_START_COMPARISON"
                # A matched odds-page title and exact race marker is required
                # before extracting real market actions. If this is merely a
                # navigation page, retain it and report the unsupported step.
                soup=BeautifulSoup(decode(raw),"html.parser")
                if "オッズ" not in (soup.title.get_text(" ",strip=True) if soup.title else ""):
                    entry["state"]="ODDS_MENU_TITLE_NOT_PROVEN_RAW_RETAINED"
                elif f"{race:02d}{DAY}" not in decode(raw):
                    entry["state"]="ODDS_MENU_RACE_BINDING_NOT_PROVEN_RAW_RETAINED"
                else:
                    for label,market in MARKET.items():
                        matches=actions(raw,label=label,channel=channel,day=DAY,race=race)
                        if len(matches)!=1:
                            entry["market_items"][market]={"state":"MARKET_ACTION_NOT_UNIQUE",
                                                           "count":len(matches)}
                            continue
                        try:
                            result=fetch(opens[channel],channel,matches[0],pacer,
                                         referer=response["official_post_url"])
                            store(raw_dir,f"r{race:02d}_{ch}_{market}_original.html",result)
                            entry["market_items"][market]={
                                "state":"RAW_ORIGINAL_SAVED_NUMERICAL_PARSER_NOT_YET_VERIFIED",
                                **result}
                        except Exception as exc:
                            entry["market_items"][market]={
                                "state":"MARKET_POST_FAILED","error_class":type(exc).__name__}
            except Exception as exc:
                entry.update(state="ODDS_MENU_POST_FAILED",
                             error_class=type(exc).__name__)
            row[channel]=entry
            # Only one source lane needed once two raw market originals exist;
            # absent/failed market may still permit independent SP fallback.
            if channel=="PC" and all(entry["market_items"].get(m,{}).get("state","").startswith(
                  "RAW_ORIGINAL_SAVED") for m in MARKET.values()):
                row["SP"]={"state":"PC_BOTH_MARKET_ORIGINALS_SAVED_SKIP_DUPLICATE"}
                break
        report["races"][str(race)]=row
    (raw_dir/"source_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode="w:gz") as tar:
        for path in sorted(raw_dir.iterdir()):
            content=path.read_bytes()
            info=tarfile.TarInfo(path.name);info.size=len(content);info.mtime=0
            tar.addfile(info,io.BytesIO(content))
    nonce=os.urandom(12)
    cipher=nonce+AESGCM(key).encrypt(nonce,stream.getvalue(),AAD_NEW)
    if AESGCM(key).decrypt(nonce,cipher[12:],AAD_NEW)!=stream.getvalue():
        raise ValueError("AES_ROUNDTRIP_MISMATCH")
    (sealed/"market_followup.tar.gz.aesgcm").write_bytes(cipher)
    (sealed/"encrypted_sha256.txt").write_text(hashlib.sha256(cipher).hexdigest()+"\n")
    (sealed/"safe_market_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    shutil.rmtree(raw_dir)
    menus=sum(any(x.get("state") in ("OFFICIAL_ODDS_MENU_RAW_SAVED",
                 "ODDS_MENU_TITLE_NOT_PROVEN_RAW_RETAINED",
                 "ODDS_MENU_RACE_BINDING_NOT_PROVEN_RAW_RETAINED")
                 for x in r.values()) for r in report["races"].values())
    pair=sum(any(all(x.get("market_items",{}).get(m,{}).get("state","").startswith(
              "RAW_ORIGINAL_SAVED") for m in MARKET.values())
              for x in r.values()) for r in report["races"].values())
    print("ACTUAL_OFFICIAL_ODDS_MENU_RACES="+str(menus)+"/12")
    print("ACTUAL_BOTH_MARKET_ORIGINAL_RACES="+str(pair)+"/12")
    print("SOURCE_AES_256_GCM_SAVED_SHA256_VERIFIED")
    print("PRE_RACE_MARKET_CERTIFICATION_FALSE;RESULTS_NOT_CAPTURED")
if __name__=="__main__":main()
