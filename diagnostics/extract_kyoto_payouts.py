"""Extract 12 race section payouts from an already captured genuine JRA HTML.
This script never reads live URLs. It labels sections by order rather than inventing race IDs.
"""
from html.parser import HTMLParser
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import re

SOURCE=Path("jra_action_capture/kyoto_all_results_20261031.html")
OUT=Path("jra_action_capture/kyoto_payouts_20261031.json")

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.hidden:self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:
            fragment=" ".join(data.split())
            if fragment:self.parts.append(fragment)

def parse_payouts(content):
    p=VisibleText()
    p.feed(content.decode("cp932",errors="replace"))
    text=" ".join(p.parts)
    if "2026年10月31日（土曜）4回京都10日" not in text:
        raise ValueError("meeting_identity_not_found")
    # Scope each payout to one race section. Never cross into another race's values.
    starts=[m.start() for m in re.finditer("払戻金 単勝 ",text)]
    if len(starts)!=12:
        raise ValueError("unexpected_race_section_count:"+str(len(starts)))
    data=[]
    for idx,start in enumerate(starts):
        segment=text[start:(starts[idx+1] if idx+1<len(starts) else len(text))]
        # '馬連 ... 馬単' and '枠連 ... ワイド' serve as hard boundaries.
        quinella=re.search(r"馬連\\s+(\\d{1,2})-(\\d{1,2})\\s+([\\d,]+)\\s+円",segment)
        bracket=re.search(r"枠連\\s+(\\d)-(\\d)\\s+([\\d,]+)\\s+円",segment)
        absent=bool(re.search(r"枠連\\s+ワイド",segment))
        if not quinella:
            raise ValueError("missing_quinella_section_"+str(idx+1))
        if not (bracket or absent) or (bracket and absent):
            raise ValueError("ambiguous_bracket_section_"+str(idx+1))
        def build(match):
            if match is None:return None
            n1,n2,pay=match.groups()
            return {"combination": [int(n1),int(n2)],"payout_yen_per_100":int(pay.replace(",",""))}
        data.append({"section_order":idx+1,"race_number_verified":False,
                     "quinella":build(quinella),
                     "bracket_quinella":{"state":"published","value":build(bracket)} if bracket else
                                      {"state":"not_displayed","value":None}})
    return data

def main():
    raw=SOURCE.read_bytes()
    rows=parse_payouts(raw)
    out={"source":"JRA official HTML", "meeting":"2026-10-31 Kyoto, 4th meeting day 10",
         "captured_html_sha256":sha256(raw).hexdigest(),
         "extracted_at_utc":datetime.now(timezone.utc).isoformat(),
         "race_number_assignment":"NOT_VERIFIED; section_order only",
         "odds_type":"FINAL_PAYOUT_NOT_PRE_RACE_ODDS","rows":rows}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print("EXTRACTED_PAYOUTS",json.dumps({"rows":len(rows),"quinella":sum(bool(x["quinella"]) for x in rows),
        "bracket_displayed":sum(x["bracket_quinella"]["state"]=="published" for x in rows),
        "rows_detail":rows},ensure_ascii=False)[:18000])

if __name__=="__main__":
    main()
