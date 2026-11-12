"""Offline, original-bound handoff from the Nov14 JRA one-shot selection.

Never requests a page, guesses CNAME, or certifies racecards, markets or bets.
The only meeting URL is derived from the exact immutable official HTML bytes.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qs
import json
import re

from diagnostics.kyoto_p1_nov14_official_one_shot_nav import (
    SOURCE, EXPECTED_DAY, MIN_DISCOVERY_UTC, MAX_DISCOVERY_UTC,
    strict_link_from_official,
)

class HandoffRejected(ValueError):
    pass

def _utc(text):
    if not isinstance(text, str):
        raise HandoffRejected("capture_clock_missing")
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HandoffRejected("capture_clock_invalid") from exc
    if when.tzinfo is None or when.utcoffset() is None:
        raise HandoffRejected("capture_clock_naive")
    return when.astimezone(timezone.utc)

def assess_saved_selection(folder):
    """Classify a saved one-shot source, separately from live market acceptance."""
    root=Path(folder)
    if root.is_symlink() or not root.is_dir():
        raise HandoffRejected("original_evidence_directory_invalid")
    rp=root/"receipt.json"
    if rp.is_symlink() or not rp.is_file():
        raise HandoffRejected("one_shot_receipt_missing")
    try:
        receipt=json.loads(rp.read_text(encoding="utf8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise HandoffRejected("one_shot_receipt_unreadable") from exc
    if (type(receipt) is not dict
        or receipt.get("schema")!="kyoto_jra_20261114_kyoto_navigation_one_off.v1"
        or receipt.get("origin")!="JRA_OFFICIAL_PC_SELECTION"
        or receipt.get("source_url")!=SOURCE
        or type(receipt.get("attempted_GET")) is not int
        or receipt["attempted_GET"] not in (0,1)):
        raise HandoffRejected("one_shot_receipt_identity_conflict")
    status=receipt.get("status")
    original=root/"official_selection.html"
    if receipt["attempted_GET"]==0:
        if original.exists() or original.is_symlink() or status not in (
            "WAIT_FOR_JRA_OFFICIAL_PUBLICATION_NO_HTTP",
            "STALE_MEETING_DISCOVERY_NO_HTTP",
            "LIVE_HTTP_NOT_EXPLICITLY_AUTHORIZED",
        ):
            raise HandoffRejected("zero_http_original_or_status_conflict")
        return {"schema":"kyoto_official_meeting_handoff.v1",
                "state":"NO_OFFICIAL_ORIGINAL_SAFE_STOP",
                "one_shot_status":status,"official_meeting_url":None,
                "racecard_verified":False,"prerace_markets_verified":False,
                "network_requests":0}
    if status=="FAILED_CLOSED":
        if original.exists() or original.is_symlink():
            raise HandoffRejected("failed_capture_contains_unverified_original")
        return {"schema":"kyoto_official_meeting_handoff.v1",
                "state":"FAILED_OFFICIAL_CAPTURE_SAFE_STOP",
                "one_shot_status":status,"official_meeting_url":None,
                "racecard_verified":False,"prerace_markets_verified":False,
                "network_requests":0}
    if status not in ("OFFICIAL_NOV14_KYOTO_MEETING_LINK_OBSERVED","NOT_YET_VISIBLE"):
        raise HandoffRejected("unsupported_one_shot_state")
    if original.is_symlink() or not original.is_file():
        raise HandoffRejected("one_shot_original_missing")
    raw=original.read_bytes()
    digest=sha256(raw).hexdigest()
    if (receipt.get("source_sha256")!=digest
        or receipt.get("source_bytes")!=len(raw)):
        raise HandoffRejected("original_bytes_receipt_digest_conflict")
    started=_utc(receipt.get("started_utc"))
    completed=_utc(receipt.get("completed_utc"))
    if not MIN_DISCOVERY_UTC<=started<MAX_DISCOVERY_UTC or completed<started:
        raise HandoffRejected("capture_window_unverified")
    parsed=strict_link_from_official(raw)
    if (parsed["status"]!=status
        or parsed["observed_links"]!=receipt.get("observed_links")
        or receipt.get("current_meeting_racecards_verified") is not False
        or receipt.get("current_prerace_market_verified") is not False
        or receipt.get("paper_trade_authorized") is not False):
        raise HandoffRejected("one_shot_claims_disagree_with_original")
    if status=="NOT_YET_VISIBLE":
        return {"schema":"kyoto_official_meeting_handoff.v1",
                "state":"OFFICIAL_LINK_NOT_YET_PUBLISHED_SAFE_STOP",
                "one_shot_status":status,"official_meeting_url":None,
                "selection_sha256":digest,
                "racecard_verified":False,"prerace_markets_verified":False,
                "network_requests":0}
    links=parsed["observed_links"]
    if len(links)!=1:
        raise HandoffRejected("unique_observed_meeting_link_required")
    link=links[0]
    url=urljoin(SOURCE,link["href"])
    u=urlsplit(url)
    q=parse_qs(u.query)
    if (u.scheme!="https" or u.hostname!="jra.jp" or u.port is not None
        or u.username or u.password or u.fragment or u.path!="/JRADB/accessD.html"
        or set(q)!={"CNAME"} or len(q["CNAME"])!=1
        or EXPECTED_DAY not in q["CNAME"][0]
        or not re.fullmatch(r"pw[A-Za-z0-9]+/[A-Za-z0-9]+",q["CNAME"][0])):
        raise HandoffRejected("observed_official_meeting_url_invalid")
    return {"schema":"kyoto_official_meeting_handoff.v1",
            "state":"OFFICIAL_MEETING_LINK_OBSERVED_NOT_RACECARD",
            "one_shot_status":status,
            "official_meeting_url":url,
            "official_meeting_label":link["label"],
            "source_url":SOURCE,
            "selection_sha256":digest,
            "receipt_sha256":sha256(rp.read_bytes()).hexdigest(),
            "observed_meeting_token_sha256":link["source_observed_token_sha256"],
            "capture_completed_utc":completed.isoformat(),
            "racecard_verified":False,"prerace_markets_verified":False,
            "network_requests":0,
            "source_provenance":"SAVED_ONE_SHOT_JRA_PC_HTML_ONLY"}

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-directory",required=True)
    p.add_argument("--out",required=True)
    opts=p.parse_args(argv)
    result=assess_saved_selection(opts.source_directory)
    dest=Path(opts.out)
    if dest.is_symlink() or not dest.parent.is_dir():
        raise HandoffRejected("unsafe_output_path")
    encoded=json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n"
    with dest.open("x",encoding="utf8") as output:
        output.write(encoded)
    print("NOV14_OFFICIAL_SOURCE_HANDOFF="+result["state"])
    print("REAL_RACECARD_VERIFIED=FALSE")
    print("REAL_PRERACE_MARKETS_VERIFIED=FALSE")
    return result

if __name__=="__main__":
    main()
