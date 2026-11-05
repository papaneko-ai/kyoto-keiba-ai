"""Inspect official Kyoto all-race HTML for payout/odds text without additional HTTP calls."""
from pathlib import Path
from html.parser import HTMLParser
import json,re

SOURCE=Path("jra_action_capture/kyoto_all_results_20261031.html")
OUT=Path("jra_action_capture/kyoto_payout_structure.json")

class VisibleText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hide=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.hide+=1
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.hide:self.hide-=1
    def handle_data(self,data):
        if not self.hide:
            s=" ".join(data.split())
            if s:self.parts.append(s)

def main():
    body=SOURCE.read_bytes()
    decoded=body.decode("cp932",errors="replace")
    parser=VisibleText();parser.feed(decoded)
    text=" ".join(parser.parts)
    keywords=["馬連","枠連","払戻金","単勝","複勝","馬単","3連複","京都","1R","12R","レース結果"]
    matches={}
    for word in keywords:
        found=list(re.finditer(re.escape(word),text))
        matches[word]={"count":len(found),"examples":[text[max(0,m.start()-110):m.end()+220] for m in found[:6]]}
    report={"page_bytes":len(body),"visible_text_length":len(text),"keywords":matches}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("PAYOUT_STRUCTURE",json.dumps(report,ensure_ascii=False)[:18000])
if __name__=="__main__":main()
