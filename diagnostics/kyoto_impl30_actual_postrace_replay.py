"""One bounded historical read-only acquisition for 2026-11-22 only.

The prior real G03 archive supplies registered runners, start times and observed
navigation; current historical capture timestamps are never backdated. Reuse
the actual deployed parser, and retain authenticated raw bytes for offline
repair if the official result or payout layout rejects them. No wagers, no
prediction, no future-day or production-state writes.
"""
import argparse,os,json,re,time,tempfile
from pathlib import Path
from datetime import datetime,date,timezone,timedelta
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.parse import urlencode,urlsplit,parse_qs
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from hashlib import sha256
from bs4 import BeautifulSoup
from diagnostics.kyoto_impl30_actual_profile_replay import archive
from diagnostics.jra_multi_capture_20261106 import parse
from diagnostics.kyoto_impl30_postrace_day import observed_actions,parse_result,MENU
from diagnostics.kyoto_impl30_final_reconcile import reconcile
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence,decrypt_evidence
from diagnostics.jra_one_shot_market_capture import NoRedirect,RequestPacer

DAY="20261122"
JST=timezone(timedelta(hours=9))
def actual_inputs(key):
    files=archive("nov22_cards","originals_all12.tar.gz.aesgcm",b"kyoto-nov22-observed-official-all12-source-only",re.compile(r"(?:r(?:0[1-9]|1[0-2])_(?:pc|sp)_official_racecard\.html|receipt\.json)"),key,10000000)
    receipt=json.loads(files["receipt.json"])
    if receipt.get("day")!=DAY:raise ValueError("wrong_original_day")
    cards={};roster={};starts={}
    for race in range(1,13):
        raw=files[f"r{race:02d}_pc_official_racecard.html"];meta=receipt["races"][str(race)]["PC"]
        if sha256(raw).hexdigest()!=meta["sha256"]:raise ValueError("original_sha")
        rows,errors=parse(raw,race,meeting_date=date(2026,11,22))
        if errors:raise ValueError("original_roster")
        soup=BeautifulSoup(raw.decode("cp932",errors="strict"),"html.parser")
        matches=set(re.findall(r"発走(?:予定)?(?:時刻)?\s*[:：]?\s*([01]?\d|2[0-3]):([0-5]\d)",soup.get_text(" ",strip=True)))
        if len(matches)!=1:raise ValueError("original_start")
        h,m=map(int,next(iter(matches)))
        starts[race]=datetime(2026,11,22,h,m,tzinfo=JST).astimezone(timezone.utc).isoformat()
        roster[race]=[(r["horse_number"],r["frame_number"],r["horse_name"]) for r in rows]
        cards[race]=raw
    return cards,roster,starts

def only(actions):
    candidates={(a[1],a[2],a[3]) for a in actions}
    if len(candidates)!=1:raise ValueError("ambiguous_or_missing_observed_action")
    return next(iter(candidates))

