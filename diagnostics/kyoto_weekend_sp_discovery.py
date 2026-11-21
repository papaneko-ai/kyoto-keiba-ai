"""Independent SP official navigation discovery; zero guessed CNAME tokens.

The only seed URL is the public SP homepage; further requests require an
actual saved <a href> from that exact host. An unknown navigation graph is
recorded as INCOMPLETE, never a synthetic SP racecard claim.
"""
from __future__ import annotations
import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, build_opener

from bs4 import BeautifulSoup
from diagnostics.jra_one_shot_market_capture import RequestPacer
from diagnostics.kyoto_p1_nov14_official_one_shot_nav import NoRedirect

SEED = "https://sp.jra.jp/"
# JRA SP actual Kyoto R1 2026-11-22 official URL independently observed.
# This is a single navigation seed, NOT synthesized race URLs or 12R proof.
OFFICIAL_OBSERVED_NOV22_R1 = (
    "https://sp.jra.jp/JRADB/accessD.html?"
    "CNAME=sw01dde0108202605060120261122%2F90"
)
LIMIT = 1_500_000

class SPDiscoveryError(ValueError):
    pass

def official_sp_anchors(raw, parent, day):
    """Return exact official HTML hrefs, not generated navigation strings."""
    if not isinstance(raw,bytes) or not 0<len(raw)<=LIMIT:
        raise SPDiscoveryError("invalid_sp_navigation_original")
    if not isinstance(day,str) or not re.fullmatch(r"20[0-9]{6}",day):
        raise SPDiscoveryError("invalid_sp_day")
    try:
        decoded=raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded=raw.decode("cp932",errors="replace")
    soup=BeautifulSoup(decoded,"html.parser")
    choices=[]
    for a in soup.select("a[href]"):
        href=a.get("href","").strip()
        if not href or href.startswith(("javascript:","#")):
            continue
        url=urljoin(parent,href)
        u=urlsplit(url)
        if (u.scheme!="https" or u.hostname!="sp.jra.jp" or u.port is not None
            or u.username or u.password or u.fragment
            or u.path!="/JRADB/accessD.html"):
            continue
        try:
            q=parse_qs(u.query,strict_parsing=True)
        except ValueError:
            continue
        if set(q)!={"CNAME"} or len(q["CNAME"])!=1:
            continue
        token=q["CNAME"][0]
        if not re.fullmatch(r"sw[A-Za-z0-9]+/[A-Za-z0-9]+",token):
            continue
        label=" ".join(a.get_text(" ",strip=True).split())
        choices.append((url,label,token))
    return choices

def observed_kyoto_race_candidates(raw, parent, day):
    """Inventory *observed* Kyoto 1-12R SP anchors; no URL construction.

    These are navigation hints, not fetched/verified racecards, odds or
    PC/SP parity. Exact date/race must appear in both token and visible label.
    """
    candidates={str(i):[] for i in range(1,13)}
    for url,label,token in official_sp_anchors(raw,parent,day):
        # Published JRA mobile token: prefix, Kyoto venue 08,
        # meeting(8 digits), race(2 digits), day, opaque verified suffix.
        # Unlike the obsolete "raceNNYYYYMMDD" test token, this pattern
        # is derived from observed official SP racecard URLs.
        match=re.fullmatch(
            r"sw01dde01(08)[0-9]{8}(0[1-9]|1[0-2])"
            +re.escape(day)+r"/[A-Za-z0-9]+",token,re.I)
        if not match:
            continue
        race=int(match.group(2))
        if not re.search(rf"(?<![0-9])0?{race}\\s*(R|レース)(?![0-9])",label,re.I):
            continue
        if url not in candidates[str(race)]:
            candidates[str(race)].append(url)
    return candidates


