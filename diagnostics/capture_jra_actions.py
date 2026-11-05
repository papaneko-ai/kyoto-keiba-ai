"""One-shot official JRA form navigation: odds, entries, results.
Only values directly parsed from live official page; 3 POSTs max; no retries.
"""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlencode
from urllib.request import Request, urlopen
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

ORIGIN = "https://www.jra.go.jp/keiba/"
TARGETS = {"出馬表": "entries", "オッズ": "odds", "レース結果": "results"}
OUT = Path("jra_action_capture")
MAX_BYTES = 1_500_000

class Actions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.active = None
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.active = {"text": "", "onclick": dict(attrs).get("onclick", "")}
    def handle_data(self, data):
        if self.active is not None:
            self.active["text"] += data
    def handle_endtag(self, tag):
        if tag == "a" and self.active is not None:
            self.links.append(self.active)
            self.active = None

def official_values(source):
    result = {}
    parser = Actions()
    parser.feed(source.decode("cp932", errors="replace"))
    for item in parser.links:
        label = " ".join(item["text"].split())
        if label not in TARGETS or label in result:
            continue
        # Exact quoted two-argument signature discovered in official markup.
        match = re.search("doAction\\s*\\(\\s*'([^']+)'\\s*,\\s*'([^']+)'\\s*\\)", item["onclick"])
        if not match:
            continue
        path, cname = match.groups()
        url = urljoin(ORIGIN, path)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "www.jra.go.jp" or not parsed.path.startswith("/JRADB/"):
            continue
        result[label] = {"url": url, "cname": cname}
    return result

def main():
    OUT.mkdir(exist_ok=True)
    with urlopen(Request(ORIGIN, headers={"User-Agent":"Mozilla/5.0", "Accept":"text/html"}), timeout=15) as response:
        source = response.read(MAX_BYTES + 1)
    if len(source) > MAX_BYTES:
        raise ValueError("index_html_too_large")
    targets = official_values(source)
    report = {"captured_at": datetime.now(timezone.utc).isoformat(), "entry_actions_found": list(targets.keys()), "results":[]}
    for label, filename in TARGETS.items():
        result = {"name": label, "status": "not_attempted", "http": None, "bytes": None, "sha256": None, "file": None, "reason": None}
        if label not in targets:
            result.update(status="missing_official_action",reason="not_in_live_index")
            report["results"].append(result)
            continue
        target = targets[label]
        req = Request(target["url"], data=urlencode({"cname": target["cname"]}).encode("ascii"), headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": ORIGIN,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml",
        }, method="POST")
        try:
            with urlopen(req, timeout=20) as response:
                result["http"] = response.status
                ct = response.headers.get("Content-Type", "").lower()
                host = urlsplit(response.geturl()).hostname
                body = response.read(MAX_BYTES + 1)
                if host not in ("www.jra.go.jp", "jra.go.jp"):
                    raise ValueError("external_redirect")
                if len(body) > MAX_BYTES:
                    raise ValueError("page_too_large")
                if "html" not in ct:
                    raise ValueError("not_html_content_type")
                if b"<html" not in body[:10000].lower() and b"<!doctype" not in body[:10000].lower():
                    raise ValueError("not_html_document")
                path=filename+".html"
                (OUT / path).write_bytes(body)
                result.update(status="captured_html",bytes=len(body),sha256=sha256(body).hexdigest(),file=path)
                # Existence of official racing labels does not prove odds/entries parsed.
                decoded=body.decode("cp932",errors="replace")
                result["marker_counts"]={k:decoded.count(k) for k in ("京都","馬連","枠連","出馬表","オッズ","レース結果")}
        except Exception as exc:
            result.update(status="failed",reason=type(exc).__name__ + ":" + str(exc)[:140])
        report["results"].append(result)
        print("ACTION",json.dumps(result,ensure_ascii=False))
    (OUT / "report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("ACTIONS_FOUND",json.dumps(report["entry_actions_found"],ensure_ascii=False))

if __name__ == "__main__":
    main()
