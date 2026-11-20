"""G04: guarded Kyoto all-horse official-profile capture after verified G03.

No guessed URLs, no repeated HTTP for the same horse, no data after race start
is promoted to as-of history. Originals survive partial failures and are sealed
by the existing weekend AES-GCM archive. Prediction/training always blocked.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,date,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from bs4 import BeautifulSoup
from diagnostics.jra_pending_profile_plan import trusted_url,PlanningError
from diagnostics.jra_prior_form_offline import parse_horse_history
from diagnostics.kyoto_g03_proof_verify import verify as verify_g03, G03ProofRejected

class G04Rejected(ValueError):pass
JST=ZoneInfo("Asia/Tokyo")
MAX_PROFILE=1_500_000
MAX_HORSES=216

def _utc(value):
    if type(value) is not str:raise G04Rejected("utc_timestamp_missing")
    try: stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise G04Rejected("utc_timestamp_invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset()!=timezone.utc.utcoffset(None):
        raise G04Rejected("timestamp_not_utc")
    return stamp

def _observed_profile_code(url):
    """Opaque JRA profile token identity; not an officially attested permanent ID."""
    query=parse_qs(urlsplit(url).query)
    tokens=query.get("CNAME",[])
    token=tokens[0] if len(tokens)==1 else ""
    match=re.fullmatch(r"pw01dud00([0-9]{10})/[A-Za-z0-9]{2}",token)
    return match.group(1) if match else None

def _metadata(raw,expected_name):
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    fields={}
    for dt in soup.select("dt"):
        key=dt.get_text(" ",strip=True)
        if key not in ("性別","馬齢","調教師名","父","母","母の父","生年月日","毛色"):
            continue
        dd=dt.find_next_sibling("dd")
        if dd is None:continue
        value=dd.get_text(" ",strip=True)
        if value:
            if key in fields and fields[key]!=value:
                raise G04Rejected("conflicting_profile_metadata:"+key)
            fields[key]=value
    if fields.get("性別") not in ("牡","牝","せん","騸"):
        raise G04Rejected("horse_sex_unverified")
    if not re.fullmatch(r"[0-9]{1,2}歳",fields.get("馬齢","")):
        raise G04Rejected("horse_age_unverified")
    if not fields.get("調教師名"):
        raise G04Rejected("trainer_unverified")
    return {"horse_name":expected_name,"sex":fields["性別"],
            "age_years":int(fields["馬齢"][:-1]),
            "trainer":fields["調教師名"],
            "sire":fields.get("父"),"dam":fields.get("母"),
            "damsire":fields.get("母の父"),
            "date_of_birth":fields.get("生年月日"),
            "coat":fields.get("毛色"),
            "jockey_current":None,"jockey_current_verified":False,
            "jra_horse_id":None,"jra_horse_id_verified":False}

def capture(*,root,day,fetch,clock,allowed=False,allow_partial=False,
            isolate_invalid_links=False):
    """G03 must already be saved/verified; fetch must use existing paced _read.

    Caller is responsible for pacing, no-redirect, bounded GET, and replacing
    the ephemeral directory with the existing encrypted-only artifact.
    """
    if allowed is not True:raise G04Rejected("profile_capture_not_authorized")\n    if type(isolate_invalid_links) is not bool:raise G04Rejected("invalid_link_isolation_mode")
    if type(day) is not str or not re.fullmatch(r"20[0-9]{6}",day):
        raise G04Rejected("bad_race_day")
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise G04Rejected("bad_source_directory")
    if allow_partial:
        from diagnostics.kyoto_g03_independent_partial import verify_partial
        proof=verify_partial(root,expected_day=day)
        selected=proof["verified_race_numbers"]
        if not selected:raise G04Rejected("no_independently_verified_races")
    else:
        try:proof=verify_g03(root,expected_day=day)
        except G03ProofRejected as exc:raise G04Rejected("g03_not_independently_verified") from exc
        if proof["races_verified"]!=12:raise G04Rejected("not_all_12_races")
        selected=list(range(1,13))
    receipt=json.loads((root/"g03_receipt.json").read_text(encoding="utf8"))
    entries=receipt["races"]
    pending=[]
    rejected=[]
    seen=set()
    seen_urls=set()
    for race in selected:
        info=entries[str(race)]
        if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]",info["start_time_jst"]):
            raise G04Rejected("unverified_start_time")
        cutoff=datetime.fromisoformat(f"{day[:4]}-{day[4:6]}-{day[6:]}T{info['start_time_jst']}:00").replace(tzinfo=JST).astimezone(timezone.utc)
        for horse in info["runners"]:
            number=horse["number"];name=horse["name"]
            if type(number) is not int or not 1<=number<=18 or not name:
                raise G04Rejected("invalid_g03_horse_identity")
            key=(race,number)
            if key in seen:raise G04Rejected("duplicate_runner")
            seen.add(key)
            try:
                url=trusted_url(horse["profile_navigation"])
                if isolate_invalid_links and url in seen_urls:
                    raise G04Rejected("duplicate_profile_url_identity")
            except (PlanningError,G04Rejected,ValueError,TypeError,KeyError) as exc:
                if not isolate_invalid_links:
                    raise
                rejected.append({"race":race,"horse_number":number,"horse_name":name,
                    "source_url":None,"source_kind":"JRA_PC_OBSERVED_RACECARD_PROFILE_LINK",
                    "observed_profile_code":None,"observed_profile_code_attested_as_permanent_id":False,
                    "current_jockey":horse.get("current_jockey"),
                    "current_jockey_source_verified":False,
                    "current_assigned_weight_kg":horse.get("assigned_weight_kg"),
                    "race_cutoff_utc":cutoff.isoformat(),
                    "raw_original_file":None,"state":"INVALID_OR_DUPLICATE_PROFILE_NAVIGATION",
                    "profile_verified":False,"prediction_ready":False,"training_ready":False,
                    "failure_class":type(exc).__name__,
                    "failure_reason":"invalid_or_duplicate_official_profile_navigation"})
                continue
            seen_urls.add(url)
            pending.append((race,number,name,url,cutoff,horse.get("current_jockey"),horse.get("assigned_weight_kg")))
    if not 2<=len(pending)+len(rejected)<=MAX_HORSES:raise G04Rejected("runner_volume_invalid")
    urls=[item[3] for item in pending]
    if len(urls)!=len(set(urls)):raise G04Rejected("duplicate_profile_url_identity")
    if (root/"g04_receipt.json").exists():
        raise G04Rejected("g04_receipt_already_exists")
    results=[]
    for race,number,name,url,cutoff,current_jockey,assigned_weight in pending:
        original_name=f"g04_profile_r{race:02d}_h{number:02d}.html"
        item={"race":race,"horse_number":number,"horse_name":name,
              "source_url":url,"source_kind":"JRA_PC_OBSERVED_RACECARD_PROFILE_LINK",
              "observed_profile_code":_observed_profile_code(url),
              "observed_profile_code_attested_as_permanent_id":False,
              "current_jockey":current_jockey if isinstance(current_jockey,str) else None,
              "current_jockey_source_verified":bool(current_jockey and isinstance(current_jockey,str)),
              "current_assigned_weight_kg":assigned_weight,
              "race_cutoff_utc":cutoff.isoformat(),"raw_original_file":original_name,
              "state":"NOT_FETCHED","profile_verified":False,
              "current_jockey_verified":bool(current_jockey and isinstance(current_jockey,str)),
              "prediction_ready":False,"training_ready":False}
        try:
            before=_utc(clock())
            if before>=cutoff:raise G04Rejected("already_after_race_start")
            raw=fetch(url)
            after=_utc(clock())
            if type(raw) is not bytes or not 0<len(raw)<=MAX_PROFILE:
                raise G04Rejected("profile_http_original_invalid")
            destination=root/original_name
            if destination.exists() or destination.is_symlink():
                raise G04Rejected("profile_original_name_collision")
            destination.write_bytes(raw)
            item["source_sha256"]=hashlib.sha256(raw).hexdigest()
            item["source_bytes"]=len(raw)
            item["captured_at_utc"]=after.isoformat()
            if after>=cutoff:raise G04Rejected("response_after_race_start")
            parsed=parse_horse_history(raw,source_url=url,fetched_at_utc=after,
                prediction_cutoff_utc=cutoff,target_date=date.fromisoformat(
                    f"{day[:4]}-{day[4:6]}-{day[6:]}"),
                expected_horse_name=name,allow_verified_no_history=True)
            if parsed["invalid_rows"]:
                raise G04Rejected("history_rows_unresolved")
            features=_metadata(raw,name)
            parsed_file=f"g04_profile_r{race:02d}_h{number:02d}_parsed.json"
            detail={"schema":"kyoto_g04_individual_prior_form.v1",
                    "race":race,"horse_number":number,"horse_name":name,
                    "source_sha256":item["source_sha256"],"captured_at_utc":item["captured_at_utc"],
                    "source_url":url,"race_cutoff_utc":cutoff.isoformat(),
                    "demographics":features,"prior_rows":parsed["prior_rows"],
                    "nonfinish_rows":parsed["nonfinish_rows"],
                    "administrative_events":parsed["administrative_events"],
                    "excluded_rows":parsed["excluded_rows"],"history_status":parsed["history_status"],
                    "prediction_ready":False,"training_ready":False}
            (root/parsed_file).write_text(
                json.dumps(detail,ensure_ascii=False,sort_keys=True,indent=2)+"\\n",encoding="utf8")
            item.update(state="PROFILE_AND_PRIOR_FORM_VERIFIED_OFFLINE",
                profile_verified=True,
                demographics=features,
                parsed_file=parsed_file,
                prior_finish_count=len(parsed["prior_rows"]),
                most_recent_prior_jockey=next((row.get("jockey") for row in parsed["prior_rows"] if row.get("jockey")),None),
                nonfinish_count=len(parsed["nonfinish_rows"]),
                administrative_event_count=len(parsed["administrative_events"]),
                excluded_row_count=len(parsed["excluded_rows"]),
                history_status=parsed["history_status"])
        except Exception as exc:
            item.update(state="SOURCE_OR_PARSE_FAILED",failure_class=type(exc).__name__,
                        failure_reason=str(exc)[:130])
        results.append(item)
    results.extend(rejected)
    results.sort(key=lambda p:(p["race"],p["horse_number"]))
    missing=[{"race":p["race"],"horse_number":p["horse_number"],"reason":p.get("failure_reason")}
             for p in results if not p["profile_verified"]]
    report={"schema":"kyoto_g04_all_horses.v1","day":day,
            "verified_g03_races":len(selected),"selected_races":selected,
            "partial_g03_source":len(selected)!=12,"expected_horses":len(pending)+len(rejected),
            "profile_verified_count":sum(bool(p["profile_verified"]) for p in results),
            "invalid_profile_navigation_count":len(rejected),
            "missing_profiles":missing,
            "all_profiles_parsed":not missing and len(selected)==12,
            "current_jockey_verified_for_all":all(p["current_jockey_source_verified"] for p in results),
            "jra_permanent_ids_verified_for_all":False,
            "observed_profile_codes_extracted":sum(bool(p.get("observed_profile_code")) for p in results),
            "prediction_ready":False,"training_ready":False,
            "profiles":results}
    (root/"g04_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    return report
