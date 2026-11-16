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
LIMIT = 1_500_000

class SPDiscoveryError(ValueError):
    pass

def official_sp_anchors(raw, parent, day):
    """Return exact official HTML hrefs, not generated navigation strings."""
    if not isinstance(raw,bytes) or not 0<len(raw)<=LIMIT:
        raise SPDiscoveryError("invalid_sp_navigation_original")
    if not isinstance(day,str) or not re.fullmatch(r"20[0-9]{6}",day):
        raise SPDiscoveryError("invalid_sp_day")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
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

def discover(root, *, day, opener=None, pacer=None):
    """At most 3 paced, no-redirect official SP HTML GETs (incl. homepage).

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
    queue=[SEED]
    visited=set()
    log=[]
    matched=set()
    for step in range(3):
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
        for target,label,token in anchors:
            if day in token and f"12{day}" in token and bool(re.search(r"(?<![0-9])12\s*(R|レース)",label,re.I)) and "京都" in (label+" "+raw.decode("cp932",errors="replace")):
                matched.add(target)
        if matched:
            break
        # Enqueue only on-page SP official selections; no URL synthesis.
        # An ambiguous candidate is not automatically visited.
        nav=[u for u,l,t in anchors if (day in t and ("京都" in l or "出馬表" in l or "開催" in l))]
        if len(set(nav))==1:
            target=nav[0]
            if target not in visited:
                queue.append(target)
    result={"schema":"kyoto_weekend_sp_independent_discovery.v1",
            "day":day,"seed":SEED,"attempts":log,
            "racecard_url":next(iter(matched)) if len(matched)==1 else "",
            "unique_observed_racecard":len(matched)==1,
            "network_requests_started":len(log),
            "state":"OBSERVED_UNIQUE_R12_SOURCE" if len(matched)==1
                    else "OFFICIAL_R12_LINK_NOT_OBSERVED",
            "source_only":True,"not_pc_derived":True,
            "prediction_ready":False}
    import json
    (root/"sp_discovery_receipt.json").write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    return result
