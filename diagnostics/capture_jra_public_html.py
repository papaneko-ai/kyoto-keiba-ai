"""Read-only one-shot capture of JRA's public home and racing index pages.
No odds requests, authentication, database writes or application code changes.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import socket
import ssl

URLS = {
    "jra_home": "https://www.jra.go.jp/",
    "jra_keiba": "https://www.jra.go.jp/keiba/",
}
MAX_BYTES = 1_500_000
OUTPUT = Path("jra_capture")

def capture(name, url):
    result = {
        "page": name, "url": url, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "dns": "pending", "https": "pending", "status": None, "bytes": 0,
        "sha256": None, "filename": None, "reason": None,
    }
    host = urlsplit(url).hostname
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        result["dns"] = "ok"
    except OSError as exc:
        result.update(dns="failed", https="not_attempted", reason=type(exc).__name__)
        return result

    try:
        request = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; personal-research-single-capture)",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urlopen(request, timeout=15, context=ssl.create_default_context()) as response:
            result["status"] = response.status
            final_host = urlsplit(response.geturl()).hostname
            if final_host not in {"jra.go.jp", "www.jra.go.jp"}:
                result.update(https="redirect_rejected", reason="unexpected_redirect")
                return result
            mime = response.headers.get("Content-Type", "").lower()
            if "text/html" not in mime and "application/xhtml+xml" not in mime:
                result.update(https="non_html", reason="unexpected_content_type")
                return result
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                result.update(https="too_large", reason="response_exceeds_limit")
                return result
            if b"<html" not in data[:10000].lower() and b"<!doctype html" not in data[:10000].lower():
                result.update(https="not_html", reason="missing_html_root")
                return result
            filename = name + ".html"
            (OUTPUT / filename).write_bytes(data)
            result.update(https="ok", bytes=len(data), sha256=sha256(data).hexdigest(), filename=filename)
    except HTTPError as exc:
        result.update(https="http_error", status=exc.code, reason="HTTPError")
    except (URLError, TimeoutError, OSError) as exc:
        result.update(https="failed", reason=type(exc).__name__)
    return result

def main():
    OUTPUT.mkdir(exist_ok=True)
    records = [capture(name, url) for name, url in URLS.items()]
    summary = {"schema": "jra-capture-v1", "complete": all(r["https"] == "ok" for r in records), "results": records}
    (OUTPUT / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"complete": summary["complete"], "results": [
        {"page": r["page"], "dns": r["dns"], "https": r["https"], "status": r["status"],
         "bytes": r["bytes"], "reason": r["reason"]} for r in records
    ]}, ensure_ascii=False))
    return summary

if __name__ == "__main__":
    main()
