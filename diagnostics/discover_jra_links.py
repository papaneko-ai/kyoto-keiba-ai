"""Identify JRA page navigation from live official HTML.
Restricted to two GET requests, same-origin HTML links, no automation bypass.
"""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from pathlib import Path
import json
import re
from datetime import datetime, timezone

OUT = Path("jra_link_discovery")
PAGES = ["https://www.jra.go.jp/", "https://www.jra.go.jp/keiba/"]
KEYWORDS = ("オッズ", "出馬", "レース結果", "払戻", "馬場", "調教", "競走馬", "騎手", "競馬場", "レーティング", "開催", "レーシング", "race", "odds", "result", "shutuba")

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.current = None
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            att = dict(attrs)
            self.current = {"href": att.get("href", ""), "text": "", "onclick": att.get("onclick", "")}
    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current is not None:
            self.items.append(self.current)
            self.current = None

def main():
    OUT.mkdir(exist_ok=True)
    summary = {"captured_at": datetime.now(timezone.utc).isoformat(), "pages": []}
    for page in PAGES:
        record = {"source": page, "status": "not_fetched", "matches": [], "error": None}
        try:
            request = Request(page, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
            with urlopen(request, timeout=15) as resp:
                body = resp.read(1_500_001)
                ct = resp.headers.get("Content-Type", "").lower()
                final_host = urlsplit(resp.geturl()).hostname
                if len(body) > 1_500_000 or "text/html" not in ct or final_host not in ("www.jra.go.jp", "jra.go.jp"):
                    raise ValueError("unexpected_response")
                record["status"] = "fetched"
                record["bytes"] = len(body)
                # JRA is commonly Shift_JIS; also support UTF-8. Avoid guessing as proof.
                charset = re.search(r"charset=[\\\"']?([\\w-]+)", ct + " " + body[:1500].decode("ascii", "ignore"), re.I)
                enc = charset.group(1) if charset else "utf-8"
                try:
                    html = body.decode(enc)
                except (LookupError, UnicodeError):
                    html = body.decode("cp932", errors="replace")
                parser = Anchors()
                parser.feed(html)
                hits = []
                for anchor in parser.items:
                    target = urljoin(resp.geturl(), anchor["href"])
                    parts = urlsplit(target)
                    label = " ".join(anchor["text"].split())[:120]
                    if parts.scheme not in ("http", "https"):
                        continue
                    if parts.hostname not in ("www.jra.go.jp", "jra.go.jp", "www.jra.go.jp", "sp.jra.jp"):
                        continue
                    searchable = label + " " + target + " " + anchor["onclick"]
                    if any(k.lower() in searchable.lower() for k in KEYWORDS):
                        hits.append({"text": label, "url": target, "onclick": anchor["onclick"][:180]})
                # Preserve observable order rather than guessing race URLs
                record["matches"] = hits[:90]
                record["total_matching_anchors"] = len(hits)
        except Exception as e:
            record["status"] = "failed"
            record["error"] = type(e).__name__ + ":" + str(e)[:180]
        summary["pages"].append(record)
    (OUT / "discovery.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for rec in summary["pages"]:
        print("PAGE", rec["source"], rec["status"], "matching", rec.get("total_matching_anchors", 0))
        for a in rec["matches"][:45]:
            print("LINK", json.dumps(a, ensure_ascii=False))
        if rec["error"]:
            print("ERROR", rec["error"])

if __name__ == "__main__":
    main()
