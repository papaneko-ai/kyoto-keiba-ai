"""SP original collection from independently saved official SP navigation.

This adapter deliberately does not synthesize SP CNAME tokens from PC values.
It reuses the existing SP navigation parser and bounded official transport.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
from diagnostics.jra_pc_sp_benchmark import observed_sp_race_links_from_saved_navigation
from diagnostics.jra_one_shot_market_capture import http_fetch, RequestPacer, LIMIT

class SPSourceError(ValueError):
    pass

def capture_observed_sp(out, *, navigation_original, navigation_url, race_day,
                        navigation_captured_utc, race_number, opener,
                        pacer=None):
    """Collect one SP racecard through a *saved* official SP navigation anchor.

    Navigation is provided by the official SP navigation capture stage, not
    guessed by substituting PC CNAME or fabricated race identifiers.
    """
    if type(navigation_original) is not bytes or not 0 < len(navigation_original) <= LIMIT:
        raise SPSourceError("sp_navigation_original_missing")
    if type(race_number) is not int or not 1 <= race_number <= 12:
        raise SPSourceError("sp_race_number_invalid")
    try:
        nav_time=datetime.fromisoformat(navigation_captured_utc.replace("Z","+00:00"))
        if nav_time.utcoffset()!=timezone.utc.utcoffset(None):
            raise ValueError("not utc")
        links=observed_sp_race_links_from_saved_navigation(
            navigation_original, source_url=navigation_url,
            source_sha256=sha256(navigation_original).hexdigest(),
            race_day=race_day)
    except (ValueError,TypeError,AttributeError) as exc:
        raise SPSourceError("sp_navigation_provenance_invalid") from exc
    candidates=[x for x in links["race_links"] if x["race_number"]==race_number]
    if len(candidates)!=1:
        raise SPSourceError("sp_race_link_not_independently_observed")
    root=Path(out)
    if root.is_symlink() or root.exists() or not root.parent.is_dir():
        raise SPSourceError("sp_capture_directory_existing_or_invalid")
    root.mkdir()
    raw_path=root/"official_sp_navigation.html"
    raw_path.write_bytes(navigation_original)
    receipt={"schema":"kyoto_sp_observed_original.v1", "channel":"SP",
             "day":race_day, "race_number":race_number,
             "navigation_source_url":navigation_url,
             "navigation_sha256":sha256(navigation_original).hexdigest(),
             "navigation_captured_at_utc":navigation_captured_utc,
             "racecard_url":candidates[0]["url"],
             "racecard_fetched":False, "market_verified":False,
             "pc_sp_parity_verified":False, "network_requests_started":1}
    try:
        page=http_fetch(opener, "SP", candidates[0]["url"],
                        pacer=pacer or RequestPacer(min_gap_seconds=2.0))
        (root/"official_sp_racecard.html").write_bytes(page["raw"])
        receipt.update(racecard_sha256=page["sha256"],
                       racecard_bytes=page["bytes"],
                       racecard_captured_at_utc=page["captured_at_utc"],
                       racecard_fetched=True)
        receipt["state"]="SP_ORIGINAL_CAPTURED_NOT_ROSTER_VERIFIED"
    except Exception as exc:
        receipt["state"]="SP_FETCH_FAILED_ORIGINAL_NAVIGATION_RETAINED"
        receipt["error_class"]=type(exc).__name__
    (root/"sp_receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
        encoding="utf8")
    return receipt

def capture_verified_sp_seed(originals, *, race_day, race_number, source_url,
                             opener, pacer=None):
    """Independently sourced official SP racecard, not a transformed PC URL.

    The seed must be observed outside the PC navigation chain (e.g. official
    SP search result). It is not evidence of a general future-day discovery
    mechanism. Saves raw bytes *before* testing the SP HTML structure.
    """
    from urllib.parse import urlsplit, parse_qs
    import re
    root=Path(originals)
    if not root.is_dir() or root.is_symlink():
        raise SPSourceError("shared_originals_missing")
    for name in ("official_sp_racecard.html","sp_receipt.json"):
        if (root/name).exists() or (root/name).is_symlink():
            raise SPSourceError("sp_original_already_exists")
    url=urlsplit(source_url)
    try:
        query=parse_qs(url.query,strict_parsing=True)
        token=query["CNAME"][0]
    except (KeyError,ValueError,IndexError):
        raise SPSourceError("sp_source_url_invalid")
    if (url.scheme!="https" or url.netloc!="sp.jra.jp"
        or url.path!="/JRADB/accessD.html" or url.fragment
        or set(query)!={"CNAME"} or len(query["CNAME"])!=1
        or not re.fullmatch(r"sw[A-Za-z0-9]+/[A-Za-z0-9]+",token)
        or race_day not in token or
        not re.search(rf"{race_number:02d}{race_day}",token)):
        raise SPSourceError("sp_source_url_unverified")
    receipt={"schema":"kyoto_sp_seed_capture.v1","channel":"SP",
             "day":race_day,"race_number":race_number,
             "observed_sp_source_url":source_url,
             "source_discovery":"INDEPENDENT_SP_OFFICIAL_RESULT",
             "network_requests_started":1,
             "racecard_fetched":False,"market_verified":False,
             "pc_sp_parity_verified":False}
    try:
        page=http_fetch(opener,"SP",source_url,
                        pacer=pacer or RequestPacer(min_gap_seconds=2.0))
        (root/"official_sp_racecard.html").write_bytes(page["raw"])
        receipt.update(state="SP_ORIGINAL_CAPTURED_NOT_ROSTER_VERIFIED",
                       racecard_fetched=True,
                       racecard_sha256=page["sha256"],
                       racecard_bytes=page["bytes"],
                       racecard_captured_at_utc=page["captured_at_utc"])
    except Exception as exc:
        receipt["state"]="SP_HTTP_FAILED"
        receipt["error_class"]=type(exc).__name__
    (root/"sp_receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\\n",
        encoding="utf8")
    return receipt


def compare_saved_pc_sp(originals, *, race_day):
    """Purely offline roster parity; equal horse number, frame, and name required."""
    from diagnostics.jra_pc_sp_benchmark import pc_rows,sp_rows
    root=Path(originals)
    pc=root/"official_racecard.html"
    sp=root/"official_sp_racecard.html"
    result={"schema":"kyoto_pc_sp_original_comparison.v1",
            "day":race_day,"PC":{"captured":pc.is_file()},
            "SP":{"captured":sp.is_file()},
            "full_roster_parity_verified":False,
            "channel_preference_certified":False}
    if not sp.is_file() or not pc.is_file():
        result["state"]="NEED_BOTH_ORIGINALS"
        return result
    try:
        receipt=json.loads((root/"receipt.json").read_text(encoding="utf8"))
        sp_receipt=json.loads((root/"sp_receipt.json").read_text(encoding="utf8"))
        race=receipt["racecard_number"]
        if (receipt.get("day")!=race_day or sp_receipt.get("day")!=race_day
            or sp_receipt.get("race_number")!=race
            or sha256(pc.read_bytes()).hexdigest()!=receipt.get("racecard_sha256")
            or sha256(sp.read_bytes()).hexdigest()!=sp_receipt.get("racecard_sha256")):
            raise ValueError("race_identity_or_digest_mismatch")
        result["race_number"]=race
        pc_parsed=pc_rows(pc.read_bytes(),race,
                          meeting_date=f"{race_day[:4]}-{race_day[4:6]}-{race_day[6:]}")
        sp_parsed=sp_rows(sp.read_bytes())
        result["PC"].update(captured=True,runner_count=len(pc_parsed),
                            sha256=receipt["racecard_sha256"])
        result["SP"].update(captured=True,runner_count=len(sp_parsed),
                            sha256=sp_receipt["racecard_sha256"])
        result["full_roster_parity_verified"]=pc_parsed==sp_parsed
        result["state"]=("ROSTER_PARITY_MATCH" if pc_parsed==sp_parsed
                         else "ROSTER_PARITY_MISMATCH")
    except (ValueError,KeyError,TypeError,OSError) as exc:
        result["state"]="ROSTER_COMPARISON_UNVERIFIED"
        result["error_class"]=type(exc).__name__
    return result