def collect(root,seed,fetch):
    root=Path(root);root.mkdir()
    report={"day":DAY,"schema":"kyoto_impl30_actual_historical_postrace.v1","requests":{},"failures":{},"historical_only":True}
    (root/"postrace_seed.html").write_bytes(seed)
    def save(name,action):
        token,method,url=only(action)
        data,stamp=fetch(method,url,token)
        (root/name).write_bytes(data)
        report["requests"][name]={"sha256":sha256(data).hexdigest(),"bytes":len(data),"captured_at_utc":stamp,"url":url,"token":token,"method":method}
        return data
    meetings={}
    for family,(path,label) in MENU.items():
        try:
            raw=save(family+"_menu.html",[a for a in observed_actions(seed,path) if a[0]==label])
            kind="srl" if family=="results" else "hde"
            matching=[a for a in observed_actions(raw,path) if re.fullmatch(r"\d+回京都\d+日",a[0]) and re.fullmatch(r"pw01"+kind+r"[01]0082026\d{4}"+DAY+r"/[A-Za-z0-9]+",a[1])]
            meetings[family]=save(family+"_meeting.html",matching)
        except Exception as exc:report["failures"][family]=type(exc).__name__+":"+str(exc)[:100]
    if "results" in meetings:
        for race in range(1,13):
            try:
                matches=[a for a in observed_actions(meetings["results"],MENU["results"][0]) if re.fullmatch(r"pw01sde[01]0082026\d{4}"+f"{race:02d}"+DAY+r"/[A-Za-z0-9]+",a[1])]
                save(f"r{race:02d}_result.html",matches)
            except Exception as exc:report["failures"][str(race)]=type(exc).__name__+":"+str(exc)[:100]
    (root/"receipt.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    return report

def analyze(root,roster,starts):
    root=Path(root);receipt=json.loads((root/"receipt.json").read_text())
    if receipt.get("day")!=DAY:raise ValueError("wrong_capture_day")
    sources={}
    for name,meta in receipt["requests"].items():
        p=root/name
        if p.is_symlink() or not p.is_file():raise ValueError("missing_source")
        data=p.read_bytes()
        if len(data)!=meta["bytes"] or sha256(data).hexdigest()!=meta["sha256"]:raise ValueError("source_sha")
        sources[name]=data
    payout=sources.get("payout_meeting.html")
    report={"day":DAY,"result_originals":0,"registered_rows":sum(map(len,roster.values())),"payout_meeting_original":payout is not None,"result_payout_parsed":0,"dual_page_matched":0,"explicit_final":0,"races":{},"capture_failures":receipt["failures"],"prediction_ready":False}
    for race in range(1,13):
        name=f"r{race:02d}_result.html";raw=sources.get(name)
        row={};report["races"][str(race)]=row
        if not raw:row["state"]="NO_ORIGINAL";continue
        report["result_originals"]+=1;meta=receipt["requests"][name]
        try:
            parsed=parse_result(raw,day=DAY,race=race,url=meta["url"],registered=roster[race])
            row["parsed_state"]=parsed["state"]
            row["parsed_reason"]=parsed.get("reason")
            report["result_payout_parsed"]+=int("quinella" in parsed and "bracket_quinella" in parsed)
        except Exception as exc:row["parse_error"]=type(exc).__name__+":"+str(exc)[:100]
        if payout is None:continue
        try:
            rec=reconcile(result_raw=raw,payout_raw=payout,day=DAY,race=race,registered=roster[race],
                result_url=meta["url"],result_utc=meta["captured_at_utc"],payout_utc=receipt["requests"]["payout_meeting.html"]["captured_at_utc"],start_utc=starts[race])
            row["reconciliation"]=rec["state"];report["dual_page_matched"]+=1
            report["explicit_final"]+=int(rec["state"]=="DUAL_PAGE_EXPLICIT_FINAL")
        except Exception as exc:row["reconcile_error"]=type(exc).__name__+":"+str(exc)[:100]
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument("--replay-only",action="store_true");p.add_argument("--prior-run");a=p.parse_args()
    key=os.environ["ARCHIVE_KEY"];repo=os.environ["GITHUB_REPOSITORY"];rid=os.environ["GITHUB_RUN_ID"]
    if os.environ.get("KYOTO_TARGET_DAY")!=DAY or not re.fullmatch(r"[a-fA-F0-9]{64}",key):raise ValueError("historical_configuration")
    cards,roster,starts=actual_inputs(bytes.fromhex(key))
    with tempfile.TemporaryDirectory(prefix="kyoto_actual_historical_") as d:
        raw=Path(d)/"raw"
        if a.replay_only:
            if not a.prior_run or not a.prior_run.isdigit():raise ValueError("prior_run_required")
            decrypt_evidence("prior_sealed",raw,key_hex=key,repo=repo,run_id=a.prior_run)
        else:
            if os.environ.get("KYOTO_HISTORICAL_READ_APPROVED")!="NOV22_ONLY" or datetime.now(timezone.utc).date()<=date(2026,11,22):raise ValueError("historical_only")
            client=build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()));pacer=RequestPacer(min_gap_seconds=2.0)
            refused=False;count=0
            def fetch(method,url,token):
                nonlocal refused,count
                if refused or count>=16:raise ValueError("historical_request_limit_or_refusal")
                u=urlsplit(url)
                if u.scheme!="https" or u.netloc!="jra.jp" or u.path not in [v[0] for v in MENU.values()] or u.fragment or not re.fullmatch(r"pw[A-Za-z0-9]+/[A-Za-z0-9]+",token):raise ValueError("historical_observed_target_only")
                if method=="POST" and not u.query:data=urlencode({"cname":token}).encode("ascii")
                elif method=="GET" and parse_qs(u.query)=={"CNAME":[token]}:data=None
                else:raise ValueError("method_binding")
                pacer.before_request();count+=1
                try:
                    with client.open(Request(url,method=method,data=data,headers={"Accept":"text/html","Content-Type":"application/x-www-form-urlencoded","User-Agent":"KyotoRaceAI-Private-ReadOnly/0.1"}),timeout=12) as response:
                        blob=response.read(1500001)
                        if response.status!=200 or response.geturl()!=url or not 0<len(blob)<=1500000 or "html" not in response.headers.get("Content-Type","").lower():raise ValueError("response_rejected")
                except HTTPError as exc:
                    if exc.code in (401,403,429):refused=True
                    raise
                except ValueError:
                    refused=True
                    raise
                return blob,datetime.now(timezone.utc).isoformat()
            collect(raw,cards[1],fetch)
            encrypt_evidence(raw,Path("historical_sealed"),key_hex=key,repo=repo,run_id=rid)
        result=analyze(raw,roster,starts)
        out=Path("historical_report");out.mkdir()
        (out/"report.json").write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
