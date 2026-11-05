"""Inspect one actual JRA odds link found in saved Kyoto 2026-10-31 results HTML.
No guessed links, no retries, no database writes, one POST maximum.
Final historical odds are not represented as pre-race snapshots.
"""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urljoin, urlsplit
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import re

ROOT = Path("jra_action_capture")
SOURCE = ROOT / "kyoto_all_results_20261031.html"
MAX_BYTES = 1500000

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.active = None
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.active = {"text": "", "onclick": dict(attrs).get("onclick", "") or ""}
    def handle_data(self, data):
        if self.active is not None:
            self.active["text"] += data
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.active is not None:
            self.active["text"] = " ".join(self.active["text"].split())
            self.items.append(self.active)
            self.active = None

def main():
    page = SOURCE.read_bytes().decode("cp932", errors="replace")
    reader = Links()
    reader.feed(page)
    selections = []
    for item in reader.items:
        if item["text"] != "オッズ":
            continue
        m = re.search(r"doAction\s*\(\s*'([^']+)'\s*,\s*'([^']+)'", item["onclick"])
        if not m:
            continue
        path, cname = m.groups()
        if path == "/JRADB/accessO.html" and "20261031" in cname and "pw151ou" in cname:
            selections.append((path, cname))
    summary = {
        "source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "number_of_historical_odds_links": len(selections),
        "status": "not_attempted",
        "historical_data_only": True,
    }
    if len(selections) < 1:
        summary["status"] = "no_historical_odds_link"
    else:
        path, cname = selections[0]
        url = urljoin("https://www.jra.go.jp/", path)
        if url != "https://www.jra.go.jp/JRADB/accessO.html":
            raise ValueError("Unexpected JRA odds endpoint")
        req = Request(
            url,
            data=urlencode({"cname": cname}).encode("ascii"),
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.jra.go.jp/keiba/",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=20) as resp:
                body = resp.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError("response_too_large")
                if urlsplit(resp.geturl()).hostname not in {"jra.go.jp", "www.jra.go.jp"}:
                    raise ValueError("unexpected_redirect")
                summary["http_status"] = resp.status
                summary["content_type"] = resp.headers.get("Content-Type", "")
                summary["final_path"] = urlsplit(resp.geturl()).path
            (ROOT / "kyoto_historical_odds_one.html").write_bytes(body)
            text = body.decode("cp932", errors="replace")
            reader2 = Links()
            reader2.feed(text)
            candidate_links = [
                {"label": i["text"], "onclick": i["onclick"][:190]}
                for i in reader2.items
                if any(term in i["text"] for term in ("馬連", "枠連", "オッズ", "1レース", "1R", "京都"))
                or ("doAction" in i["onclick"] and "/JRADB/accessO.html" in i["onclick"])
            ]
            summary.update(
                status="html_captured",
                body_bytes=len(body),
                body_sha256=sha256(body).hexdigest(),
                text_markers={k: text.count(k) for k in ("馬連", "枠連", "オッズ", "京都", "最終")},
                links=candidate_links[:65],
                links_count=len(candidate_links),
            )
        except Exception as e:
            summary.update(status="failed", error=type(e).__name__ + ": " + str(e)[:140])
    (ROOT / "kyoto_historical_odds_probe.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("HISTORICAL_ODDS_PROBE", json.dumps(summary, ensure_ascii=False)[:19000])

if __name__ == "__main__":
    main()
