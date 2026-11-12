"""Second-run read-only verification of a real JRA final-source SQLite journal.

Does not import the code creating the journal or the first JRA parser.
Independently links SQL source SHA to pristine JRA original HTML ZIP,
checks original top-two and final two market payouts, SHA chain, no bets.
"""
from __future__ import annotations
import hashlib,io,json,re,sqlite3,zipfile
from pathlib import Path
from bs4 import BeautifulSoup

class SecondOfficialAuditRejected(ValueError):pass
ZIP_SHA="dad5f93f72b3b993ab96ef1a053561d60a84ad3c868b4d3b4f4b2dc72bb9f004"
RECEIPT_RUN="43141692999"
RECEIPT_HEAD="554f40404fec9970e1f09cb54c45220b1bcb9cee"
RACES=[
 ("2026-10-25",10,"20261025_kyoto_10.html",(12,10),(7,6),(10,12,15090),(6,7,1540)),
 ("2026-11-08",11,"20261108_kyoto_11.html",(11,8),(6,4),(8,11,1670),(4,6,1330)),
]
def check(ok,why):
    if not ok:raise SecondOfficialAuditRejected(why)
def hash_obj(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()
def original_fields(raw,date,race):
    soup=BeautifulSoup(raw.decode("cp932","strict"),"html.parser")
    tables=[x for x in soup.select("table") if all(x.select_one("th."+t) for t in ("horse","num","waku","place"))]
    check(len(tables)==1,"official_result_table_ambiguous")
    rows=[]
    for tr in tables[0].select("tr"):
        h=tr.select_one("td.horse");n=tr.select_one("td.num")
        if h is None:continue
        f=tr.select_one("td.waku img[alt]");p=tr.select_one("td.place")
        check(n is not None and f is not None and p is not None,"incomplete_result_line")
        m=re.search(r"枠([1-8])",f.get("alt",""))
        check(bool(m),"frame_unreadable")
        rows.append((int(n.get_text(strip=True)),int(m.group(1)),p.get_text(" ",strip=True)))
    check(len(rows)>=2 and sum(x[2]=="1" for x in rows)==1 and sum(x[2]=="2" for x in rows)==1,"top_two_not_unique")
    winner=next(x for x in rows if x[2]=="1")
    second=next(x for x in rows if x[2]=="2")
    text=soup.get_text(" ",strip=True)
    check(f"{int(date[:4])}年{int(date[5:7])}月{int(date[8:])}日" in text and
          "京都" in text and re.search(rf"(?<!\d){race}\s*(?:R|レース)",text),
          "official_race_identity_missing")
    def market(label,next_):
        found=re.findall(r"(?<!\S)"+label+r"\s+(.+?)\s+"+next_+r"(?=\s|$)",text)
        check(len(found)==1,"payout_section_not_unique")
        row=re.fullmatch(r"\s*(\d{1,2})-(\d{1,2})\s+([\d,]+)\s+円\s+\d+\s+番人気\s*",found[0])
        check(row is not None,"invalid_payout_section")
        return (int(row[1]),int(row[2]),int(row[3].replace(",","")))
    return winner,second,market("馬連","馬単"),market("枠連","ワイド"),len(rows)

def verify(db_path,db_receipt,actual_source_zip):
    path=Path(db_path)
    check(path.is_file() and not path.is_symlink(),"missing_sqlite_file")
    check(hashlib.sha256(path.read_bytes()).hexdigest()==db_receipt.get("registry_sha256"),"sqlite_receipt_hash_mismatch")
    check(db_receipt.get("schema")=="kyoto_two_real_jra_final_only_registry_evidence.v1"
        and db_receipt.get("ci_run_id")==RECEIPT_RUN
        and db_receipt.get("ci_sha")==RECEIPT_HEAD,"wrong_first_run_receipt")
    check(db_receipt.get("synthetic_bets_inserted") is False
          and db_receipt.get("prerace_market_verified") is False
          and db_receipt.get("live_actual_settlement_operational") is False,"false_live_claim")
    check(hashlib.sha256(actual_source_zip).hexdigest()==ZIP_SHA
          and db_receipt.get("source_archive_sha256")==ZIP_SHA,"original_html_zip_unverified")
    uri=path.resolve().as_uri()+"?mode=ro"
    con=sqlite3.connect(uri,uri=True)
    try:
        stored=con.execute("SELECT event_key,race_id,observed_at_utc,raw_payload,prior_sha256,event_sha256 FROM official_postrace_observations ORDER BY seq").fetchall()
    finally:con.close()
    check(len(stored)==2,"expected_exact_two_actual_races")
    chain="0"*64
    results=[]
    with zipfile.ZipFile(io.BytesIO(actual_source_zip)) as z:
        for rec,(date,race,member,hn,fn,q,b) in zip(stored,RACES):
            event_key,race_id,at,raw,prior,event_sha=rec
            p=json.loads(raw)
            check(raw==json.dumps(p,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False),"canonical_payload_changed")
            check(prior==chain,"broken_event_chain")
            check(event_sha==hash_obj({"event_key":event_key,"race_id":race_id,
                "observed_at_utc":at,"payload":p,"prior_sha256":prior}),"event_sha_mismatch")
            check(at.endswith("Z") and at.startswith("2026-11-12T") and
                  event_key==f"official_final:{date}-KYOTO-R{race:02d}" and
                  race_id==f"{date}-KYOTO-R{race:02d}","source_identity_or_time_mismatch")
            raw_original=z.read(member)
            source_hash=hashlib.sha256(raw_original).hexdigest()
            check(p["source_sha256"]==source_hash,"original_jra_html_hash_mismatch")
            first,second,pr_q,pr_b,runner_count=original_fields(raw_original,date,race)
            check((first[0],second[0])==hn and (first[1],second[1])==fn
                and pr_q==q and pr_b==b,"independent_original_official_result_disagrees")
            check(p["winner_horse_number"]==first[0]
                and p["runner_up_horse_number"]==second[0]
                and tuple(p["quinella_final"]["pair"])+
                    (p["quinella_final"]["yen_per_100"],)==q
                and tuple(p["bracket_final"]["pair"])+
                    (p["bracket_final"]["yen_per_100"],)==b,"saved_official_payout_disagrees")
            check(p["payouts_are_genuine_final_not_prerace_odds"] is True
                and p["no_prerace_bets_asserted"] is True,"false_prerace_claim")
            chain=event_sha
            results.append({"date":date,"race_number":race,"original_source_sha256":source_hash,
                            "postrace_runner_count":runner_count,"payout_markets":2})
    check(chain==db_receipt["replay"]["chain_head"]==db_receipt["append"]["chain_head"],
          "source_replay_chain_mismatch")
    return {"schema":"kyoto_p6_second_original_official_sqlite_validation.v1",
            "original_ci_run_id":int(RECEIPT_RUN),
            "original_sqlite_sha256":db_receipt["registry_sha256"],
            "official_source_zip_sha256":ZIP_SHA,
            "verified_real_postrace_races":2,"verified_markets":4,
            "verified_postrace_runner_rows":sum(x["postrace_runner_count"] for x in results),
            "events":results,
            "independent_method":"new BeautifulSoup result+market parser and read-only raw sqlite chain replay",
            "authentic_prerace_odds":False,"preregistered_paper_trades":False,
            "real_bet_authorized":False}
