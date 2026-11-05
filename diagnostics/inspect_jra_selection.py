"""Inspect captured JRA entry/odds/result selection HTML without further network calls."""
from html.parser import HTMLParser
from pathlib import Path
import json

FILES = ("entries.html", "odds.html", "results.html")
ROOT = Path("jra_action_capture")

class Elements(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.forms=[]; self.options=[]; self.active=None;self.current_form=None;self.option=None
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="a":
            self.active={"text":"","href":d.get("href"),"onclick":d.get("onclick")}
        elif tag=="form":
            self.current_form={"name":d.get("name"),"action":d.get("action"),"method":d.get("method"),"fields":[]}
            self.forms.append(self.current_form)
        elif tag=="input" and self.current_form is not None:
            self.current_form["fields"].append({"name":d.get("name"),"value":(d.get("value") or "")[:100]})
        elif tag=="option":
            self.option={"text":"","value":d.get("value")}
    def handle_data(self,data):
        if self.active is not None:self.active["text"]+=data
        if self.option is not None:self.option["text"]+=data
    def handle_endtag(self,tag):
        if tag=="a" and self.active is not None:
            self.active["text"]=" ".join(self.active["text"].split())
            self.links.append(self.active);self.active=None
        elif tag=="form":self.current_form=None
        elif tag=="option" and self.option is not None:
            self.option["text"]=" ".join(self.option["text"].split());self.options.append(self.option);self.option=None

def main():
    results={}
    for name in FILES:
        path=ROOT/name
        if not path.exists():
            results[name]={"error":"not_captured"};continue
        html=path.read_bytes().decode("cp932",errors="replace")
        parser=Elements();parser.feed(html)
        interactive=[item for item in parser.links if item["onclick"] or any(w in (item["text"] or "") for w in ("京都","レース","開催","オッズ","馬連","枠連","11月"))]
        results[name]={"bytes":path.stat().st_size,"forms":parser.forms[:8],"links":interactive[:100],"links_total":len(parser.links),"interactive_total":len(interactive),"options":parser.options[:80]}
        print("HTML_DETAIL",json.dumps({"file":name,"bytes":results[name]["bytes"],"forms":parser.forms[:5],"interactive_total":len(interactive),"links":interactive[:35],"options":parser.options[:20]},ensure_ascii=False)[:18000])
    (ROOT/"selection_structure.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf8")

if __name__=="__main__":main()
