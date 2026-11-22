"""Forensic structural evidence for exactly five unresolved JRA horse histories.

No HTTP. Keep alternative aliases separate from authenticated identity.
Inspect track public table headings rather than inventing values.
"""
import os,re,hashlib,json
from pathlib import Path
from bs4 import BeautifulSoup
from diagnostics.kyoto_nov22_actual_185_profile_history_track_replay import archived,source_cards
from diagnostics.kyoto_nov22_horse_profile_followup import plan
from diagnostics.jra_prior_form_offline import parse_horse_history
from datetime import datetime,date,timezone
def text(raw):
    try:return raw.decode("utf8")
    except UnicodeError:return raw.decode("cp932",errors="replace")
def main():
    key=bytes.fromhex(os.environ["KYOTO_JRA_ARCHIVE_AES256_HEX"])
    cards,receipts=source_cards(key)
    queue=plan(cards)
    profiles=archived("profile","ciphertext_sha256.txt",b"kyoto-nov22-observed-profile-history-originals-v1",key)
    actual=json.loads(profiles["profile_receipt.json"])["items"]
    selected={}
    for pos in (14,40,102,138,173):
        idx=pos-1
        entry=queue[idx]
        raw=profiles[f"profile_{pos:03d}.html"]
        soup=BeautifulSoup(text(raw),"html.parser")
        visible=[]
        for node in soup.select("span.txt"):
            if node.select_one("span.opt") and "競走馬情報" in node.get_text(" ",strip=True):
                cp=BeautifulSoup(str(node),"html.parser")
                for extra in cp.select("span.opt,span.name_en"):extra.decompose()
                visible.append(cp.get_text(" ",strip=True))
        hist=next((t for t in soup.select("table")
                   if t.select_one("th.date") and t.select_one("th.place")
                   and t.select_one("th.dist")),None)
        summary={"observed_racecard_label":entry["horse_name_observed"],
                 "actual_profile_identity":visible,
                 "name_equal":bool(visible and entry["horse_name_observed"]==visible[0]),
                 "history_present":hist is not None,
                 "raw_sha_matches_receipt":hashlib.sha256(raw).hexdigest()==actual[idx]["sha256"]}
        if hist is not None:
            trs=hist.select("tr")[1:]
            summary["source_history_rows"]=len(trs)
            summary["history_row_signatures"]=[{
                "number":i,
                "cell_count":len(tr.find_all("td",recursive=False)),
                "date":(tr.select_one("td.date").get_text(" ",strip=True) if tr.select_one("td.date") else ""),
                "place":(tr.select_one("td.place").get_text(" ",strip=True) if tr.select_one("td.place") else ""),
                "distance":(tr.select_one("td.dist").get_text(" ",strip=True) if tr.select_one("td.dist") else ""),
                "race_name":(tr.select_one("td.race").get_text(" ",strip=True) if tr.select_one("td.race") else "")
            } for i,tr in enumerate(trs,1) if i<=6]
        selected[str(pos)]=summary
    track=archived("track","source_sha256.txt",b"kyoto-nov22-official-ground-source-only",key)
    soup=BeautifulSoup(text(track["official_kyoto_track.html"]),"html.parser")
    info={"tables":[]}
    for t in soup.select("table")[:20]:
        info["tables"].append({"headers":[th.get_text(" ",strip=True)[:60] for th in t.select("th")[:16]],
                               "first_rows":[tr.get_text(" ",strip=True)[:200] for tr in t.select("tr")[:3]]})
    for phrase in ("馬場状態","芝のクッション値","含水率","芝コース","ダートコース"):
        n=soup.find(string=lambda s:isinstance(s,str) and phrase in s)
        info[phrase]={"parent_text":n.parent.parent.get_text(" ",strip=True)[:520] if n and n.parent and n.parent.parent else ""}
    report={"schema":"kyoto_nov22_five_rejects_official_source_layout.v1",
            "profiles":selected,"track_layout":info,
            "no_jra_http":True,"approval_to_guess_identity":False}
    dest=Path("actual_layout_forensic");dest.mkdir()
    (dest/"five_horses_and_track.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("FIVE_PROFILE_SOURCE_LAYOUT="+json.dumps(selected,ensure_ascii=False)[:4500])
    print("OFFICIAL_TRACK_TABLE_LAYOUT="+json.dumps(info,ensure_ascii=False)[:7000])
if __name__=="__main__":main()
