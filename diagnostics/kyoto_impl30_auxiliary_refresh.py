"""Afternoon-only supplementary racecard/track acquisition.

Existing morning 8 slots, PC/SP collector and database remain unchanged.
Only observed current-day official links. Previously authenticated schedule
evidence prioritizes races approaching start; missing schedule is not a veto.
No profile or historical-result re-fetch. Encrypted originals, not model inputs.
"""
import argparse,json,os,re,tempfile,time,subprocess
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import build_opener,HTTPCookieProcessor
from http.cookiejar import CookieJar
from diagnostics.kyoto_nov15_two_original_observer import SOURCE,_read,NoRedirect
from diagnostics.jra_official_link_repair import unique_observed
from diagnostics.jra_one_shot_market_capture import RequestPacer
from diagnostics.kyoto_g03_all_races import links,acquire_all
from diagnostics.kyoto_g03_independent_partial import verify_partial
from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
from diagnostics.kyoto_g05_conditions import compile_saved
from diagnostics.kyoto_g05_official_track import capture_kyoto_track
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence,decrypt_evidence
from diagnostics.kyoto_impl25_c12_all_runs_handoff import WEEKENDS,_date,_gh,_download
from diagnostics.kyoto_g04_all_horse_profiles import _utc

DAYS=("20261128","20261129")
WORKFLOW="kyoto-20261128-29-auxiliary-refresh.yml"
NAME="Kyoto Nov28-29 afternoon auxiliary refresh"

def prior_starts(day,repo,key):
    workflow,file,_=WEEKENDS[day]
    found={};conflicts=set()
    deadline=time.monotonic()+45
    def remaining(cap):
        budget=deadline-time.monotonic()
        if budget<=0:raise TimeoutError("prior_archive_budget")
        return min(cap,budget)
    def api(endpoint):
        return json.loads(subprocess.check_output(["gh","api",endpoint],text=True,stderr=subprocess.DEVNULL,timeout=remaining(8)))
    try:
        index=api(f"repos/{repo}/actions/workflows/{file}/runs?created={_date(day)}&per_page=100")
        runs=index["workflow_runs"]
        if index["total_count"]!=len(runs) or len(runs)>100:return {}
        for run in sorted(runs,key=lambda x:x["id"],reverse=True):
            if time.monotonic()>=deadline:break
            if run["name"]!=workflow or run["created_at"][:10]!=_date(day) or run["status"]!="completed" or run["event"] not in ("schedule","workflow_dispatch"):continue
            rid=run["id"]
            try:
                with tempfile.TemporaryDirectory(prefix="kyoto_aux_prior_") as tmp:
                    base=Path(tmp);cipher=base/"cipher";cipher.mkdir();raw=base/"raw"
                    subprocess.run(["gh","run","download",str(rid),"--repo",repo,"--name",f"kyoto-pc-{rid}-{day}","--dir",str(cipher)],
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=remaining(20))
                    decrypt_evidence(cipher,raw,key_hex=key,repo=repo,run_id=str(rid))
                    verified=verify_partial(raw,expected_day=day)["verified_race_numbers"]
                    records=records_from_g03(raw,day=day,skip_invalid_races=True)
                    for race in verified:
                        item=records[race]
                        if not item:continue
                        start=item["verified_start_utc"]
                        if race in found and found[race]!=start:conflicts.add(race)
                        else:found[race]=start
                    if len(found)==12:break
            except Exception:continue
    except Exception:return {}
    return {r:s for r,s in found.items() if r not in conflicts}

def targets(observed,starts,now,*,horizon_minutes=75):
    # Exact start times, not assumed race numbers. Unknown times may be
    # inspected once from the observed current-day page; no promotion after start.
    return [race for race in sorted(observed,key=lambda r:(starts.get(r,"9999"),r))
            if race not in starts or now<_utc(starts[race])<=now+timedelta(minutes=horizon_minutes)]

