"""Real Nov22 archive reanalysis, zero JRA network. Never export source HTML/key.
Exact original-link membership, not names or count differences, establishes scope.
Late profiles remain historical diagnostic sources, not pre-start feature evidence.
"""
import os,io,json,re,tarfile,hashlib
from pathlib import Path
from datetime import datetime,date,timezone,timedelta
from collections import Counter
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.jra_multi_capture_20261106 import parse
from diagnostics.jra_prior_form_offline import parse_horse_history
from diagnostics.kyoto_g04_all_horse_profiles import _metadata
from diagnostics.jra_pending_profile_plan import trusted_url

DAY="20261122"
def sha(b):return hashlib.sha256(b).hexdigest()

def archive(root,name,aad,allowed,key,cap):
    p=Path(root)
    blob=(p/name).read_bytes()
    if not 28<len(blob)<=cap or sha(blob)!=(p/"ciphertext_sha256.txt").read_text().strip():
        raise ValueError("cipher_sha_or_size")
    clear=AESGCM(key).decrypt(blob[:12],blob[12:],aad)
    out={};total=0
    with tarfile.open(fileobj=io.BytesIO(clear),mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or not allowed.fullmatch(m.name) or m.name in out or m.size>1500000:
                raise ValueError("archive_member_invalid")
            raw=tar.extractfile(m).read(1500001)
            total+=len(raw)
            if len(raw)!=m.size or total>cap*30:raise ValueError("archive_size_invalid")
            out[m.name]=raw
    return out

def run(key):
    cards=archive("nov22_cards","originals_all12.tar.gz.aesgcm",b"kyoto-nov22-observed-official-all12-source-only",re.compile(r"(?:r(?:0[1-9]|1[0-2])_(?:pc|sp)_official_racecard\.html|receipt\.json)"),key,10000000)
    profiles=archive("nov22_profiles","horse_profiles.tar.gz.aesgcm",b"kyoto-nov22-observed-profile-history-originals-v1",re.compile(r"(?:profile_\d{3}\.html|profile_receipt\.json)"),key,10000000)
    cr=json.loads(cards["receipt.json"]);pr=json.loads(profiles["profile_receipt.json"])
    public=json.loads(Path("nov22_parser/safe_race_parser_results.json").read_text())
    if any(d.get("day")!=DAY for d in (cr,pr,public)):raise ValueError("wrong_day")
    items={}
    for x in pr["items"]:
        h=x["observed_profile_url_sha256"]
        if h in items:raise ValueError("duplicate_profile_receipt")
        raw=profiles[x["encrypted_filename"]]
        if sha(raw)!=x["sha256"] or len(raw)!=x["bytes"]:raise ValueError("profile_original_sha")
        items[h]=(x,raw)
    all_expected=set();matched=set();race_reports={};failures=Counter();late=0
    for race in range(1,13):
        c=cr["races"][str(race)]["PC"];raw=cards[f"r{race:02d}_pc_official_racecard.html"]
        if sha(raw)!=c["sha256"] or sha(raw)!=public["races"][str(race)]["original_sha256"]:raise ValueError("racecard_original_sha")
        rows,errors=parse(raw,race,meeting_date=date(2026,11,22))
        if errors or len(rows)!=public["races"][str(race)]["runner_count"]:raise ValueError("roster_replay_mismatch")
        hour,minute=map(int,public["races"][str(race)]["start_time_jst"].split(":"))
        start=datetime(2026,11,22,hour,minute,tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
        rr={"registered":len(rows),"matched":0,"prestart_originals":0,"history_valid":0,"metadata_valid":0,"complete_parse":0,"prior_rows":0,"failure_counts":{}}
        rf=Counter()
        for row in rows:
            # The old followup used the exact relative observed href, with
            # https://jra.jp prepended. Check that exact request digest first.
            url=trusted_url(row["horse_profile_href"])
            old_url="https://jra.jp"+row["horse_profile_href"]
            h=sha(old_url.encode())
            if h in all_expected:raise ValueError("duplicate_registered_link")
            all_expected.add(h)
            if h not in items:rf["profile_not_captured"]+=1;continue
            x,data=items[h];matched.add(h);rr["matched"]+=1
            stamp=datetime.fromisoformat(x["captured_at_utc"])
            if stamp<start:rr["prestart_originals"]+=1
            else:late+=1
            history=False;metadata=False
            try:
                p=parse_horse_history(data,source_url=url,fetched_at_utc=stamp,prediction_cutoff_utc=start,target_date=date(2026,11,22),expected_horse_name=row["horse_name"],allow_verified_no_history=True)
                for e in p["invalid_rows"]:rf["history:"+e["reason"]]+=1
                history=not p["invalid_rows"]
                rr["prior_rows"]+=len(p["prior_rows"])
            except ValueError as e:rf["history:"+str(e)[:90]]+=1
            try:
                _metadata(data,row["horse_name"]);metadata=True
            except ValueError as e:rf["metadata:"+str(e)[:90]]+=1
            rr["history_valid"]+=int(history);rr["metadata_valid"]+=int(metadata);rr["complete_parse"]+=int(history and metadata)
        rr["failure_counts"]=dict(rf);failures.update(rf);race_reports[str(race)]=rr
    out={"schema":"kyoto_impl30_actual_profile_replay.v1","day":DAY,"registered_unique_links":len(all_expected),"captured_unique_links":len(items),"matched_registered_links":len(matched),"nonroster_links":len(set(items)-all_expected),"registered_links_missing":len(all_expected-set(items)),"poststart_matched_profiles":late,"races":race_reports,"failure_counts":dict(failures),"new_jra_http":0,"prediction_ready":False}
    return out
if __name__=="__main__":
    key=os.environ["ARCHIVE_KEY"]
    if not re.fullmatch(r"[a-fA-F0-9]{64}",key):raise ValueError("archive_key_invalid")
    report=run(bytes.fromhex(key))
    out=Path("actual_profile_replay");out.mkdir()
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
