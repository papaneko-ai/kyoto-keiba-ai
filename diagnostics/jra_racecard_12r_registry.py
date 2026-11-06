"""JRA indexed racecard URL registry and archived result first-runner spot-check.
Search-index text != captured official racecard HTML, and can never certify prediction.
"""
from hashlib import sha256
from zipfile import ZipFile
import json,csv
from pathlib import Path
from diagnostics.jra_roster_crosswalk import crosswalk

# [race, host, official page CNAME, first horse from JRA indexed result]
INDEXED=(
(1,"www.jra.go.jp","pw01dde0108202604100120261031/52","スリーオブスペイズ"),
(2,"own.jra.jp","pw01dde1008202604100220261031/E6","フクノブルースカイ"),
(3,"www.jra.go.jp","pw01dde0108202604100320261031/BC","シルクウォード"),
(4,"www.jra.go.jp","pw01dde0108202604100420261031/71","グロリアラウス"),
(5,"www.jra.go.jp","pw01dde1008202604100520261031/05","ソトッキー"),
(6,"www.jra.go.jp","pw01dde0108202604100620261031/DB","レッドガレオン"),
(7,"www.jra.go.jp","pw01dde0108202604100720261031/90","マリノエステーラ"),
(8,"www.jra.go.jp","pw01dde0108202604100820261031/45","ミサビスケッツ"),
(9,"www.jra.go.jp","pw01dde0108202604100920261031/FA","ダノンカゼルタ"),
(10,"www.jra.go.jp","pw01dde0108202604101020261031/EF","セブンマジシャン"),
(11,"www.jra.go.jp","pw01dde1008202604101120261031/83","レニュアージュ"),
(12,"www.jra.go.jp","pw01dde0108202604101220261031/59","スマートティアナ"))
ARCHIVE_MEMBER="jra_action_capture/kyoto_all_results_20261031.html"

def racecard_sources():
    out=[]
    for race,host,cname,name in INDEXED:
        if host not in ("www.jra.go.jp","own.jra.jp") or f"20260410{race:02d}20261031" not in cname:
            raise ValueError("unverified_race_identity")
        out.append({"race_number":race,"url":f"https://{host}/JRADB/accessD.html?CNAME="+cname.replace("/","%2F"),
                    "indexed_first_name":name,"source_type":"JRA_SEARCH_INDEX_ONLY",
                    "raw_html_acquired":False,"pre_race_snapshot_verified":False,"training_ready":False})
    return out

def compare_archived_result(raw,*,result_url="https://www.jra.go.jp/JRADB/accessD.html"):
    result=crosswalk(raw,result_url=result_url)
    if result["parse_errors"]:raise ValueError("result_parse_errors")
    records=result["runners"]
    checks=[]
    for source in racecard_sources():
        rows=[x for x in records if x["race_number"]==source["race_number"] and x["horse_number"]==1]
        if len(rows)!=1:raise ValueError("first_runner_missing_or_duplicate")
        checks.append({"race":source["race_number"],"indexed_first_name":source["indexed_first_name"],
                       "archived_first_name":rows[0]["horse_name"],
                       "first_name_match":rows[0]["horse_name"]==source["indexed_first_name"],
                       "whole_racecard_checked":False})
    return {"schema_version":"jra_12r_indexed_first_runner_audit.v1",
            "result_source_sha256":sha256(raw).hexdigest(),
            "race_count":result["race_count"],"result_rows":len(records),
            "profile_navigation_tokens_unique":len({x["profile_navigation_token"] for x in records}),
            "official_indexed_page_count":len(INDEXED),
            "first_runner_matches":sum(x["first_name_match"] for x in checks),
            "first_runner_spotchecks":checks,"sources":racecard_sources(),
            "whole_racecard_roster_verified":False,"permanent_horse_ids_verified":False,
            "pre_race_snapshot_verified":False,"ready_for_training":False}

def audit_zip(path):
    with ZipFile(path) as z:raw=z.read(ARCHIVE_MEMBER)
    return compare_archived_result(raw)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--archive",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=audit_zip(a.archive)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({k:v for k,v in report.items() if not isinstance(v,list)},ensure_ascii=False))
