"""Nov15 independent observed-link collection, with bounded zero-guess GETs.

At most three paced requests: official selection, observed Kyoto meeting,
and (when linked) one racecard; optional fourth POST records its directly
observed odds menu action. All bytes stay in the
ephemeral workspace until encrypted; no roster or market authentication claim.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime, timezone
from urllib.request import Request,build_opener,HTTPCookieProcessor
from http.cookiejar import CookieJar
from pathlib import Path
from diagnostics.kyoto_p1_nov14_official_one_shot_nav import (
    SOURCE,LIMIT,NoRedirect
)
from diagnostics.jra_official_link_repair import observed_links, LinkRepairRejected
from diagnostics.jra_one_shot_market_capture import RequestPacer,exact_odds_action,http_fetch,SourceChainError
from diagnostics.jra_official_market_navigation import find_market_links, MarketNavigationError

DAY="20261115"
BEGIN=datetime(2026,11,12,7,15,tzinfo=timezone.utc)
END=datetime(2026,11,15,4,0,tzinfo=timezone.utc)

class ObservationRejected(ValueError): pass

def _parse_kyoto(original,source_url):
    try: options=observed_links(original,source_url)
    except (LinkRepairRejected,UnicodeError) as exc:
        raise ObservationRejected("official_anchor_parse_rejected") from exc
    found={(url,text) for url,text,token in options if DAY in token and "京都" in text}
    if len(found)!=1: raise ObservationRejected("day15_official_meeting_not_unique_or_missing")
    return next(iter(found))

def _read(opener, url):
    request=Request(url,method="GET",headers={
        "Accept":"text/html","User-Agent":"KyotoRaceAI-Private-ReadOnly/0.1"})
    with opener.open(request,timeout=12) as reply:
        status=reply.status;content_type=reply.headers.get("Content-Type","")
        location=reply.geturl();raw=reply.read(LIMIT+1)
    if (status!=200 or location!=url or "html" not in content_type.lower()
        or not 0<len(raw)<=LIMIT):
        raise ObservationRejected("unverified_http_response")
    # Preserve response bytes before checking text encoding or page structure.
    # The caller writes and hashes this raw original before parsing.
    return raw

def _validate_saved_html_encoding(raw):
    try:
        raw.decode("cp932",errors="strict")
    except UnicodeError as exc:
        raise ObservationRejected("html_encoding_invalid_after_original_preserved") from exc

def _single_observed_racecard(meeting_original, meeting_url):
    """Only actual racecard anchor, uniquely matched. Never synthesize a CNAME."""
    try:
        anchors=observed_links(meeting_original,meeting_url)
    except (LinkRepairRejected,UnicodeError) as exc:
        raise ObservationRejected("observed_racecard_links_invalid") from exc
    choices={}
    for url,label,token in anchors:
        if DAY not in token:
            continue
        match=re.search(r"(?<![0-9])(?:0?([1-9])|(1[0-2]))\s*(?:R|レース)(?![0-9])",label,re.IGNORECASE)
        if not match:
            continue
        race=int(match.group(1) or match.group(2))
        if f"{race:02d}{DAY}" not in token:
            continue
        choices.setdefault(race,set()).add(url)
    if not choices:
        return None
    # Prefer the latest numbered explicitly observed race; no start-time claim.
    race=max(choices)
    if len(choices[race])!=1:
        raise ObservationRejected("ambiguous_same_race_official_link")
    return race,next(iter(choices[race]))

def observe(selection_root, *, now_utc, opener=None, allowed=False,
            include_observed_racecard=False, include_observed_odds_menu=False, pacer=None):
    root=Path(selection_root)
    if root.is_symlink() or root.exists() or not root.parent.is_dir():
        raise ObservationRejected("one_shot_output_existing_or_invalid")
    current=datetime.fromisoformat(now_utc.replace("Z","+00:00"))
    if current.utcoffset()!=timezone.utc.utcoffset(None):
        raise ObservationRejected("clock_not_utc")
    if not BEGIN <= current < END:
        raise ObservationRejected("outside_observation_window_zero_http")
    if allowed is not True:
        raise ObservationRejected("live_http_not_explicitly_authorized")
    root.mkdir()
    receipt={"schema":"kyoto_nov15_observed_link_capture.v1",
             "day":DAY,"selection_source":SOURCE,"state":"STARTED",
             "http_requests_started":0,"real_racecard_verified":False,
             "both_markets_verified":False,"paper_trade_authorized":False,
             "racecard_original_fetched":False,"odds_menu_original_fetched":False,
             "market_requests_started":0,
             "started_at_utc":current.isoformat()}
    # Preserve official session cookies when following observed odds POST
    # actions, reusing the capturer's existing no-redirect transport policy.
    client=opener if opener is not None else build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
    # Reuse the established market-capture pacer across all bounded GETs.
    try:
        request_pacer=pacer if pacer is not None else RequestPacer(min_gap_seconds=2.0)
        if not callable(getattr(request_pacer,"before_request",None)):
            raise ObservationRejected("request_pacer_invalid")
        receipt["http_requests_started"]=1
        request_pacer.before_request()
        selection=_read(client,SOURCE)
        receipt["selection_captured_at_utc"]=datetime.now(timezone.utc).isoformat()
        (root/"official_selection.html").write_bytes(selection)
        receipt["selection_sha256"]=hashlib.sha256(selection).hexdigest()
        receipt["selection_bytes"]=len(selection)
        _validate_saved_html_encoding(selection)
        meeting_url,meeting_label=_parse_kyoto(selection,SOURCE)
        receipt["observed_meeting_url"]=meeting_url
        receipt["meeting_label"]=meeting_label
        receipt["http_requests_started"]=2
        request_pacer.before_request()
        meeting=_read(client,meeting_url)
        receipt["meeting_captured_at_utc"]=datetime.now(timezone.utc).isoformat()
        (root/"official_meeting.html").write_bytes(meeting)
        receipt["meeting_sha256"]=hashlib.sha256(meeting).hexdigest()
        receipt["meeting_bytes"]=len(meeting)
        _validate_saved_html_encoding(meeting)
        # Optional third request is restricted to an exact observed race URL.
        # This is raw source capture, never a roster/start/odds certification.
        if include_observed_racecard is True:
            observed=_single_observed_racecard(meeting,meeting_url)
            if observed is None:
                receipt["racecard_observation"]="NOT_IN_OFFICIAL_MEETING_ORIGINAL"
            else:
                race_number,race_url=observed
                receipt["racecard_number"]=race_number
                receipt["observed_racecard_url"]=race_url
                receipt["http_requests_started"]=3
                request_pacer.before_request()
                racecard=_read(client,race_url)
                receipt["racecard_captured_at_utc"]=datetime.now(timezone.utc).isoformat()
                (root/"official_racecard.html").write_bytes(racecard)
                receipt["racecard_sha256"]=hashlib.sha256(racecard).hexdigest()
                receipt["racecard_bytes"]=len(racecard)
                receipt["racecard_original_fetched"]=True
                _validate_saved_html_encoding(racecard)
                receipt["racecard_observation"]="ORIGINAL_BYTES_CAPTURED_NOT_ROSTER_AUTHENTICATED"
                # The fourth request is allowed only when the racecard itself
                # contains exactly one official odds POST action. This is
                # raw menu evidence, NOT a certified pre-race price matrix.
                if include_observed_odds_menu is True:
                    try:
                        token=exact_odds_action(racecard,"PC")
                    except SourceChainError as exc:
                        receipt["odds_menu_observation"]="NO_UNIQUE_OFFICIAL_ACTION"
                        receipt["odds_menu_error"]=type(exc).__name__
                    else:
                        receipt["http_requests_started"]=4
                        try:
                            # Reuse existing POST, no redirect, host, size,
                            # SHA256 and shared 2-second pacing.
                            page=http_fetch(
                                client,"PC","https://jra.jp/JRADB/accessO.html",
                                cname=token,referer=race_url,pacer=request_pacer)
                            menu=page["raw"]
                            (root/"official_odds_menu.html").write_bytes(menu)
                            receipt["odds_menu_sha256"]=page["sha256"]
                            receipt["odds_menu_bytes"]=page["bytes"]
                            receipt["odds_menu_captured_at_utc"]=page["captured_at_utc"]
                            receipt["odds_menu_action"]=token
                            receipt["odds_menu_original_fetched"]=True
                            _validate_saved_html_encoding(menu)
                            receipt["odds_menu_observation"]="RAW_OFFICIAL_MENU_NOT_PRICE_VALIDATED"
                            # Only independently identified, direct official
                            # 馬連/枠連 links from this exact menu may be used.
                            # No navigation guesses, no extra GETs or retry.
                            try:
                                links=find_market_links(
                                    menu,expected_race_day=DAY,
                                    expected_race_number=race_number,
                                    expected_host="jra.jp")
                            except MarketNavigationError:
                                receipt["market_observation"]="OFFICIAL_MARKET_LINKS_NOT_PRESENT_IN_MENU"
                            else:
                                if (links["source_final_odds_detected"] or
                                    "オッズは未発表" in menu.decode("cp932",errors="replace")):
                                    receipt["market_observation"]="FINAL_OR_UNPUBLISHED_NO_MORE_HTTP"
                                else:
                                    receipt["market_observation"]="OFFICIAL_MARKET_LINKS_SEEN"
                                    for market in ("quinella","bracket_quinella"):
                                        rec=links["markets"][market]
                                        if receipt["http_requests_started"]>=6:
                                            break
                                        receipt["http_requests_started"]+=1
                                        receipt["market_requests_started"]+=1
                                        try:
                                            page=http_fetch(
                                                client,"PC",rec["official_post_url"],
                                                cname=rec["cname"],
                                                referer="https://jra.jp/JRADB/accessO.html",
                                                pacer=request_pacer)
                                            raw_market=page["raw"]
                                            name="official_"+market+"_odds.html"
                                            (root/name).write_bytes(raw_market)
                                            receipt[market+"_sha256"]=page["sha256"]
                                            receipt[market+"_bytes"]=page["bytes"]
                                            receipt[market+"_captured_at_utc"]=page["captured_at_utc"]
                                            receipt[market+"_action"]=rec["cname"]
                                            receipt[market+"_original_fetched"]=True
                                            _validate_saved_html_encoding(raw_market)
                                        except Exception as market_error:
                                            receipt[market+"_original_fetched"]=False
                                            receipt[market+"_error_class"]=type(market_error).__name__
                                            # Keep already acquired original files.
                                            break

                        except Exception as exc:
                            receipt["odds_menu_observation"]="POST_FAILED_PRESERVE_RACECARD"
                            receipt["odds_menu_error"]=type(exc).__name__
                            # Retain PC original rather than treating a
                            # failed odds menu as lost source data.
        # This is a link observation, not a prerace market, independent roster
        # or correctness proof for the content supplied by JRA.
        receipt["state"]=("NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED"
                          if receipt["racecard_original_fetched"] else
                          "NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD")
    except Exception as exc:
        receipt["state"]="FAILED_CLOSED"
        receipt["error_class"]=type(exc).__name__
        receipt["error_code"]=str(exc)[:160]
    finally:
        receipt["ended_at_utc"]=datetime.now(timezone.utc).isoformat()
        (root/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,
                                                      sort_keys=True,indent=2)+"\n",encoding="utf8")
    return receipt

def accept_observation(folder):
    root=Path(folder)
    try:
        receipt=json.loads((root/"receipt.json").read_text(encoding="utf8"))
    except (OSError,ValueError) as exc:
        raise ObservationRejected("receipt_missing") from exc
    if receipt.get("state") not in ("NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD",
                                   "NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED"):
        raise ObservationRejected("observation_not_successful")
    # Reject forged market/roster success and impossible HTTP accounting. 
    # A saved PC-only observation cannot certify independent SP or markets.
    if any(receipt.get(flag, False) is not False for flag in (
        "real_racecard_verified", "both_markets_verified", "paper_trade_authorized")):
        raise ObservationRejected("unverified_success_claim_in_observation")
    has_menu=receipt.get("odds_menu_original_fetched") is True
    menu_attempted=receipt.get("odds_menu_observation") in (
        "RAW_OFFICIAL_MENU_NOT_PRICE_VALIDATED",
        "POST_FAILED_PRESERVE_RACECARD")
    expected_requests=((4+receipt.get("market_requests_started",0))
                       if menu_attempted else 3
                       if receipt.get("racecard_original_fetched") is True else 2)
    if (type(receipt.get("market_requests_started",0)) is not int
        or not 0<=receipt.get("market_requests_started",0)<=2
        or (not has_menu and receipt.get("market_requests_started",0)!=0)):
        raise ObservationRejected("market_request_accounting_invalid")
    if type(receipt.get("http_requests_started")) is not int or (
        receipt["http_requests_started"] != expected_requests):
        raise ObservationRejected("observation_http_count_inconsistent")
    for filename,prefix in (("official_selection.html","selection"),
                            ("official_meeting.html","meeting")):
        path=root/filename
        if path.is_symlink() or not path.is_file():
            raise ObservationRejected("observed_original_missing")
        raw=path.read_bytes()
        if not 0<len(raw)<=LIMIT or hashlib.sha256(raw).hexdigest()!=receipt.get(prefix+"_sha256") or len(raw)!=receipt.get(prefix+"_bytes"):
            raise ObservationRejected("observed_original_digest_mismatch")
    # Verify the actual selection-to-meeting provenance chain, not merely
    # separately hashed originals paired with a claimed meeting URL.
    if receipt.get("selection_source")!=SOURCE or receipt.get("day")!=DAY:
        raise ObservationRejected("selection_source_or_date_invalid")
    try:
        observed_meeting_url,observed_meeting_label=_parse_kyoto(
            (root/"official_selection.html").read_bytes(),SOURCE)
    except ObservationRejected as exc:
        raise ObservationRejected("selection_meeting_original_link_invalid") from exc
    if (receipt.get("observed_meeting_url")!=observed_meeting_url or
        receipt.get("meeting_label")!=observed_meeting_label):
        raise ObservationRejected("meeting_url_or_label_not_in_selection_original")
    has_racecard=receipt.get("racecard_original_fetched")
    expected_state=("NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED"
                    if has_racecard is True else "NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD")
    # A third original is evidence only when the capture receipt includes
    # a UTC timestamp for that exact HTTP response.
    # Independently check provenance of the two mandatory saved originals.
    # These timestamps must be parseable UTC instants, not merely present.
    for field in ("selection_captured_at_utc", "meeting_captured_at_utc"):
        stamp=receipt.get(field)
        try:
            parsed=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        except (AttributeError,TypeError,ValueError) as exc:
            raise ObservationRejected("mandatory_original_capture_timestamp_missing") from exc
        if parsed.utcoffset()!=timezone.utc.utcoffset(None):
            raise ObservationRejected("mandatory_original_capture_timestamp_not_utc")
    if has_racecard is True:
        captured_at=receipt.get("racecard_captured_at_utc")
        try:
            captured_time=datetime.fromisoformat(captured_at.replace("Z","+00:00"))
        except (AttributeError,TypeError,ValueError) as exc:
            raise ObservationRejected("racecard_capture_timestamp_missing") from exc
        if captured_time.utcoffset()!=timezone.utc.utcoffset(None):
            raise ObservationRejected("racecard_capture_timestamp_not_utc")
    if type(has_racecard) is not bool or receipt.get("state")!=expected_state:
        raise ObservationRejected("observed_state_and_originals_inconsistent")
    if has_racecard is False and (root/"official_racecard.html").exists():
        raise ObservationRejected("unexpected_unclaimed_racecard_original")
    if has_racecard is False and any(k in receipt for k in (
        "racecard_sha256","racecard_bytes","observed_racecard_url","racecard_number")):
        raise ObservationRejected("unclaimed_racecard_metadata_present")
    if has_racecard is True:
        racecard=root/"official_racecard.html"
        if racecard.is_symlink() or not racecard.is_file():
            raise ObservationRejected("racecard_original_missing")
        raw=racecard.read_bytes()
        if not 0<len(raw)<=LIMIT or hashlib.sha256(raw).hexdigest()!=receipt.get("racecard_sha256") or len(raw)!=receipt.get("racecard_bytes"):
            raise ObservationRejected("racecard_original_digest_mismatch")
        observed=_single_observed_racecard((root/"official_meeting.html").read_bytes(),
                                         receipt["observed_meeting_url"])
        if observed != (receipt.get("racecard_number"),receipt.get("observed_racecard_url")):
            raise ObservationRejected("racecard_anchor_not_bound")
    if has_menu:
        p=root/"official_odds_menu.html"
        if p.is_symlink() or not p.is_file():
            raise ObservationRejected("odds_menu_original_missing")
        raw=p.read_bytes()
        if (not 0<len(raw)<=LIMIT
            or hashlib.sha256(raw).hexdigest()!=receipt.get("odds_menu_sha256")
            or len(raw)!=receipt.get("odds_menu_bytes")):
            raise ObservationRejected("odds_menu_original_digest_mismatch")
        try:
            from diagnostics.jra_one_shot_market_capture import exact_odds_action
            observed_token=exact_odds_action(
                (root/"official_racecard.html").read_bytes(),"PC")
        except SourceChainError as exc:
            raise ObservationRejected("odds_menu_action_not_in_racecard") from exc
        if observed_token!=receipt.get("odds_menu_action"):
            raise ObservationRejected("odds_menu_action_not_bound")
        try:
            stamp=datetime.fromisoformat(receipt["odds_menu_captured_at_utc"].replace("Z","+00:00"))
        except (ValueError,TypeError,KeyError) as exc:
            raise ObservationRejected("odds_menu_timestamp_invalid") from exc
        if stamp.utcoffset()!=timezone.utc.utcoffset(None):
            raise ObservationRejected("odds_menu_timestamp_not_utc")
    elif (root/"official_odds_menu.html").exists() or any(k in receipt for k in (
        "odds_menu_sha256","odds_menu_bytes","odds_menu_captured_at_utc",
        "odds_menu_action")):
        raise ObservationRejected("unclaimed_odds_menu_original")
    if has_menu:
        try:
            observed_market_links=find_market_links(
                (root/"official_odds_menu.html").read_bytes(),
                expected_race_day=DAY,
                expected_race_number=receipt["racecard_number"],
                expected_host="jra.jp")
        except (MarketNavigationError,KeyError):
            observed_market_links=None
        for market in ("quinella","bracket_quinella"):
            name="official_"+market+"_odds.html"
            p=root/name
            if receipt.get(market+"_original_fetched") is True:
                if observed_market_links is None or market not in observed_market_links["markets"]:
                    raise ObservationRejected("market_action_not_original_observed")
                if receipt.get(market+"_action")!=observed_market_links["markets"][market]["cname"]:
                    raise ObservationRejected("market_action_mismatch")
                if p.is_symlink() or not p.is_file():
                    raise ObservationRejected("market_original_missing")
                raw=p.read_bytes()
                if (not 0<len(raw)<=LIMIT
                    or hashlib.sha256(raw).hexdigest()!=receipt.get(market+"_sha256")
                    or len(raw)!=receipt.get(market+"_bytes")):
                    raise ObservationRejected("market_original_digest_mismatch")
                try:
                    stamp=datetime.fromisoformat(
                        receipt[market+"_captured_at_utc"].replace("Z","+00:00"))
                except (ValueError,TypeError,KeyError) as exc:
                    raise ObservationRejected("market_capture_timestamp_invalid") from exc
                if stamp.utcoffset()!=timezone.utc.utcoffset(None):
                    raise ObservationRejected("market_capture_timestamp_not_utc")
            elif p.exists() or any(k in receipt for k in (
                market+"_sha256",market+"_bytes",market+"_captured_at_utc",market+"_action")):
                raise ObservationRejected("unclaimed_market_original")
    return {"state":"TWO_ORIGINALS_MATCH_RECEIPT_ONLY",
            "day":DAY,"http_requests_started":receipt["http_requests_started"],
            "racecard_verified":False,"market_verified":False,
            "source_authenticated_independently":False}
