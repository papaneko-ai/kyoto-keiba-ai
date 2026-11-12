"""One-shot bounded JRA official odds retrieval, no guessed CNAME, no retries.

Experimental diagnostic only. Intentionally cannot auto-run before publication,
after the independently confirmed freeze cutoff, or against unofficial hosts.
Every HTTP response has a separate timestamp, byte count, and SHA-256.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta,date
from zoneinfo import ZoneInfo
from pathlib import Path
from hashlib import sha256
from http.cookiejar import CookieJar
from urllib.request import Request,build_opener,HTTPCookieProcessor,HTTPRedirectHandler
from urllib.parse import urlsplit,urlencode
from bs4 import BeautifulSoup
import argparse,json,re,time,unicodedata
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs

from diagnostics.jra_official_market_navigation import find_market_links,MarketNavigationError
from diagnostics.jra_market_source_chain import audit_source_originals,SourceChainError
from diagnostics.jra_odds_source_archive import aware_utc

RACE_DAY="20261107"
RACE_NUMBER=11
RACE_ID="2026-11-07_KYOTO_11R"
VENUE="京都"
NORMAL_SALES_OPEN_UTC="2026-11-06T09:30:00+00:00"
PC_RACECARD_URL="https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605011120261107%2F13"
SP_RACECARD_URL="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605011120261107%2FA0"
MOBILE_UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
ACTION=re.compile(r"doAction\s*\(\s*['\"](/JRADB/accessO\.html)['\"]\s*,\s*['\"]([^'\"]+)['\"]")
LIMIT=1_500_000

class RequestPacer:
    """Rate limit requests within this one-shot, including PC/SP fallback.

    This does not claim global deduplication across separately running
    hosts; the offline cross-process registry is a distinct existing gate.
    """
    def __init__(self,*,min_gap_seconds=2.0,clock=None,sleep=None):
        self.clock=clock if clock is not None else time.monotonic
        self.sleep=sleep if sleep is not None else time.sleep
        if min_gap_seconds<2:
            raise SourceChainError("jra_request_gap_under_two_seconds")
        self.gap=min_gap_seconds
        self.last=None
    def before_request(self):
        current=self.clock()
        if self.last is not None:
            remaining=self.gap-(current-self.last)
            if remaining>0:
                self.sleep(remaining)
        self.last=self.clock()

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise SourceChainError('redirect_forbidden')


@dataclass(frozen=True)
class ObservedRaceSpec:
    """User-supplied, independently observed official navigation, never guessed."""
    race_day: str
    race_number: int
    race_id: str
    venue: str
    pc_racecard_url: str
    sp_racecard_url: str
    normal_sales_open_utc: str

    def validate(self,*,require_channels=("PC","SP")):
        if (not isinstance(require_channels,(tuple,list))
            or len(require_channels) not in (1,2)
            or len(set(require_channels))!=len(require_channels)
            or not set(require_channels)<=set(("PC","SP"))):
            raise SourceChainError("invalid_required_channels")
        try:
            d=date.fromisoformat(self.race_day[:4]+"-"+self.race_day[4:6]+"-"+self.race_day[6:])
            if d.strftime("%Y%m%d")!=self.race_day:raise ValueError("date")
            if type(self.race_number) is not int or not 1<=self.race_number<=12:
                raise ValueError("race")
            if self.venue!="京都" or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}",self.race_id):
                raise ValueError("race_identity")
            if d.strftime("%Y-%m-%d") not in self.race_id or not re.search(
                    fr"(?:^|[_-]){self.race_number}R(?:$|[_-])",self.race_id):
                raise ValueError("race_key_not_bound")
            from diagnostics.jra_market_integrity_gate import normal_sales_open
            opening=normal_sales_open(d)
            if opening is None or aware_utc(self.normal_sales_open_utc)!=opening:
                raise ValueError("sales_time_not_independently_validated")
            for channel,url in (("PC",self.pc_racecard_url),("SP",self.sp_racecard_url)):
                # A single verified PC link can be used for PC-only work;
                # NEVER guess an SP URL. Hybrid needs BOTH observed URLs.
                if channel not in require_channels:
                    if url not in ("",None):
                        # Optional unused URLs are still validated when present.
                        pass
                    else:
                        continue
                elif url in ("",None):
                    raise ValueError("required_observed_racecard_url_missing:"+channel)
                u=urlsplit(url)
                host="jra.jp" if channel=="PC" else "sp.jra.jp"
                q=parse_qs(u.query,strict_parsing=True)
                if (u.scheme!="https" or u.hostname!=host or u.port is not None
                        or u.username is not None or u.password is not None
                        or u.path!="/JRADB/accessD.html" or u.fragment
                        or set(q)!={"CNAME"} or len(q["CNAME"])!=1
                        or not re.fullmatch(r"[ps]w[A-Za-z0-9]+/[A-Za-z0-9]+",q["CNAME"][0])
                        or not q["CNAME"][0].startswith("pw" if channel=="PC" else "sw")
                        or self.race_day not in q["CNAME"][0]):
                    raise ValueError("unverified_official_racecard_url")
        except (ValueError,TypeError,OverflowError) as exc:
            raise SourceChainError("race_spec_unverified:"+str(exc)) from exc
        return self


DEFAULT_RACE_SPEC=ObservedRaceSpec(RACE_DAY,RACE_NUMBER,RACE_ID,VENUE,
    PC_RACECARD_URL,SP_RACECARD_URL,NORMAL_SALES_OPEN_UTC)


def verified_roster_from_snapshot(snapshot, spec, *, race_start_utc):
    """Bind the racecard roster to the SAME observed meeting and start time.

    Previous manual workflow accepted any JSON named 'roster', including
    2026-11-07 evidence paired with 2026-11-14 odds. That must never happen.
    This is a consistency test, not authentication of the source original.
    """
    if not isinstance(snapshot,dict):
        raise SourceChainError("racecard_snapshot_dictionary_required")
    start=aware_utc(race_start_utc)
    if start.astimezone(ZoneInfo("Asia/Tokyo")).date().strftime("%Y%m%d")!=spec.race_day:
        raise SourceChainError("race_start_date_mismatch")
    expected_date=f"{spec.race_day[:4]}-{spec.race_day[4:6]}-{spec.race_day[6:]}"
    if (snapshot.get("race_date")!=expected_date
        or snapshot.get("race_number")!=spec.race_number
        or snapshot.get("venue") not in ("KYOTO","京都")
        or type(snapshot.get("source_url")) is not str
        or not snapshot["source_url"]
        or snapshot["source_url"] not in (spec.pc_racecard_url,spec.sp_racecard_url)):
        raise SourceChainError("roster_meeting_race_source_mismatch")
    raw_sha=snapshot.get("source_sha256")
    raw_size=snapshot.get("source_bytes")
    if (type(raw_sha) is not str or not re.fullmatch(r"[0-9a-f]{64}",raw_sha)
        or type(raw_size) is not int or raw_size<1):
        raise SourceChainError("roster_original_provenance_missing")
    captured=snapshot.get("fetched_at_utc",snapshot.get("captured_at_utc"))
    if captured is None or aware_utc(captured)>=start:
        raise SourceChainError("roster_capture_not_before_start")
    runners=snapshot.get("runners")
    if (type(runners) is not list or not 2<=len(runners)<=18):
        raise SourceChainError("numbered_runner_roster_required")
    expected_numbers=list(range(1,len(runners)+1))
    numbers=[];output=[];names=set()
    for runner in runners:
        if not isinstance(runner,dict):
            raise SourceChainError("roster_runner_invalid")
        number=runner.get("horse_number");frame=runner.get("frame_number")
        name=runner.get("horse_name")
        if (type(number) is not int or type(frame) is not int
                or not 1<=frame<=8 or type(name) is not str or not name.strip()
                or name in names):
            raise SourceChainError("roster_horse_frame_or_name_invalid")
        if runner.get("status") in ("SCRATCHED","CANCELLED","WITHDRAWN","除外","取消"):
            raise SourceChainError("roster_withdrawal_needs_current_independent_proof")
        numbers.append(number);names.add(name);output.append((number,frame))
    if numbers!=expected_numbers:
        raise SourceChainError("roster_number_sequence_invalid")
    return tuple(output)



def verify_live_racecard_roster(original,channel,spec,active_runners,
                               expected_named_runners,*,captured_at_utc,observed_utc,
                               verified_start_utc):
    """Adapter to the EXISTING Nov9 three-column, SHA and UTC reconciler.

    Do not duplicate the already accepted PC/SP identity comparison.
    This is a current source safeguard, not new independent certification.
    """
    from diagnostics.jra_pc_sp_benchmark import reconcile_saved_racecards
    if not isinstance(original,bytes) or not 0<len(original)<=LIMIT:
        raise SourceChainError("racecard_original_invalid")
    if channel not in ("PC","SP"):
        raise SourceChainError("racecard_channel_invalid")
    if (not isinstance(expected_named_runners,(tuple,list))
        or not 2<=len(expected_named_runners)<=18):
        raise SourceChainError("official_named_roster_reference_required")
    if any(not isinstance(x,(tuple,list)) or len(x)!=3 or
           type(x[2]) is not str or not x[2].strip()
           for x in expected_named_runners):
        raise SourceChainError("official_named_roster_invalid")
    reference=tuple(tuple(x) for x in expected_named_runners)
    if tuple((x[0],x[1]) for x in reference)!=tuple(active_runners):
        raise SourceChainError("official_numbered_roster_reference_mismatch")
    race_date=f"{spec.race_day[:4]}-{spec.race_day[4:6]}-{spec.race_day[6:]}"
    frozen={"race_date":race_date,"race_number":spec.race_number,
            "roster_verified":True,
            "runners":[{"horse_number":n,"frame_number":f,"horse_name":name}
                       for n,f,name in reference]}
    observed={channel:{"raw":original,"sha256":sha256(original).hexdigest(),
                       "captured_utc":captured_at_utc}}
    try:
        audited=reconcile_saved_racecards(
            observed,frozen,meeting_date=race_date,race=spec.race_number,
            cutoff_utc=verified_start_utc,observed_utc=observed_utc)
    except (ValueError,TypeError,KeyError) as exc:
        raise SourceChainError("existing_racecard_reconciler_rejected:"+str(exc)) from exc
    status=audited["sources"][channel]["status"]
    if status!="MATCH":
        raise SourceChainError("official_racecard_three_column_mismatch:"+status)
    # The SP parser does not itself verify the meeting header. Guard that
    # channel against a different race sharing the same numbered roster.
    if channel=="SP":
        soup=BeautifulSoup(original.decode("cp932",errors="replace"),"html.parser")
        visible=soup.get_text(" ",strip=True)
        d=date.fromisoformat(race_date)
        if (not re.search(fr"{d.year}年\s*{d.month}月\s*{d.day}日",visible)
            or not re.search(fr"(?<!\d)0?{spec.race_number}\s*(?:R|レース)(?!\d)",visible)
            or "京都" not in visible):
            raise SourceChainError("sp_racecard_date_race_venue_not_proven")
    return {"count":audited["runner_count"],"channel":channel,
            "roster_source_sha256":sha256(original).hexdigest(),
            "race_id":spec.race_id,
            "reused_reconciler":"reconcile_saved_racecards",
            "source_only":True}


def exact_odds_action(raw,channel):
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    values=set()
    for a in soup.select("a"):
        if a.get_text(" ",strip=True)!="オッズ":continue
        match=ACTION.search(a.get("onclick",""))
        if match:values.add(match.group(2))
    if len(values)!=1:raise SourceChainError("odds_navigation_ambiguous_or_missing")
    token=next(iter(values))
    if (channel=="PC")!=(token.startswith("pw")) or not re.fullmatch(r"[A-Za-z0-9]+/[A-Za-z0-9]+",token):
        raise SourceChainError("unverified_navigation_token")
    return token

def observed_next_market_action(raw, channel, spec, *, step):
    """Choose exactly one real official market-navigation action from HTML.

    0: Kyoto meeting with the expected published calendar day.
    1: exact race number. Never manufacture or modify a CNAME.
    This is deliberately conservative; unsupported menu layouts fail closed.
    """
    if step not in (0, 1) or channel not in ("PC", "SP"):
        raise SourceChainError("unsupported_market_navigation_step")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    visible=soup.get_text(" ",strip=True)
    d=date.fromisoformat(spec.race_day[:4]+"-"+spec.race_day[4:6]+"-"+spec.race_day[6:])
    calendar=(f"{d.year}年{d.month}月{d.day}日",f"{d.month}月{d.day}日")
    if not any(x in visible for x in calendar):
        raise SourceChainError("market_navigation_day_not_visible")
    if "最終オッズ" in visible or "オッズは未発表" in visible:
        raise SourceChainError("market_navigation_not_live")
    candidates=set()
    for link in soup.select("a"):
        label=link.get_text(" ",strip=True)
        action=ACTION.search(link.get("onclick",""))
        if not action:continue
        token=action.group(2)
        if not re.fullmatch(r"[A-Za-z0-9]+/[A-Za-z0-9]+",token):
            continue
        if not token.startswith("pw" if channel=="PC" else "sw"):
            continue
        if step==0:
            # A footer saying "Kyoto Racecourse" is NOT the target meeting.
            matched=("京都" in label and
                     (any(day in label for day in calendar) or spec.race_day in token))
        else:
            matched=bool(re.search(fr"(?<!\d)0?{spec.race_number}(?:\s*R|\s*レース)(?!\d)",label))
            # Race number alone is shared by every venue. Require a Kyoto
            # label or a published date+race-bound token, not page footer text.
            matched=matched and ("京都" in label or
                                 f"{spec.race_number:02d}{spec.race_day}" in token)
        if matched:
            candidates.add(token)
    if len(candidates)!=1:
        raise SourceChainError("observed_market_navigation_link_missing_or_ambiguous")
    return next(iter(candidates))

def http_fetch(opener,channel,path,*,cname=None,referer=None,pacer=None):
    host="jra.jp" if channel=="PC" else "sp.jra.jp"
    u=urlsplit(path)
    if (u.scheme!="https" or u.hostname!=host or u.port is not None
        or u.username or u.password or u.fragment
        or u.path not in ("/JRADB/accessD.html","/JRADB/accessO.html")
        or (cname is not None and (u.query or u.path!="/JRADB/accessO.html"))):
        raise SourceChainError("invalid_target_origin")
    method="GET" if cname is None else "POST"
    headers={"User-Agent":"Mozilla/5.0" if channel=="PC" else MOBILE_UA,"Accept":"text/html"}
    if referer:headers["Referer"]=referer
    if cname is not None:headers["Content-Type"]="application/x-www-form-urlencoded"
    post_body=None if cname is None else urlencode({"cname":cname}).encode("ascii")
    request=Request(path,data=post_body,
                    headers=headers,method=method)
    if pacer is not None:pacer.before_request()
    with opener.open(request,timeout=20) as response:
        data=response.read(LIMIT+1);status=response.status
        ct=response.headers.get("Content-Type","")
        final=urlsplit(response.geturl())
    received_at=datetime.now(timezone.utc).isoformat()
    if (status!=200 or not 0<len(data)<=LIMIT or "html" not in ct.lower()
        or final.scheme!="https" or final.hostname!=host or final.path!=u.path
        or final.query!=u.query or final.fragment or final.port is not None):
        raise SourceChainError("official_http_response_invalid")
    return {"raw":data,"sha256":sha256(data).hexdigest(),"bytes":len(data),
            "captured_at_utc":received_at,"http_status":status,"method":method,
            "requested_url":path,"response_url":response.geturl(),
            "observed_action_token":cname,
            "post_body_sha256":sha256(post_body).hexdigest() if post_body is not None else None,
            "post_body_size":len(post_body) if post_body is not None else 0}


def prepare_empty_original_directory(folder):
    """Reject reusing an existing source or receipt; no HTTP if nonempty."""
    folder=Path(folder)
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        raise SourceChainError("source_output_path_not_a_directory")
    if folder.exists() and any(folder.iterdir()):
        raise SourceChainError("source_output_contains_existing_evidence")
    folder.mkdir(parents=True,exist_ok=True)
    return folder


def persist_original_once(folder, name, original, receipt):
    """Persist exact response bytes exclusively and verify their disk SHA."""
    target=folder/name
    if type(original) is not bytes or not original:
        raise SourceChainError("source_original_bytes_required")
    if not isinstance(receipt,dict) or receipt.get("sha256")!=sha256(original).hexdigest():
        raise SourceChainError("source_original_receipt_hash_disagrees")
    try:
        with target.open("xb") as out:
            out.write(original)
    except FileExistsError as exc:
        raise SourceChainError("source_original_already_exists") from exc
    if sha256(target.read_bytes()).hexdigest()!=receipt["sha256"]:
        raise SourceChainError("source_written_bytes_digest_conflict")
    return target


def persist_receipt_once(folder,name,receipt):
    """Write one immutable JSON evidence receipt; no later rewrite."""
    if not isinstance(receipt,dict):
        raise SourceChainError("source_receipt_invalid")
    serialized=json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    try:
        with (folder/name).open("x",encoding="utf-8") as out:
            out.write(serialized)
    except FileExistsError as exc:
        raise SourceChainError("source_receipt_already_exists") from exc

def capture(out,*,channel,verified_start_utc,active_runners,now_utc=None,opener=None,
            race_spec=None,authorized_live_http=False,pacer=None,
            expected_named_runners=None,auto_repair_broken_pc_link=False):
    spec=(race_spec or DEFAULT_RACE_SPEC).validate(require_channels=(channel,))
    folder=prepare_empty_original_directory(out)
    start=aware_utc(verified_start_utc)
    if start.astimezone(ZoneInfo('Asia/Tokyo')).date().strftime('%Y%m%d')!=spec.race_day:
        raise SourceChainError('verified_start_day_does_not_match_race_spec')
    if not 2<=len(active_runners)<=18 or len({x[0] for x in active_runners})!=len(active_runners):
        raise SourceChainError('independent_active_roster_required')
    now=aware_utc(now_utc) if now_utc else datetime.now(timezone.utc)
    result={"schema_version":"jra_one_shot_market_capture.v1","race_id":spec.race_id,
        "channel":channel,"started_at_utc":now.isoformat(),
        "verified_start_utc":start.isoformat(),"state":"STARTED",
        "request_receipts":[],"pre_race_prices_accepted":False,
        "prediction_ready":False,"training_ready":False}
    if channel not in ("PC","SP"):raise SourceChainError("invalid_channel")
    if now<aware_utc(spec.normal_sales_open_utc):
        result["state"]="WAIT_FOR_OFFICIAL_SALES"
        persist_receipt_once(folder,"receipt.json",result)
        return result
    if now>=start-timedelta(minutes=10):
        result["state"]="CUTOFF_PASSED_NO_HTTP"
        persist_receipt_once(folder,"receipt.json",result)
        return result
    if authorized_live_http and pacer is None:
        pacer=RequestPacer()
    if opener is None:
        if not authorized_live_http:
            result["state"]="LIVE_HTTP_NOT_AUTHORIZED"
            persist_receipt_once(folder,"receipt.json",result)
            return result
        opener=build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
    source=spec.pc_racecard_url if channel=="PC" else spec.sp_racecard_url
    host="jra.jp" if channel=="PC" else "sp.jra.jp"
    try:
        try:
            racecard=http_fetch(opener,channel,source,pacer=pacer)
        except Exception as broken:
            # Strict opt-in: only an HTTP 404/410 on the PC racecard link
            # may trigger a bounded official-page rediscovery. Never repair
            # on redirect, 403, content/identity conflict, or network timeout.
            from urllib.error import HTTPError
            eligible=(auto_repair_broken_pc_link is True and
                      authorized_live_http is True and channel=="PC" and
                      isinstance(broken,HTTPError) and broken.code in (404,410))
            if not eligible:
                if isinstance(broken,HTTPError) and broken.code in (404,410):
                    result["link_repair"]={"state":"BROKEN_NOT_REPAIRED",
                                           "original_http_status":broken.code}
                    result["operator_alert"]={"severity":"ERROR",
                        "code":"JRA_RACECARD_LINK_BROKEN",
                        "message":"JRA公式出馬表リンク切れ。自動切替を行わず取得停止しました。"}
                raise
            result["operator_alert"]={"severity":"WARNING",
                "code":"JRA_RACECARD_LINK_BROKEN_REPAIR_ATTEMPT",
                "message":"JRA公式出馬表リンク切れを検知。公式リンクを検証付きで再探索しています。"}
            from diagnostics.jra_official_link_repair import repair_pc_racecard
            def verified_fetch(url):
                if datetime.now(timezone.utc)>=start-timedelta(minutes=10):
                    raise SourceChainError("cutoff_reached_during_link_repair")
                return http_fetch(opener,"PC",url,pacer=pacer)
            def retain_repair(name,page):
                persist_original_once(folder,name,page["raw"],page)
                result["request_receipts"].append({
                    "step":name,**{k:v for k,v in page.items() if k!="raw"}})
            def verify_repaired(raw,changed,captured):
                return verify_live_racecard_roster(
                    raw,"PC",changed,active_runners,expected_named_runners,
                    captured_at_utc=captured,
                    observed_utc=datetime.now(timezone.utc).isoformat(),
                    verified_start_utc=start.isoformat())
            try:
                spec,racecard,repair_receipt=repair_pc_racecard(
                    spec,fetch=verified_fetch,retain=retain_repair,
                    verify=verify_repaired)
            except Exception as repair_error:
                result["link_repair"]={
                    "state":"FAILED_CLOSED", "original_http_status":broken.code,
                    "error":type(repair_error).__name__+":"+str(repair_error)[:160]}
                result["operator_alert"]={"severity":"ERROR",
                    "code":"JRA_LINK_REPAIR_FAILED",
                    "message":"公式リンクの自動修復に失敗。未検証URLへ切り替えず安全停止しました。"}
                raise SourceChainError("official_link_repair_failed") from repair_error
            result["link_repair"]=repair_receipt
            # Preserve a *separate*, immutable verified candidate spec for
            # the next manual diagnostic; never rewrite approved source files
            # or silently promote links to the production configuration.
            from dataclasses import asdict
            persist_receipt_once(folder,"verified_repaired_race_spec.json",{
                "schema":"jra_verified_repaired_race_spec.v1",
                "race_spec":asdict(spec),
                "repair_receipt":repair_receipt,
                "promotion_state":"SOURCE_ONLY_NOT_PRODUCTION",
            })
            result["operator_alert"]={"severity":"INFO",
                "code":"JRA_LINK_REPAIRED_VERIFIED",
                "message":"JRA公式リンクを再発見し出馬表を照合しました。修復証拠を記録しました。"}
            source=spec.pc_racecard_url
        persist_original_once(folder,"official_racecard.html",racecard["raw"],racecard)
        result["request_receipts"].append({"step":"racecard",**{k:v for k,v in racecard.items() if k!="raw"}})
        if authorized_live_http:
            result["current_racecard_roster_proof"]=verify_live_racecard_roster(
                racecard["raw"],channel,spec,active_runners,expected_named_runners,
                captured_at_utc=racecard["captured_at_utc"],
                observed_utc=datetime.now(timezone.utc).isoformat(),
                verified_start_utc=start.isoformat())
        token=exact_odds_action(racecard["raw"],channel)
        menu_url=f"https://{host}/JRADB/accessO.html"
        menu=http_fetch(opener,channel,menu_url,cname=token,referer=source,pacer=pacer)
        persist_original_once(folder,"official_odds_menu.html",menu["raw"],menu)
        result["request_receipts"].append({"step":"odds_menu",**{k:v for k,v in menu.items() if k!="raw"}})
        text=BeautifulSoup(menu["raw"].decode("cp932",errors="replace"),"html.parser").get_text(" ",strip=True)
        if "今週のオッズは未発表です" in text or "オッズは未発表" in text:
            result["state"]="OFFICIAL_NOT_PUBLISHED"
            return result
        if "最終オッズ" in text:
            result["state"]="REJECT_FINAL_ODDS"
            return result
        # Previous workflow stopped at the generic "odds meeting selection".
        # Traverse at most TWO explicitly observed menu actions. Each page
        # is persisted and time-stamped BEFORE attempting another action.
        seen_tokens={token}
        for navigation_step in range(3):
            try:
                markets=find_market_links(menu["raw"],expected_race_day=spec.race_day,
                    expected_race_number=spec.race_number,expected_host=host)
                break
            except MarketNavigationError:
                if navigation_step>=2:
                    result["state"]="OFFICIAL_MENU_NEEDS_RACE_NAVIGATION"
                    return result
                try:
                    next_token=observed_next_market_action(menu["raw"],channel,spec,
                                                            step=navigation_step)
                except SourceChainError as exc:
                    result["state"]="OFFICIAL_MENU_NEEDS_RACE_NAVIGATION"
                    result["navigation_reason"]=str(exc)
                    return result
                if next_token in seen_tokens:
                    raise SourceChainError("market_navigation_cycle")
                seen_tokens.add(next_token)
                if datetime.now(timezone.utc)>=start-timedelta(minutes=10):
                    raise SourceChainError("cutoff_reached_during_navigation")
                menu=http_fetch(opener,channel,menu_url,cname=next_token,referer=menu_url,pacer=pacer)
                persist_original_once(folder,f"official_odds_navigation_{navigation_step+1}.html",menu["raw"],menu)
                result["request_receipts"].append({
                    "step":f"odds_navigation_{navigation_step+1}",
                    **{k:v for k,v in menu.items() if k!="raw"}})
                text=BeautifulSoup(menu["raw"].decode("cp932",errors="replace"),
                                   "html.parser").get_text(" ",strip=True)
                if "最終オッズ" in text:
                    result["state"]="REJECT_FINAL_ODDS"
                    return result
                if "オッズは未発表" in text:
                    result["state"]="OFFICIAL_NOT_PUBLISHED"
                    return result
        market_originals={};urls={};times={}
        for market in ("quinella","bracket_quinella"):
            record=markets["markets"][market]
            link=record["cname"]
            url=record["official_post_url"]
            if datetime.now(timezone.utc)>=start-timedelta(minutes=10):
                raise SourceChainError("cutoff_reached_during_acquisition")
            page=http_fetch(opener,channel,url,cname=link,referer=menu_url,pacer=pacer)
            market_originals[market]=page["raw"]
            urls[market]=url
            times[market]=page["captured_at_utc"]
            persist_original_once(folder,f"{market}_original.html",page["raw"],page)
            result["request_receipts"].append({"step":market,**{k:v for k,v in page.items() if k!="raw"}})
        chain=audit_source_originals(menu["raw"],market_originals,urls,
          race_key=spec.race_id,race_day=spec.race_day,venue=spec.venue,race_number=spec.race_number,
          channel=channel,captured_at_utc=menu["captured_at_utc"],
          verified_start_utc=start.isoformat(),active_runners=active_runners,
          market_captured_at_utc=times,
          archive_directory=folder/"frozen_source")
        result["market_receipt"]=chain
        result["pre_race_prices_accepted"]=chain["classification"]=="VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED"
        result["state"]="SOURCE_FROZEN" if result["pre_race_prices_accepted"] else "MARKETS_FAILED_VALIDATION"
    except Exception as exc:
        result["state"]="CAPTURE_BLOCKED"
        result["reason"]=type(exc).__name__+":"+str(exc)[:230]
    finally:
        result["ended_at_utc"]=datetime.now(timezone.utc).isoformat()
        persist_receipt_once(folder,"receipt.json",result)
    return result
def capture_hybrid(out, *, primary_channel, verified_start_utc, active_runners,
                   race_spec, authorized_live_http=False, now_utc=None,
                   openers=None, capture_fn=None, expected_named_runners=None,
                   independent_crosscheck=False):
    """Use the existing official PC/SP capturer; try other source once on error.

    Source-only diagnostic: never allows wagers, prediction promotion or
    automatic URL invention. Both URLs in race_spec must be independently
    observed. Primary failure remains in its own directory. Publication,
    cutoff, permission and final-odds refusals are terminal, not fallback
    triggers. Distinct data from two channels are never merged by guesswork.
    """
    spec=race_spec.validate()
    route_basis={"selection":"EXPLICIT","sampled_benchmark":False}
    if primary_channel=="AUTO":
        # Do not re-benchmark the public site. Replay the already accepted
        # 2026-11-06 actual PC/SP 5-race evidence via its existing validator.
        from diagnostics.jra_benchmark_acceptance import audit_report, REPORT, _read
        try:
            measured=audit_report(_read(REPORT))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SourceChainError("historical_route_evidence_unverified") from exc
        primary_channel=measured.get("router_candidate")
        if measured.get("router_state")!="CANDIDATE" or primary_channel not in ("PC","SP"):
            raise SourceChainError("historical_route_candidate_not_accepted")
        route_basis={"selection":"HISTORICAL_MEASURED_CANDIDATE_ONLY",
                     "sampled_benchmark":True,
                     "source_sample_day":measured["date"],
                     "sampled_races":measured["sampled_races"],
                     "sp_bytes_reduction_pct":measured["sp_bytes_reduction_pct"],
                     "sp_end_to_end_gain_pct":measured["sp_end_to_end_gain_pct"]}
    if primary_channel not in ("PC", "SP"):
        raise SourceChainError("invalid_primary_channel")
    if type(authorized_live_http) is not bool:
        raise SourceChainError("explicit_boolean_authorization_required")
    if type(independent_crosscheck) is not bool:
        raise SourceChainError("crosscheck_boolean_required")
    if openers is not None and (type(openers) is not dict or
                                set(openers) - {"PC", "SP"}):
        raise SourceChainError("invalid_channel_openers")
    folder=Path(out)
    if folder.exists() and any(folder.iterdir()):
        raise SourceChainError("hybrid_run_directory_not_empty")
    folder.mkdir(parents=True, exist_ok=True)
    runner=capture_fn or capture
    shared_pacer=RequestPacer() if authorized_live_http else None
    outcomes=[]
    def one(channel):
        channel_dir=folder / channel.lower()
        args=dict(channel=channel, verified_start_utc=verified_start_utc,
                  active_runners=active_runners, race_spec=spec,
                  authorized_live_http=authorized_live_http,
                  now_utc=now_utc)
        if capture_fn is None:
            args["expected_named_runners"]=expected_named_runners
        if shared_pacer is not None and capture_fn is None:
            args["pacer"]=shared_pacer
        if openers is not None:
            args["opener"]=openers.get(channel)
        try:
            result=runner(channel_dir, **args)
            if type(result) is not dict:
                raise SourceChainError("invalid_channel_receipt")
            state=result.get("state")
            if result.get("race_id") != spec.race_id or result.get("channel") != channel:
                raise SourceChainError("channel_race_identity_conflict")
            if state=="SOURCE_FROZEN" and not result.get("pre_race_prices_accepted"):
                raise SourceChainError("false_source_validation")
            return dict(channel=channel, state=state,
                        accepted=state=="SOURCE_FROZEN",
                        reason=result.get("reason"),
                        receipt_path=str(channel_dir/"receipt.json"))
        except Exception as exc:
            return dict(channel=channel,state="CAPTURE_EXCEPTION",accepted=False,
                        reason=type(exc).__name__+":"+str(exc)[:160],
                        receipt_path=str(channel_dir/"receipt.json"))
    first=one(primary_channel)
    outcomes.append(first)
    # Do not turn publication/permission/cutoff refusals into a second GET.
    fallback_allowed={"CAPTURE_BLOCKED",
                      "OFFICIAL_MENU_NEEDS_RACE_NAVIGATION",
                      "MARKETS_FAILED_VALIDATION"}
    selected=primary_channel if first["accepted"] else None
    other="SP" if primary_channel=="PC" else "PC"
    # Do not camouflage a wrong identity, source-content contradiction or
    # unsafe market phase as a normal transient-channel failure.
    terminal_conflicts=(
        "official_racecard_three_column_mismatch",
        "official_numbered_roster_reference_mismatch",
        "sp_racecard_date_race_venue_not_proven",
        "existing_racecard_reconciler_rejected",
        "official_named_roster_reference_required",
        "conflicting_market_phases",
        "market_navigation_cycle",
        "racecard_original_invalid",
        "official_market_identity_conflict",
        "cutoff_reached_during",
        "source_not_before_cutoff",
        "final_or_unpublished_original",
    )
    unsafe_primary=any(x in (first.get("reason") or "") for x in terminal_conflicts)
    if not selected and first["state"] in fallback_allowed and not unsafe_primary:
        second=one(other)
        outcomes.append(second)
        if second["accepted"]:
            selected=other
    elif selected and independent_crosscheck:
        # Explicit diagnostic only. Each channel preserves separate originals,
        # individual UTC times and its own validated roster/market receipts.
        # Different-time market prices must NEVER be merged or called parity.
        outcomes.append(one(other))
    dual_captured=(len(outcomes)==2 and all(x["accepted"] for x in outcomes))
    receipt=dict(schema="jra_pc_sp_one_shot_failover.v1",
                 race_id=spec.race_id, primary_channel=primary_channel,
                 route_basis=route_basis,
                 selected_channel=selected, attempts=outcomes,
                 independent_crosscheck_requested=independent_crosscheck,
                 primary_semantic_conflict_blocked=unsafe_primary,
                 dual_independent_source_originals=dual_captured,
                 cross_time_odds_comparison_authorized=False,
                 market_value_parity_verified=False,
                 state=("DUAL_SOURCES_CAPTURED_PRICE_PARITY_UNVERIFIED" if dual_captured
                        else "SOURCE_ONLY_PRIMARY" if selected==primary_channel
                        else "SOURCE_ONLY_FALLBACK" if selected else "SAFE_STOP"),
                 prediction_ready=False, training_ready=False,
                 paper_trade_authorized=False,
                 actual_wager_authorized=False)
    (folder/"hybrid_receipt.json").write_text(json.dumps(
        receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return receipt

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    p.add_argument("--channel",choices=["PC","SP","AUTO"],default="PC")
    p.add_argument("--hybrid",action="store_true",help="One conditional cross-channel fallback")
    p.add_argument("--independent-crosscheck",action="store_true",help="Explicitly capture other official channel for independent original evidence; no price-time merge")
    p.add_argument("--verified-start-utc",required=True)
    p.add_argument("--active-roster-json",required=True)
    p.add_argument("--race-spec-json",help="Independently observed official navigation and race identity; no HTTP authorization")
    p.add_argument('--authorized-live-http', action='store_true',
        help='Explicit diagnostic read-only opt-in; never a production authorization')
    p.add_argument('--auto-repair-broken-pc-link',action='store_true',
        help='Optional 404/410-only official PC link recovery; no guessed URLs')
    args=p.parse_args()
    if args.channel=="AUTO" and not args.hybrid:
        p.error("--channel AUTO requires --hybrid")
    if args.independent_crosscheck and not args.hybrid:
        p.error("--independent-crosscheck requires --hybrid")
    if args.authorized_live_http and not args.race_spec_json:
        p.error('--authorized-live-http requires independently observed --race-spec-json')
    channels=("PC","SP") if args.hybrid else (args.channel,)
    spec=(ObservedRaceSpec(**json.loads(Path(args.race_spec_json).read_text(encoding="utf8"))).validate(
             require_channels=channels)
          if args.race_spec_json else DEFAULT_RACE_SPEC.validate(require_channels=channels))
    roster=json.loads(Path(args.active_roster_json).read_text(encoding="utf8"))
    rows=verified_roster_from_snapshot(roster,spec,race_start_utc=args.verified_start_utc)
    named_rows=tuple((r["horse_number"],r["frame_number"],r["horse_name"]) for r in roster["runners"])
    runner=capture_hybrid if args.hybrid else capture
    options=dict(verified_start_utc=args.verified_start_utc,active_runners=rows,
                 expected_named_runners=named_rows,
                 race_spec=spec,authorized_live_http=args.authorized_live_http)
    if args.hybrid:
        if args.auto_repair_broken_pc_link:
            p.error("--auto-repair-broken-pc-link requires single-channel capture")
        options["independent_crosscheck"]=args.independent_crosscheck
    else:
        options["auto_repair_broken_pc_link"]=args.auto_repair_broken_pc_link
    options["primary_channel" if args.hybrid else "channel"]=args.channel
    print(json.dumps(runner(args.out,**options),ensure_ascii=False,indent=2))
