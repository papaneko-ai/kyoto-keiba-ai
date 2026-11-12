"""Bounded fail-closed recovery of a broken JRA PC racecard link.

Only observed anchors in two saved official pages may supply CNAME tokens.
This is *not* a general crawler, URL synthesizer, or permission to place bets.
"""
from dataclasses import replace
from hashlib import sha256
from urllib.parse import urljoin, urlsplit, parse_qs
import re
from bs4 import BeautifulSoup

OFFICIAL_ENTRY = "https://jra.jp/JRADB/accessD.html?CNAME=pw01dli00%2FF3"

class LinkRepairRejected(ValueError):
    pass

def observed_links(original, parent):
    """Return only fully checked JRA /JRADB/accessD.html anchors."""
    if type(original) is not bytes or not 0 < len(original) <= 1_500_000:
        raise LinkRepairRejected("invalid_official_original")
    soup = BeautifulSoup(original.decode("cp932", errors="replace"), "html.parser")
    result = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        url = urljoin(parent, href)
        target = urlsplit(url)
        try:
            q = parse_qs(target.query, strict_parsing=True)
        except ValueError:
            continue
        if (target.scheme != "https" or target.hostname != "jra.jp"
            or target.port is not None or target.username or target.password
            or target.path != "/JRADB/accessD.html" or target.fragment
            or set(q) != {"CNAME"} or len(q["CNAME"]) != 1
            or not re.fullmatch(r"pw[A-Za-z0-9]+/[A-Za-z0-9]+", q["CNAME"][0])):
            continue
        result.append((url, " ".join(anchor.get_text(" ", strip=True).split()), q["CNAME"][0]))
    return result

def unique_observed(original, parent, predicate):
    found = {url for url, label, token in observed_links(original, parent)
             if predicate(label, token)}
    if len(found) != 1:
        raise LinkRepairRejected("official_repair_link_missing_or_ambiguous")
    return next(iter(found))

def repair_pc_racecard(spec, *, fetch, retain, verify):
    """At most three official GETs: selection, meeting, proposed racecard.

    fetch(url) uses existing NoRedirect, host, byte, timeout and rate controls.
    retain(name, page) writes *immutable* originals and audit receipts.
    verify(raw, amended_spec, timestamp) independently checks exact roster.
    No candidate is accepted on a merely successful HTTP response.
    """
    day = spec.race_day
    if spec.venue != "京都" or not re.fullmatch(r"20\d{6}", day):
        raise LinkRepairRejected("unsupported_race_identity")
    selector = fetch(OFFICIAL_ENTRY)
    retain("repair_selection.html", selector)
    meeting = unique_observed(selector["raw"], OFFICIAL_ENTRY,
                              lambda label, token: "京都" in label and day in token)
    meeting_page = fetch(meeting)
    retain("repair_meeting.html", meeting_page)
    target_key = f"{spec.race_number:02d}{day}"
    racecard = unique_observed(
        meeting_page["raw"], meeting,
        lambda label, token: (
            target_key in token and bool(re.search(
                rf"(?<!\d)0?{spec.race_number}\s*(?:R|レース)(?!\d)", label))
        ))
    if racecard == spec.pc_racecard_url:
        raise LinkRepairRejected("original_link_still_published")
    amended = replace(spec, pc_racecard_url=racecard)
    amended.validate(require_channels=("PC",))
    page = fetch(racecard)
    retain("repair_candidate_racecard.html", page)
    proof = verify(page["raw"], amended, page["captured_at_utc"])
    if not isinstance(proof, dict) or proof.get("race_id") != spec.race_id:
        raise LinkRepairRejected("candidate_roster_not_verified")
    return amended, page, {
        "status": "REPAIRED_VERIFIED_PC_ONLY",
        "old_url": spec.pc_racecard_url,
        "new_url": racecard,
        "official_entry_url": OFFICIAL_ENTRY,
        "selection_sha256": sha256(selector["raw"]).hexdigest(),
        "meeting_sha256": sha256(meeting_page["raw"]).hexdigest(),
        "candidate_sha256": sha256(page["raw"]).hexdigest(),
        "race_id": spec.race_id,
        "proof": proof,
        "no_guessed_urls": True,
        "request_count": 3,
    }
