"""Nov15 independent observed-link collection, with bounded zero-guess GETs.

Two requests maximum: JRA PC selection then link actually present in
the selection original. All bytes stay in volatile workflow workspace until
encrypted; never claim racecard or market authenticity from a meeting link.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime, timezone
from urllib.request import Request,build_opener
from pathlib import Path
from diagnostics.kyoto_p1_nov14_official_one_shot_nav import (
    SOURCE,LIMIT,NoRedirect
)
from diagnostics.jra_official_link_repair import observed_links, LinkRepairRejected

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
        match=re.search(r"(?<![0-9])0?([1-9]|1[0-2])\s*(?:R|レース)(?![0-9])",label,re.IGNORECASE)
        if not match:
            continue
        race=int(match.group(1))
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
            include_observed_racecard=False):
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
             "racecard_original_fetched":False,
             "started_at_utc":current.isoformat()}
    client=opener if opener is not None else build_opener(NoRedirect())
    try:
        receipt["http_requests_started"]=1
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
                racecard=_read(client,race_url)
                receipt["racecard_captured_at_utc"]=datetime.now(timezone.utc).isoformat()
                (root/"official_racecard.html").write_bytes(racecard)
                receipt["racecard_sha256"]=hashlib.sha256(racecard).hexdigest()
                receipt["racecard_bytes"]=len(racecard)
                receipt["racecard_original_fetched"]=True
                _validate_saved_html_encoding(racecard)
                receipt["racecard_observation"]="ORIGINAL_BYTES_CAPTURED_NOT_ROSTER_AUTHENTICATED"
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
    for filename,prefix in (("official_selection.html","selection"),
                            ("official_meeting.html","meeting")):
        path=root/filename
        if path.is_symlink() or not path.is_file():
            raise ObservationRejected("observed_original_missing")
        raw=path.read_bytes()
        if not 0<len(raw)<=LIMIT or hashlib.sha256(raw).hexdigest()!=receipt.get(prefix+"_sha256") or len(raw)!=receipt.get(prefix+"_bytes"):
            raise ObservationRejected("observed_original_digest_mismatch")
    if receipt.get("racecard_original_fetched") is True:
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
    return {"state":"TWO_ORIGINALS_MATCH_RECEIPT_ONLY",
            "day":DAY,"http_requests_started":receipt["http_requests_started"],
            "racecard_verified":False,"market_verified":False,
            "source_authenticated_independently":False}
