"""Capture the actual quinella and bracket-quinella views for ONE historical Kyoto race.
Two requests total, solely using form actions parsed from previously captured JRA HTML.
These are historical final odds; never use them as pre-race evidence.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urljoin, urlsplit
from datetime import datetime, timezone
from hashlib import sha256
import re
import json

ROOT = Path("jra_action_capture")
SOURCE = ROOT / "kyoto_historical_odds_one.html"
TARGETS = {"馬連": "quinella", "枠連": "bracket_quinella"}
MAX_BYTES = 1_500_000

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.a = None
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.a = {"label": "", "onclick": dict(attrs).get("onclick") or ""}
    def handle_data(self, value):
        if self.a is not None:
            self.a["label"] += value
    def handle_endtag(self, tag):
        if tag == "a" and self.a is not None:
            self.a["label"] = " ".join(self.a["label"].split())
            self.items.append(self.a)
            self.a = None

class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hide = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hide += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hide:
            self.hide -= 1
    def handle_data(self, data):
        if not self.hide:
            s = " ".join(data.split())
            if s:
                self.parts.append(s)

def main():
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    source = SOURCE.read_bytes()
    parser = Anchors()
    parser.feed(source.decode("cp932", errors="replace"))
    report = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": sha256(source).hexdigest(),
        "historical_final_odds_only": True,
        "results": []
    }
    for label, key in TARGETS.items():
        row = {"type": key, "label": label, "status": "not_attempted"}
        matches = [i for i in parser.items if i["label"] == label and "doAction" in i["onclick"]]
        if len(matches) != 1:
            row.update(status="ambiguous_official_link", count=len(matches))
            report["results"].append(row)
            continue
        m = re.search(r"doAction\s*\(\s*'([^']+)'\s*,\s*'([^']+)'", matches[0]["onclick"])
        if not m:
            row["status"] = "unrecognized_action"
            report["results"].append(row)
            continue
        path, cname = m.groups()
        url = urljoin("https://www.jra.go.jp/", path)
        if url != "https://www.jra.go.jp/JRADB/accessO.html":
            raise ValueError("unexpected_url")
        request = Request(
            url,
            data=urlencode({"cname": cname}).encode("ascii"),
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.jra.go.jp/keiba/",
                     "Content-Type": "application/x-www-form-urlencoded", "Accept": "text/html"},
            method="POST"
        )
        try:
            with urlopen(request, timeout=20) as response:
                content_type = response.headers.get("Content-Type", "")
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES or "html" not in content_type.lower():
                    raise ValueError("invalid_html_response")
                if urlsplit(response.geturl()).hostname not in ("jra.go.jp", "www.jra.go.jp"):
                    raise ValueError("unexpected_redirect")
                http_status = response.status
            output = ROOT / ("kyoto_20261031_race01_" + key + ".html")
            output.write_bytes(payload)
            v = Visible()
            v.feed(payload.decode("cp932", errors="replace"))
            text = " ".join(v.parts)
            word = label
            pos = text.find(word)
            row.update(status="captured_html", http=http_status, bytes=len(payload),
                       sha256=sha256(payload).hexdigest(), filename=output.name,
                       markers={x: text.count(x) for x in ("馬連", "枠連", "最終", "オッズ", "京都")},
                       first_market_context=text[max(0, pos-50):pos+900] if pos >= 0 else "")
        except Exception as exc:
            row.update(status="failed", error=type(exc).__name__ + ":" + str(exc)[:160])
        report["results"].append(row)
    (ROOT / "kyoto_historical_bet_types.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("KYOTO_BET_TYPES", json.dumps(report, ensure_ascii=False)[:14000])

if __name__ == "__main__":
    main()
