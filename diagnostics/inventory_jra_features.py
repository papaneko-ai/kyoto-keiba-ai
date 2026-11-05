"""Inspect predictive features actually present in JRA's public HTML.
Read the already captured genuine Kyoto all-results page, and GET three
public supplementary pages once each. Never backdate extracted information.
"""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import re
import time

BASE=Path("jra_feature_discovery")
SOURCE=Path("jra_action_capture/kyoto_all_results_20261031.html")
URLS={
 "kyoto_track_conditions":"https://www.jra.go.jp/keiba/baba/",
 "racecard_pdf_index":"https://www.jra.go.jp/keiba/rpdf/",
 "jockey_trainer_index":"https://www.jra.go.jp/datafile/meikan/",
}
MARKERS={
 "runners":["馬名","馬番","着順","性齢","負担重量","騎手名","調教師名"],
 "race_conditions":["発走時刻","コース","ダート","芝","天候","馬場"],
 "results":["走破タイム","タイム","着差","コーナー通過順位","推定上り","馬体重","単勝人気"],
 "financial":["払戻金","馬連","枠連"],
 "track":["クッション値","含水率","芝丈","散水","使用コース","馬場状態","雨量"],
 "form":["過去4走","過去の成績","競走馬情報","騎手","調教師"],
}

class Content(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text=[]
        self.hidden=0
        self.links=[]
        self.a=None
        self.tables=0
        self.rows=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag in ("script","style"):
            self.hidden+=1
        if tag=="a":
            self.a={"label":"","href":d.get("href","")}
        if tag=="table":
            self.tables+=1
        if tag=="tr":
            self.rows+=1
    def handle_data(self,data):
        if not self.hidden:
            value=" ".join(data.split())
            if value:
                self.text.append(value)
                if self.a is not None:
                    self.a["label"]+=value+" "
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.hidden:
            self.hidden-=1
        if tag=="a" and self.a is not None:
            self.a["label"]=" ".join(self.a["label"].split())
            self.links.append(self.a)
            self.a=None

def summarize(raw):
    html=raw.decode("cp932",errors="replace")
    parser=Content()
    parser.feed(html)
    text=" ".join(parser.text)
    counts={group:{word:text.count(word) for word in words}
            for group,words in MARKERS.items()}
    sections=[]
    for word in ("着順","馬体重","払戻金","クッション値","含水率","過去4走","騎手","調教師","馬場状態"):
        p=text.find(word)
        if p>=0:
            sections.append({"term":word,"excerpt":text[max(0,p-55):p+170]})
    links=[x for x in parser.links if any(w in x["label"] for w in
           ("京都","騎手","調教師","馬場","競走馬","出馬表","含水率","クッション"))]
    return {"html_bytes":len(raw),"sha256":sha256(raw).hexdigest(),
            "table_count":parser.tables,"table_row_count":parser.rows,
            "keyword_counts":counts,"sample_context":sections,
            "relevant_links":links[:35],
            "warning":"keyword presence proves visibility, not stable field extraction"}

def retrieve(url):
    host=urlsplit(url).hostname
    if host!="www.jra.go.jp":
        raise ValueError("Unexpected hostname")
    req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
    with urlopen(req,timeout=15) as response:
        if urlsplit(response.geturl()).hostname not in ("www.jra.go.jp","jra.go.jp"):
            raise ValueError("External redirect")
        body=response.read(1_000_001)
        if len(body)>1_000_000:raise ValueError("oversize")
        if "html" not in response.headers.get("Content-Type","").lower():
            raise ValueError("not HTML")
    return body

def main():
    BASE.mkdir(exist_ok=True)
    report={"captured_at_utc":datetime.now(timezone.utc).isoformat(),
            "historical_source":"2026-10-31 Kyoto official race results",
            "sources":{}, "pre_race_data_verified":False}
    if SOURCE.exists():
        report["sources"]["kyoto_historical_results"]={
            "status":"read_local_genuine_html",**summarize(SOURCE.read_bytes())}
    else:
        report["sources"]["kyoto_historical_results"]={"status":"missing_local_html"}
    for index,(key,url) in enumerate(URLS.items()):
        if index:
            time.sleep(2)
        try:
            raw=retrieve(url)
            (BASE/(key+".html")).write_bytes(raw)
            report["sources"][key]={"status":"retrieved", "url":url,**summarize(raw)}
        except Exception as error:
            report["sources"][key]={"status":"failed","url":url,
                                     "error":type(error).__name__+":"+str(error)[:120]}
    (BASE/"jra_feature_inventory.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    for key,value in report["sources"].items():
        print("JRA_FEATURE_SOURCE",json.dumps({
            "key":key,"status":value["status"],
            "bytes":value.get("html_bytes"),"tables":value.get("table_count"),
            "rows":value.get("table_row_count"),
            "keyword_counts":value.get("keyword_counts"),
            "sample_context":value.get("sample_context",[])[:8],
            "links":value.get("relevant_links",[])[:12],
            "error":value.get("error")
        },ensure_ascii=False)[:10000])

if __name__=="__main__":
    main()
