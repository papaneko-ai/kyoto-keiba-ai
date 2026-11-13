"""Nov15 independent observed-link collection, with bounded zero-guess GETs.

Two requests maximum: JRA PC selection then link actually present in
the selection original. All bytes stay in volatile workflow workspace until
encrypted; never claim racecard or market authenticity from a meeting link.
"""
from __future__ import annotations
import hashlib,json
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
    try:
        raw.decode("cp932",errors="strict")
    except UnicodeError as exc:
        raise ObservationRejected("html_encoding_invalid") from exc
    return raw

def observe(selection_root, *, now_utc, opener=None, allowed=False):
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
             "both_markets_verified":False,"paper_trade_authorized":False}
    client=opener if opener is not None else build_opener(NoRedirect())
    try:
        receipt["http_requests_started"]=1
        selection=_read(client,SOURCE)
        (root/"official_selection.html").write_bytes(selection)
        receipt["selection_sha256"]=hashlib.sha256(selection).hexdigest()
        receipt["selection_bytes"]=len(selection)
        meeting_url,meeting_label=_parse_kyoto(selection,SOURCE)
        receipt["observed_meeting_url"]=meeting_url
        receipt["meeting_label"]=meeting_label
        receipt["http_requests_started"]=2
        meeting=_read(client,meeting_url)
        (root/"official_meeting.html").write_bytes(meeting)
        receipt["meeting_sha256"]=hashlib.sha256(meeting).hexdigest()
        receipt["meeting_bytes"]=len(meeting)
        # This is a link observation, not a prerace market, independent roster
        # or correctness proof for the content supplied by JRA.
        receipt["state"]="NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD"
    except Exception as exc:
        receipt["state"]="FAILED_CLOSED"
        receipt["error_class"]=type(exc).__name__
        receipt["error_code"]=str(exc)[:160]
    finally:
        (root/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,
                                                      sort_keys=True,indent=2)+"\n",encoding="utf8")
    return receipt

def accept_observation(folder):
    root=Path(folder)
    try:
        receipt=json.loads((root/"receipt.json").read_text(encoding="utf8"))
    except (OSError,ValueError) as exc:
        raise ObservationRejected("receipt_missing") from exc
    if receipt.get("state")!="NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD":
        raise ObservationRejected("observation_not_successful")
    for filename,prefix in (("official_selection.html","selection"),
                            ("official_meeting.html","meeting")):
        path=root/filename
        if path.is_symlink() or not path.is_file():
            raise ObservationRejected("observed_original_missing")
        raw=path.read_bytes()
        if not 0<len(raw)<=LIMIT or hashlib.sha256(raw).hexdigest()!=receipt.get(prefix+"_sha256") or len(raw)!=receipt.get(prefix+"_bytes"):
            raise ObservationRejected("observed_original_digest_mismatch")
    return {"state":"TWO_ORIGINALS_MATCH_RECEIPT_ONLY",
            "day":DAY,"http_requests_started":receipt["http_requests_started"],
            "racecard_verified":False,"market_verified":False,
            "source_authenticated_independently":False}
