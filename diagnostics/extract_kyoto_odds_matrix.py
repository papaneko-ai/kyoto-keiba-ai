"""Extract actual historical JRA odds matrices for one Kyoto race into JSON.
Input: saved official HTML only. Never label final odds as pre-race odds.
"""
from html.parser import HTMLParser
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import re

ROOT=Path("jra_action_capture")
INPUTS={"quinella":"kyoto_20261031_race01_quinella.html",
        "bracket_quinella":"kyoto_20261031_race01_bracket_quinella.html"}

class TableValues(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables=[]
        self.depth=0
        self.text=None
        self.attrs=None
        self.hide=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):
            self.hide+=1
        if tag=="table":
            if self.depth==0:
                self.text=[]
                self.attrs=dict(attrs)
            self.depth+=1
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.hide:
            self.hide-=1
        if tag=="table" and self.depth:
            self.depth-=1
            if self.depth==0:
                self.tables.append({"text":" ".join(self.text),"class":self.attrs.get("class","")})
                self.text=None
    def handle_data(self,data):
        if self.depth and not self.hide and self.text is not None:
            val=" ".join(data.split())
            if val:self.text.append(val)

def read_market(raw, market):
    html=raw.decode("cp932",errors="replace")
    if "2026年10月31日" not in html or "4回京都10日" not in html or "最終オッズ" not in html:
        raise ValueError("historical_meeting_identity_missing")
    if ("馬連オッズ" if market=="quinella" else "枠連オッズ") not in html:
        raise ValueError("ticket_type_heading_missing")
    reader=TableValues()
    reader.feed(html)
    tables=[t for t in reader.tables if "発売票数" not in t["text"]]
    n=16 if market=="quinella" else 8
    expected=n-1 if market=="quinella" else n
    if len(tables)!=expected:
        raise ValueError("unexpected_table_count:"+str(len(tables)))
    rows=[]
    for ti, table in enumerate(tables):
        if "narrow" not in table["class"]:
            raise ValueError("unexpected_market_table_class")
        tokens=table["text"].split()
        base=ti+1
        if market=="quinella":
            if not tokens or tokens[0]!=str(base):
                raise ValueError("base_horse_not_matching")
            tokens=tokens[1:]
        if len(tokens)%2:
            raise ValueError("odd_market_tokens")
        previous=base-1 if market=="bracket_quinella" else base
        for index in range(0,len(tokens),2):
            second=int(tokens[index])
            odds=float(tokens[index+1].replace(",",""))
            if second<=previous or second>n or not (odds>1.0 and odds<1000000):
                raise ValueError("invalid_or_unordered_pair")
            if market=="quinella" and second<=base:
                raise ValueError("invalid_horse_pair")
            if market=="bracket_quinella" and second<base:
                raise ValueError("invalid_bracket_pair")
            previous=second
            rows.append({"pair":[base,second],"odds":odds})
    if len(set(tuple(x["pair"]) for x in rows))!=len(rows):
        raise ValueError("duplicate_pairs")
    if len(rows)!=n*(n-1)//2 if market=="quinella" else len(rows)!=n*(n+1)//2:
        raise ValueError("incomplete_matrix")
    return rows

def main():
    out={"meeting_date":"2026-10-31","venue":"京都","race_number":1,
         "odds_phase":"historical_final_not_pre_race",
         "captured_at_utc":datetime.now(timezone.utc).isoformat(),"markets":{}}
    for market,name in INPUTS.items():
        raw=(ROOT/name).read_bytes()
        rows=read_market(raw,market)
        out["markets"][market]={"source_sha256":sha256(raw).hexdigest(),"count":len(rows),"pairs":rows}
    # Verify winning combinations against the independently parsed real payout HTML.
    q=next(x for x in out["markets"]["quinella"]["pairs"] if x["pair"]==[5,13])
    b=next(x for x in out["markets"]["bracket_quinella"]["pairs"] if x["pair"]==[3,7])
    if q["odds"]!=15.1 or b["odds"]!=6.2:
        raise ValueError("winning_pair_crosscheck_failed")
    (ROOT/"kyoto_race01_odds_structured.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
    print("ODDS_EXTRACTION",json.dumps({
        "quinella_pairs":out["markets"]["quinella"]["count"],
        "bracket_pairs":out["markets"]["bracket_quinella"]["count"],
        "winning_quinella_odds":q["odds"],"winning_bracket_odds":b["odds"],
        "crosscheck":"passed","source_type":"historical_final_odds"
    },ensure_ascii=False))

if __name__=="__main__":main()
