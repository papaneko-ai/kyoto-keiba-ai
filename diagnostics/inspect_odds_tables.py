"""Offline structure inspection of two real JRA historical odds HTML documents.
No HTTP requests; print bounded, sanitized diagnostic excerpts.
"""
from html.parser import HTMLParser
from pathlib import Path
import json
import re

ROOT=Path("jra_action_capture")
FILES=["kyoto_20261031_race01_quinella.html","kyoto_20261031_race01_bracket_quinella.html"]

class Tables(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.current=None;self.tables=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.skip+=1
        if tag=="table":
            if self.depth==0:self.current={"attrs":dict(attrs),"texts":[],"tags":[]}
            self.depth+=1
        if self.depth and self.current is not None and tag in ("tr","td","th"):
            if len(self.current["tags"])<120:self.current["tags"].append({"tag":tag, "attrs":dict(attrs)})
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.skip:self.skip-=1
        if tag=="table" and self.depth:
            self.depth-=1
            if self.depth==0 and self.current is not None:
                self.tables.append(self.current);self.current=None
    def handle_data(self,content):
        if self.depth and not self.skip and self.current is not None:
            value=" ".join(content.split())
            if value:self.current["texts"].append(value)
def main():
    output={}
    for filename in FILES:
        data=(ROOT/filename).read_bytes()
        html=data.decode("cp932",errors="replace")
        p=Tables();p.feed(html)
        summaries=[]
        for idx,t in enumerate(p.tables):
            body=" ".join(t["texts"])
            if any(x in body for x in ("枠連","馬連","オッズ","1 - ","1－","1-2")) or len(body)>100:
                summaries.append({"index":idx,"class":t["attrs"].get("class"),"id":t["attrs"].get("id"),
                                  "text":body[:600],"length":len(body),"tags":t["tags"][:12]})
        visible=re.sub(r"<[^>]+>"," ",html)
        visible=" ".join(visible.split())
        anchor=visible.find("ここから本文")
        if anchor<0:anchor=visible.find("最終オッズ")
        output[filename]={"tables_count":len(p.tables),"candidate_tables":summaries[-25:],
                          "body_sample":visible[anchor:anchor+2600] if anchor>=0 else ""}
        print("ODDS_STRUCTURE",json.dumps({"file":filename,**output[filename]},ensure_ascii=False)[:14000])
    (ROOT/"odds_structure.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
