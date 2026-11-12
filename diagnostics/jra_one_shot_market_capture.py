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
import argparse,json,re
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

    def validate(self):
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

def http_fetch(opener,channel,path,*,cname=None,referer=None):
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
    request=Request(path,data=None if cname is None else urlencode({"cname":cname}).encode("ascii"),
                    headers=headers,method=method)
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
            "captured_at_utc":received_at,"http_status":status,"method":method}

def capture(out,*,channel,verified_start_utc,active_runners,now_utc=None,opener=None,
            race_spec=None,authorized_live_http=False):
    spec=(race_spec or DEFAULT_RACE_SPEC).validate()
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
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
        (folder/"receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        return result
    if now>=start-timedelta(minutes=10):
        result["state"]="CUTOFF_PASSED_NO_HTTP"
        (folder/"receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        return result
    if opener is None:
        if not authorized_live_http:
            result["state"]="LIVE_HTTP_NOT_AUTHORIZED"
            (folder/"receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\\n",encoding="utf8")
            return result
        opener=build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
    source=spec.pc_racecard_url if channel=="PC" else spec.sp_racecard_url
    host="jra.jp" if channel=="PC" else "sp.jra.jp"
    try:
        racecard=http_fetch(opener,channel,source)
        (folder/"official_racecard.html").write_bytes(racecard["raw"])
        result["request_receipts"].append({"step":"racecard",**{k:v for k,v in racecard.items() if k!="raw"}})
        token=exact_odds_action(racecard["raw"],channel)
        menu_url=f"https://{host}/JRADB/accessO.html"
        menu=http_fetch(opener,channel,menu_url,cname=token,referer=source)
        (folder/"official_odds_menu.html").write_bytes(menu["raw"])
        result["request_receipts"].append({"step":"odds_menu",**{k:v for k,v in menu.items() if k!="raw"}})
        text=BeautifulSoup(menu["raw"].decode("cp932",errors="replace"),"html.parser").get_text(" ",strip=True)
        if "今週のオッズは未発表です" in text or "オッズは未発表" in text:
            result["state"]="OFFICIAL_NOT_PUBLISHED"
            return result
        if "最終オッズ" in text:
            result["state"]="REJECT_FINAL_ODDS"
            return result
        try:markets=find_market_links(menu["raw"],expected_race_day=spec.race_day,
                expected_race_number=spec.race_number,expected_host=host)
        except MarketNavigationError:
            # The current page may be a meeting-selection index. Do not
            # invent subsequent endpoints; require observed navigation.
            result["state"]="OFFICIAL_MENU_NEEDS_RACE_NAVIGATION"
            return result
        market_originals={};urls={};times={}
        for market in ("quinella","bracket_quinella"):
            record=markets["markets"][market]
            link=record["cname"]
            url=record["official_post_url"]
            if datetime.now(timezone.utc)>=start-timedelta(minutes=10):
                raise SourceChainError("cutoff_reached_during_acquisition")
            page=http_fetch(opener,channel,url,cname=link,referer=menu_url)
            market_originals[market]=page["raw"]
            urls[market]=url
            times[market]=page["captured_at_utc"]
            (folder/f"{market}_original.html").write_bytes(page["raw"])
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
        (folder/"receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return result
def capture_hybrid(out, *, primary_channel, verified_start_utc, active_runners,
                   race_spec, authorized_live_http=False, now_utc=None,
                   openers=None, capture_fn=None):
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
    if openers is not None and (type(openers) is not dict or
                                set(openers) - {"PC", "SP"}):
        raise SourceChainError("invalid_channel_openers")
    folder=Path(out)
    if folder.exists() and any(folder.iterdir()):
        raise SourceChainError("hybrid_run_directory_not_empty")
    folder.mkdir(parents=True, exist_ok=True)
    runner=capture_fn or capture
    outcomes=[]
    def one(channel):
        channel_dir=folder / channel.lower()
        args=dict(channel=channel, verified_start_utc=verified_start_utc,
                  active_runners=active_runners, race_spec=spec,
                  authorized_live_http=authorized_live_http,
                  now_utc=now_utc)
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
    if not selected and first["state"] in fallback_allowed:
        other="SP" if primary_channel=="PC" else "PC"
        second=one(other)
        outcomes.append(second)
        if second["accepted"]:
            selected=other
    receipt=dict(schema="jra_pc_sp_one_shot_failover.v1",
                 race_id=spec.race_id, primary_channel=primary_channel,
                 route_basis=route_basis,
                 selected_channel=selected, attempts=outcomes,
                 state=("SOURCE_ONLY_PRIMARY" if selected==primary_channel else
                        "SOURCE_ONLY_FALLBACK" if selected else "SAFE_STOP"),
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
    p.add_argument("--verified-start-utc",required=True)
    p.add_argument("--active-roster-json",required=True)
    p.add_argument("--race-spec-json",help="Independently observed official navigation and race identity; no HTTP authorization")
    p.add_argument('--authorized-live-http', action='store_true',
        help='Explicit diagnostic read-only opt-in; never a production authorization')
    args=p.parse_args()
    if args.channel=="AUTO" and not args.hybrid:
        p.error("--channel AUTO requires --hybrid")
    if args.authorized_live_http and not args.race_spec_json:
        p.error('--authorized-live-http requires independently observed --race-spec-json')
    roster=json.loads(Path(args.active_roster_json).read_text(encoding="utf8"))
    rows=tuple((int(r["horse_number"]),int(r["frame_number"])) for r in roster["runners"])
    spec=(ObservedRaceSpec(**json.loads(Path(args.race_spec_json).read_text(encoding="utf8"))).validate()
          if args.race_spec_json else DEFAULT_RACE_SPEC)
    runner=capture_hybrid if args.hybrid else capture
    options=dict(verified_start_utc=args.verified_start_utc,active_runners=rows,
                 race_spec=spec,authorized_live_http=args.authorized_live_http)
    options["primary_channel" if args.hybrid else "channel"]=args.channel
    print(json.dumps(runner(args.out,**options),ensure_ascii=False,indent=2))