def discover(root, *, day, opener=None, pacer=None):
    """At most 3 Saturday or 6 Sunday no-redirect SP HTML GETs.

    This is deliberately independent of the PC selector and tokens.
    Every successful GET is saved byte-for-byte with SHA256 and UTC.
    """
    root=Path(root)
    if root.exists() or root.is_symlink() or not root.parent.is_dir():
        raise SPDiscoveryError("discovery_root_not_fresh")
    if day not in ("20261121","20261122"):
        raise SPDiscoveryError("discovery_day_invalid")
    root.mkdir()
    client=opener or build_opener(NoRedirect())
    throttle=pacer or RequestPacer(min_gap_seconds=2.0)
    # An actual official Sunday R1 document was independently observed.
    # Download it directly and derive all other race URLs exclusively from
    # saved official page anchor bytes; no guessed CNAME or PC-derived URL.
    queue=[SEED,OFFICIAL_OBSERVED_NOV22_R1] if day=="20261122" else [SEED]
    visited=set()
    log=[]
    matched=set()
    race_candidates={str(i):set() for i in range(1,13)}
    # Sunday is a predeclared, separately testable route fallback.
    # All requests still follow genuine saved official SP anchors; never
    # synthesize URLs or retry already visited pages.
    max_steps=3 if day=="20261121" else 6
    for step in range(max_steps):
        if not queue:
            break
        url=queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        throttle.before_request()
        stamp=datetime.now(timezone.utc).isoformat()
        request=Request(url,method="GET",headers={
            "Accept":"text/html","User-Agent":"KyotoRaceAI-Private-ReadOnly/0.1"})
        try:
            with client.open(request,timeout=12) as response:
                raw=response.read(LIMIT+1)
                status=response.status
                actual=response.geturl()
                ctype=response.headers.get("Content-Type","")
        except Exception as exc:
            log.append({"url":url,"request_started_at_utc":stamp,
                        "error_class":type(exc).__name__})
            break
        if status!=200 or actual!=url or "html" not in ctype.lower() or not 0<len(raw)<=LIMIT:
            log.append({"url":url,"request_started_at_utc":stamp,
                        "state":"HTTP_RESPONSE_REJECTED"})
            break
        name=f"official_sp_discovery_{step+1}.html"
        (root/name).write_bytes(raw)
        digest=hashlib.sha256(raw).hexdigest()
        log.append({"url":url,"captured_at_utc":datetime.now(timezone.utc).isoformat(),
                    "sha256":digest,"bytes":len(raw),"file":name})
        anchors=official_sp_anchors(raw,url,day)
        # Record every independently observed Kyoto race anchor, including
        # ambiguous races, without fetching or certifying it.
        for number,urls in observed_kyoto_race_candidates(raw,url,day).items():
            race_candidates[number].update(urls)
        for target,label,token in anchors:
            if day in token and f"12{day}" in token and bool(re.search(r"(?<![0-9])12\s*(R|レース)",label,re.I)) and "京都" in label:
                matched.add(target)
        if matched:
            break
        # Enqueue only on-page SP official selections; no URL synthesis.
        # An ambiguous candidate is not automatically visited.
        nav=[u for u,l,t in anchors if (day in t and ("京都" in l or "出馬表" in l or "開催" in l))]
        if day=="20261121":
            if len(set(nav))==1:
                target=nav[0]
                if target not in visited and target not in queue:
                    queue.append(target)
        else:
            # The Sunday fallback explores bounded *observed* alternatives,
            # retaining loop protection and never constructing a CNAME.
            for target in sorted(set(nav)):
                if target not in visited and target not in queue and len(queue)<5:
                    queue.append(target)
    result={"schema":"kyoto_weekend_sp_independent_discovery.v1",
            "day":day,"seed":SEED,"attempts":log,
            "racecard_url":next(iter(matched)) if len(matched)==1 else "",
            "unique_observed_racecard":len(matched)==1,
            "per_race_observed_navigation_candidates":{
                str(i):{"candidate_count":len(race_candidates[str(i)]),
                         "candidate_urls":sorted(race_candidates[str(i)]),
                         "state":("UNIQUE_OFFICIAL_SP_NAVIGATION_HINT_NOT_FETCHED"
                                  if len(race_candidates[str(i)])==1
                                  else "AMBIGUOUS_OFFICIAL_SP_NAVIGATION_HINT_NOT_FETCHED"
                                  if len(race_candidates[str(i)])>1
                                  else "NO_OFFICIAL_SP_RACE_LINK_OBSERVED")}
                for i in range(1,13)},
            "full_twelve_race_sp_fallback_verified":False,
            "observed_link_is_not_authenticated_racecard":True,
            "network_requests_started":len(log),
            "state":"OBSERVED_UNIQUE_R12_SOURCE" if len(matched)==1
                    else "OFFICIAL_R12_LINK_NOT_OBSERVED",
            "source_only":True,"not_pc_derived":True,
            "prediction_ready":False}
    import json
    (root/"sp_discovery_receipt.json").write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    return result
