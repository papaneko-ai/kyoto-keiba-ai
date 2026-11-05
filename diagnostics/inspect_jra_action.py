"""Read-only inspection of JRA form fields and inline navigation code."""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from pathlib import Path
import json

class Inspect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "form":
            self.current = {"action": d.get("action"), "method": d.get("method"), "name": d.get("name"), "fields": []}
            self.forms.append(self.current)
        elif tag == "input" and self.current is not None:
            self.current["fields"].append({"name": d.get("name"), "type": d.get("type"), "value": (d.get("value") or "")[:80]})
        elif tag == "script" and d.get("src"):
            self.scripts.append(d["src"])
    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None

def main():
    url = "https://www.jra.go.jp/keiba/"
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as response:
        data = response.read(1_500_001)
    if len(data) > 1_500_000:
        raise ValueError("too large")
    html = data.decode("cp932", errors="replace")
    inspect = Inspect()
    inspect.feed(html)
    action_snippets = []
    for needle in ("function doAction", "function doAction(", "doAction = function"):
        position = html.find(needle)
        if position != -1:
            action_snippets.append(html[max(0, position - 80):position + 1800])
    # Inspect only the script URL explicitly referenced by the actual JRA HTML.
    js_url = "https://www.jra.go.jp/common/js/common2.js"
    js_details = {"url": js_url, "snippets": [], "error": None}
    try:
        with urlopen(Request(js_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as resp:
            raw = resp.read(200001)
        if len(raw) > 200000:
            raise ValueError("script_too_large")
        js = raw.decode("utf-8", errors="replace")
        for word in ("function doAction", "function doAction(", "doAction = function", "CNAME", "EXPIRE"):
            where = js.find(word)
            if where != -1:
                js_details["snippets"].append({"needle": word, "text": js[max(0,where-120):where+1500]})
    except Exception as exc:
        js_details["error"] = type(exc).__name__
    print("EXTERNAL_JS", json.dumps(js_details, ensure_ascii=False)[:10000])
    result = {"forms": inspect.forms[:30], "action_snippets": action_snippets, "scripts": inspect.scripts[:60], "external_js": js_details}
    out = Path("jra_link_discovery")
    out.mkdir(exist_ok=True)
    (out / "action_details.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FORMS", json.dumps(result["forms"], ensure_ascii=False)[:9000])
    print("ACTION_JS", json.dumps(action_snippets, ensure_ascii=False)[:7000])
    print("SCRIPTS", json.dumps(inspect.scripts[:35], ensure_ascii=False))

if __name__ == "__main__":
    main()
