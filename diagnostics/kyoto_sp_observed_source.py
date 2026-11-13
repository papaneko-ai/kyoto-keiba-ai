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