def collect(root,*,day,starts,fetch,clock):
    root=Path(root);root.mkdir()
    report={"schema":"kyoto_impl30_auxiliary_refresh.v1","day":day,"source_only":True,
            "prediction_ready":False,"target_races":[],"verified_races":[]}
    try:
        selection=fetch(SOURCE)
        (root/"official_selection.html").write_bytes(selection)
        meeting_url=unique_observed(selection,SOURCE,lambda label,token: "京都" in label and day in token)
        meeting=fetch(meeting_url)
        observed=links(meeting,meeting_url,day)
        chosen=targets(observed,starts,_utc(clock()))
        report["target_races"]=chosen
        reverse={url:race for race,url in observed.items()}
        def selected_fetch(url):
            r=reverse[url]
            if r not in chosen:raise ValueError("NOT_IN_CURRENT_REFRESH_WINDOW")
            if r in starts and _utc(clock())>=_utc(starts[r]):raise ValueError("START_ALREADY_PASSED")
            return fetch(url)
        stage=root/"g03_tmp"
        try:
            acquire_all(day=day,root=stage,meeting_raw=meeting,meeting_url=meeting_url,
                        fetch=selected_fetch,captured_at_utc=clock,allowed=True,
                        race_order=chosen+[n for n in range(1,13) if n not in chosen])
        finally:
            if stage.is_dir():
                for p in stage.iterdir():
                    name=p.name if p.name in ("official_meeting.html","g03_receipt.json") else "g03_"+p.name
                    p.rename(root/name)
                stage.rmdir()
        report["verified_races"]=verify_partial(root,expected_day=day)["verified_race_numbers"]
        if report["verified_races"]:
            conditions=compile_saved(root,day=day,allow_partial=True)
            report["observed_field_values"]=conditions["observed_field_values"]
    except Exception as exc:
        report["racecard_error_class"]=type(exc).__name__
    try:
        track=capture_kyoto_track(root,day,fetch,clock,allowed=True)
        report["track_state"]=track["state"]
    except Exception as exc:report["track_error_class"]=type(exc).__name__
    (root/"receipt.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument("--day",required=True,choices=DAYS);p.add_argument("--out",required=True,type=Path);a=p.parse_args()
    day=a.day;repo=os.environ["GITHUB_REPOSITORY"];rid=os.environ["GITHUB_RUN_ID"];key=os.environ["ARCHIVE_KEY"]
    now=lambda:datetime.now(timezone.utc)
    def within():
        t=now()
        return t.strftime("%Y%m%d")==day and 3<=t.hour<8
    if os.environ.get("KYOTO_TARGET_DAY")!=day or os.environ.get("KYOTO_AUX_HTTP_APPROVED")!="YES" or os.environ.get("GITHUB_EVENT_NAME") not in ("schedule","workflow_dispatch") or not re.fullmatch(r"[a-fA-F0-9]{64}",key) or not within():
        raise ValueError("auxiliary_live_window_or_authorization")
    # Use the latest authenticated morning slot, but do not block live work
    # merely because it was not available. All HTTP still follows fresh links.
    starts=prior_starts(day,repo,key)
    client=build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
    pacer=RequestPacer(min_gap_seconds=2.0);count=0;refused=False;end=time.monotonic()+180
    def fetch(url):
        nonlocal count,refused
        if refused or not within() or count>=15 or time.monotonic()>=end:raise ValueError("auxiliary_request_budget_or_refusal")
        pacer.before_request();count+=1
        try:return _read(client,url)
        except HTTPError as exc:
            if exc.code in (401,403,429):refused=True
            raise
        except ValueError:
            refused=True
            raise
    with tempfile.TemporaryDirectory(prefix="kyoto_aux_refresh_") as d:
        root=Path(d)/"raw";report=collect(root,day=day,starts=starts,fetch=fetch,clock=lambda:now().isoformat())
        encrypt_evidence(root,a.out,key_hex=key,repo=repo,run_id=rid)
    print(json.dumps({"verified_races":report["verified_races"],"observed_field_values":report.get("observed_field_values",0),"http_requests":count,"source_only":True},sort_keys=True))

def saved_slots(day,repo,key):
    """Re-open encrypted afternoon artifacts; preserve errors and morning data."""
    from diagnostics.kyoto_impl30_day_coverage import extract_slot
    slots=[];errors=[]
    try:
        index=_gh(f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?created={_date(day)}&per_page=100")
        runs=index["workflow_runs"]
        if index["total_count"]!=len(runs) or len(runs)>100:raise ValueError("auxiliary_run_index_incomplete")
        seen=set()
        for run in sorted(runs,key=lambda r:r["id"]):
            rid=run["id"]
            if rid in seen:raise ValueError("duplicate_auxiliary_run")
            seen.add(rid)
            if run["name"]!=NAME or run["created_at"][:10]!=_date(day) or run["status"]!="completed" or run["event"] not in ("schedule","workflow_dispatch"):continue
            try:
                with tempfile.TemporaryDirectory(prefix="kyoto_aux_read_") as d:
                    base=Path(d);cipher=base/"cipher";cipher.mkdir();raw=base/"raw"
                    _download(rid,f"kyoto-auxiliary-{rid}-{day}",cipher,repo)
                    decrypt_evidence(cipher,raw,key_hex=key,repo=repo,run_id=str(rid))
                    receipt=json.loads((raw/"receipt.json").read_text())
                    if receipt.get("day")!=day or receipt.get("schema")!="kyoto_impl30_auxiliary_refresh.v1":raise ValueError("auxiliary_identity")
                    slots.append(extract_slot(raw,day,rid))
            except Exception as exc:errors.append({"run_id":rid,"error_class":type(exc).__name__})
    except Exception as exc:errors.append({"error_class":type(exc).__name__})
    return slots,errors

if __name__=="__main__":main()

