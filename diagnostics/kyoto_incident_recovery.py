"""Read-only incident evidence and reproducible repair worklist, not a success tally.

Trusted checkout only. Source archives are authenticated by the existing reader.
No original plaintext, credentials, URL, token or arbitrary exception text is
published. Receipt observations do not certify JRA provenance or model readiness.
"""
import argparse, hashlib, importlib.util, json, os, re, subprocess, tempfile
from pathlib import Path
from datetime import datetime, timezone
from diagnostics.kyoto_job_artifact_state import classify_artifact, SKIPPED

REPO="papaneko-ai/kyoto-keiba-ai"
DAYS=("20261128","20261129")
PATH_PREFIX=".github/workflows/kyoto-20261128-29-"
KINDS={"two-source-production-observer.yml":("pc","sp"),
       "auxiliary-refresh.yml":("auxiliary",),"postrace-evidence.yml":("postrace",),
       "workout-source.yml":("workout",),"cushion-source.yml":("cushion",)}
READER_SHA="39b9d79c39b986b1b01775957e6a6f93adc29dbc"
CUSHION_SHA="47cd7f9e881aa989b9f932373cfaf5278dea223a"
SAFE_KEYS={"state","status","error","error_class","error_code","failure_class","failure_reason","reason","message",
           "sp_market_state","transport_stop_reason","racecard_error_class","track_error_class",
           "results_meeting_state","payout_meeting_state","candidate_count","racecard_fetched",
           "network_requests_started","http_requests_started","verified_races","expected_horses",
           "profile_verified_count","g03_verified_races","g04_verified_profiles","g05_bound_races",
           "g06_paired_market_races_locally_verified","official_horses","covered_horses","records",
           "source_requests","request_count","race","horse_number","profile_verified","complete",
           "all_profiles_parsed","request_method"}
REPAIR={
 "PC_ENTRY":("REPLAY_SAVED_SELECTION_OR_HTTP_BOUNDARY","FIX_OBSERVED_PUBLIC_NAVIGATION","TEST_ACTUAL_FORM_AND_REFUSAL_BOUNDARY"),
 "PC_MEETING":("REPLAY_EXACT_SELECTION_HTML","FIX_OBSERVED_MEETING_ACTION","TEST_DAY_AND_MEETING_IDENTITY"),
 "G03":("REPLAY_SAME_RACE_SAVED_HTML_AND_ROSTER","FIX_LINK_OR_ROSTER_PARSER","TEST_12_RACES_AND_CANCELLED_RUNNERS"),
 "G04":("REPLAY_EXACT_PROFILE_LINK_AND_SAVED_PROFILE","FIX_NAVIGATION_OR_PRIOR_FORM_PARSE","TEST_PER_HORSE_ID_TIME_AND_MISSING"),
 "G05":("REPLAY_CARD_AND_TRACK_MEASUREMENT","FIX_FIELD_IDENTITY_OR_PUBLICATION_TIME","TEST_SAME_DAY_TRACK_AND_UNKNOWN_FIELDS"),
 "G06":("REPLAY_EACH_MARKET_RAW_AND_REGISTERED_ROSTER","FIX_MARKET_NAVIGATION_OR_MATRIX_PARSE","TEST_BOTH_MARKETS_PRESTART_CANCELLATION"),
 "SP_DISCOVERY":("REPLAY_SAVED_SP_NAVIGATION_AND_FORMS","FIX_INDEPENDENT_OBSERVED_ACTION","TEST_ALL_12_LINKS_WITHOUT_PC_TOKEN"),
 "SP_CAPTURE":("REPLAY_PER_RACE_SP_RECEIPT_AND_ORIGINALS","FIX_RACE_OR_MARKET_CAPTURE","TEST_INDEPENDENT_ROSTER_AND_BOTH_MARKETS"),
 "AUXILIARY":("REPLAY_AUXILIARY_RECEIPT_AND_ORIGINALS","FIX_OBSERVED_NAVIGATION_OR_FIELD_PARSE","TEST_TRACK_RESERVE_AND_PARTIAL_SUCCESS"),
 "POSTRACE":("REPLAY_RESULT_PAYOUT_ORIGINALS_AND_MENU","FIX_OBSERVED_POSTRACE_CHAIN_OR_RECONCILIATION","TEST_12_RACES_REFUNDS_TIES_CORRECTIONS"),
 "WORKOUT":("REPLAY_AUTHENTICATED_WORKOUT_AND_ROSTER_JOIN","FIX_MISSING_SOURCE_OR_IDENTITY_MATCH","TEST_PER_HORSE_COVERAGE_AND_CLOCK"),
 "CUSHION":("REPLAY_SAVED_CUSHION_ORIGINAL_AND_HEADING","FIX_DATE_MEASUREMENT_OR_PUBLICATION_PARSE","TEST_SAME_DAY_VALUES_AND_STALE_REJECTION"),
 "ARCHIVE":("CHECK_EXACT_JOB_STEP_AND_ARTIFACT_ID","FIX_SEAL_OR_UPLOAD_OR_RUNNER_FAILURE","TEST_INTERRUPTED_CAPTURE_RECOVERY"),
}
def canonical(x):
    return json.dumps(x,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def digest(x):return hashlib.sha256(x).hexdigest()
def label(x):
    if not isinstance(x,str):return "UNKNOWN"
    if re.fullmatch(r"(?:[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+|[a-z][a-z0-9]*(?:_[a-z0-9]+)+|[A-Za-z]{1,60}(?:Error|Rejected|Exception)|GET|POST|FAILED|STARTED|DEADLINE)",x) and len(x)<=120:
        return x
    m=re.fullmatch(r"HTTP Error ([1-5][0-9]{2})(?::[^\r\n]*)?",x)
    return "HTTP_STATUS_"+m.group(1) if m else "UNCLASSIFIED_TEXT_SHA256_"+digest(x.encode())[:16]
def small(x):
    if type(x) is bool:return x
    if type(x) is int and 0<=x<=1000000:return x
    if isinstance(x,str):return label(x)
    if isinstance(x,list) and len(x)<=12 and all(type(n) is int and 1<=n<=12 for n in x):return x
    return None
def fields(row):
    return {k:small(v) for k,v in sorted(row.items()) if k in SAFE_KEYS and small(v) is not None} if isinstance(row,dict) else {}
def stamp(x):
    try:
        t=datetime.fromisoformat(x.replace("Z","+00:00"))
        if t.utcoffset()==timezone.utc.utcoffset(None):return t.isoformat()
    except (AttributeError,ValueError,TypeError):pass
    return None
def load(root,name):
    p=root/name
    if not p.is_file() or p.is_symlink() or not 0<p.stat().st_size<=1_500_000:return {}
    try:
        d=json.loads(p.read_bytes())
        return d if isinstance(d,dict) else {}
    except (ValueError,OSError):return {}
def inventory(root):
    rows={}
    for p in sorted(root.iterdir()):
        if p.is_file() and not p.is_symlink() and re.fullmatch(r"[A-Za-z0-9_.-]{1,110}",p.name) and p.stat().st_size<=75_000_000:
            rows[p.name]={"sha256":digest(p.read_bytes()),"bytes":p.stat().st_size}
    post=load(root,"source_verification.json")
    for row in post.get("source_rows",[]):
        if isinstance(row,dict) and row.get("filename") in rows and rows[row["filename"]]["sha256"]==row.get("sha256"):
            utc=stamp(row.get("captured_at_utc"))
            if utc:rows[row["filename"]]["receipt_utc"]=utc
    return rows
def inspect_source(root,day,lane):
    root=Path(root);files=inventory(root);receipt=load(root,"receipt.json")
    if receipt.get("day")!=day:raise ValueError("receipt_day_mismatch")
    stages=[];incidents=[]
    def stage(name,observed,detail=None,code=None,blocked=None,evidence=()):
        detail=detail or {};ev=[n for n in evidence if n in files]
        state="OBSERVED_NOT_CERTIFIED" if observed else "BLOCKED_BY_UPSTREAM" if blocked else "GAP_REQUIRES_DIAGNOSIS"
        row={"stage":name,"state":state,"observations":detail,"evidence_files":ev}
        stages.append(row)
        if not observed:
            signature={"stage":name,"code":code or "UNKNOWN","blocked_by":blocked}
            checks=REPAIR[name]
            incidents.append({**signature,"signature_sha256":digest(canonical(signature)),
                "cause_status":"DIRECT_FAILURE_SIGNATURE_OBSERVED" if code else "ROOT_CAUSE_NOT_YET_PROVED",
                "root_cause_closed":False,"diagnostic_action":checks[0],"repair_direction":checks[1],
                "required_regression":checks[2],"evidence_files":ev,
                "closure_requires":["REPRODUCE_FROM_EXACT_EVIDENCE","ISOLATED_PATCH","REGRESSION_PASS","INDEPENDENT_DEPLOYMENT_RECHECK"],
                "blocked_by":blocked})
    def rows(doc):
        rr=doc.get("races",{})
        if isinstance(rr,dict):return {str(n):fields(rr.get(str(n),{})) for n in range(1,13)}
        if isinstance(rr,list):return {str(r["race"]):fields(r) for r in rr if isinstance(r,dict) and type(r.get("race")) is int and 1<=r["race"]<=12}
        return {}
    def code(d):
        for k in ("error_code","error_class","failure_reason","reason","error"):
            if isinstance(d.get(k),str):return label(d[k])
        return None
    if receipt.get("schema")=="kyoto_archive_salvage.v1":
        saved=receipt.get("saved_originals")
        rejected=receipt.get("rejected_members")
        valid=isinstance(saved,dict) and bool(saved) and set(saved)==set(files)-{"receipt.json"} and all(isinstance(v,dict) and files[n].get("sha256")==v.get("sha256") and files[n].get("bytes")==v.get("bytes") for n,v in saved.items())
        valid=valid and isinstance(rejected,list) and len(rejected)<=900 and all(isinstance(v,dict) and re.fullmatch(r"[0-9a-f]{64}",v.get("path_sha256","")) and v.get("reason") in {"NONREGULAR","UNRECOGNIZED","SYMLINK","UNSAFE_G06_MEMBER","UNKNOWN_STAGE","UNRECOGNIZED_DISCOVERY","COLLISION","UNREADABLE_OR_OVERSIZE","INVALID_G06_BUNDLE","G06_DUPLICATE_STAGE","UNREADABLE_G06_MEMBER","G06_BUNDLE_UNVERIFIED"} for v in rejected)
        stage("ARCHIVE",False,{"roundtrip_receipt_matches_originals":bool(valid),"saved_member_count":len(saved) if isinstance(saved,dict) else None,"rejected_members":rejected if valid else [],"source_credit":False},code="STRICT_ARCHIVE_REJECTED_PARTIAL_RECOVERY" if valid else "SALVAGE_RECEIPT_MISMATCH",evidence=tuple(files))
    if lane=="pc":
        selection="official_selection.html" in files
        meeting="official_meeting.html" in files
        stage("PC_ENTRY",selection,fields(receipt),code(receipt) if not selection else None,
              evidence=("receipt.json","observer_partial_receipt.json","official_pc_navigation_home.html","official_selection.html"))
        stage("PC_MEETING",meeting,fields(receipt),code(receipt) if selection and not meeting else None,
              blocked="PC_ENTRY" if not selection else None,evidence=("receipt.json","official_selection.html","official_meeting.html"))
        g03=load(root,"g03_receipt.json");r03=rows(g03)
        good03=[n for n,r in r03.items() if r.get("state") in ("ROSTER_AND_START_VERIFIED_OFFLINE","ROSTER_START_VERIFIED_OFFLINE") and f"g03_official_racecard_{int(n):02d}.html" in files]
        stage("G03",len(good03)==12,{"verified_claims":good03,"race_states":r03},blocked="PC_MEETING" if not meeting else None,evidence=("g03_receipt.json","g03_official_meeting.html"))
        g04=load(root,"g04_receipt.json");missing=[]
        for r in g04.get("profiles",[]):
            if isinstance(r,dict) and r.get("profile_verified") is not True:missing.append(fields(r))
        stage("G04",g04.get("all_profiles_parsed") is True and len(good03)==12 and not missing,{"counts":fields(g04),"missing_profiles":missing[:216]},blocked="G03" if not good03 else None,evidence=("g04_receipt.json",))
        g05=load(root,"g05_receipt.json");track=load(root,"g05_track_receipt.json")
        stage("G05",bool(g05) and bool(track) and "g05_official_kyoto_track.html" in files,{"conditions":fields(g05),"track":fields(track),"track_independent_of_g03":True},code(track),evidence=("g05_receipt.json","g05_track_receipt.json","g05_official_kyoto_track.html"))
        c11=load(root,"c11_per_family_source_proof.json");market={}
        for n,v in c11.get("races",{}).items():
            if str(n) in {str(k) for k in range(1,13)} and isinstance(v,dict):market[str(n)]=fields(v.get("g06",{}))
        stage("G06",c11.get("g06_paired_market_races_locally_verified")==12 and "g06_source_bundle.tar.gz" in files,{"counts":fields(c11),"race_states":market},blocked="G03" if not good03 else None,evidence=("c11_per_family_source_proof.json","g06_source_bundle.tar.gz"))
    elif lane=="sp":
        d=load(root,"sp_discovery_receipt.json")
        candidates=d.get("per_race_observed_navigation_candidates",{})
        counts={str(n):small(candidates.get(str(n),{}).get("candidate_count")) for n in range(1,13)} if isinstance(candidates,dict) else {}
        attempts=[fields(x) for x in d.get("attempts",[]) if isinstance(x,dict)][:12]
        signature=None;post_entry=False
        if counts and all(v==0 for v in counts.values()):
            from bs4 import BeautifulSoup
            for n in files:
                if re.fullmatch(r"official_sp_discovery_[1-6]\.html",n):
                    soup=BeautifulSoup((root/n).read_bytes(),"html.parser")
                    for a in soup.select("a[onclick]"):
                        if re.fullmatch(r"\s*(?:return\s+)?doAction\(\s*['\"]/JRADB/accessD\.html['\"]\s*,\s*['\"]sw01dli00/[A-Za-z0-9]{2}['\"]\s*\)\s*;?\s*",a["onclick"]) and "出馬表" in a.get_text():
                            post_entry=True
            if post_entry and not any(a.get("request_method")=="POST" for a in attempts):
                signature="OBSERVED_POST_ENTRY_NO_POST_ATTEMPT"
        stage("SP_DISCOVERY",len(counts)==12 and all(v==1 for v in counts.values()),{"candidate_counts":counts,"attempts":attempts,"observed_post_entry":post_entry},signature or code(d),evidence=("sp_discovery_receipt.json",)+tuple(n for n in files if n.startswith("official_sp_discovery_")))
        m=load(root,"sp_all12_receipt.json");r=rows(m)
        both={str(n):all(f"r{n:02d}_{s}" in files for s in ("official_sp_racecard.html","official_sp_quinella_odds.html","official_sp_bracket_quinella_odds.html")) for n in range(1,13)}
        stage("SP_CAPTURE",all(both.values()),{"race_states":r,"all_three_originals_present":both},blocked="SP_DISCOVERY" if not any(v==1 for v in counts.values()) else None,evidence=("sp_all12_receipt.json",))
    elif lane=="auxiliary":
        stage("AUXILIARY",bool(receipt.get("verified_races")) and "g05_track_receipt.json" in files,fields(receipt),code(receipt),evidence=("receipt.json","g03_receipt.json","g05_receipt.json","g05_track_receipt.json"))
    elif lane=="postrace":
        r=rows(receipt)
        present={str(n):f"r{n:02d}_result.html" in files for n in range(1,13)}
        reconciliation={str(n):fields(receipt.get("races",{}).get(str(n),{}).get("independent_reconciliation",{})) for n in range(1,13)}
        stage("POSTRACE",all(present.values()) and "payout_meeting.html" in files and all(x.get("state")=="DUAL_PAGE_EXPLICIT_FINAL" for x in reconciliation.values()),{"receipt":fields(receipt),"raw_results_present":present,"race_states":r,"reconciliation":reconciliation},code(receipt),evidence=("receipt.json","postrace_seed.html","results_menu.html","results_meeting.html","payout_menu.html","payout_meeting.html","postrace_revision_history.json"))
    elif lane=="cushion":
        stage("CUSHION",receipt.get("state")=="OFFICIAL_ORIGINAL_PARSED" and "g05_official_cushion_fragment.html" in files,fields(receipt),code(receipt),evidence=("receipt.json","g05_official_cushion_fragment.html"))
    else:raise ValueError("unsupported_lane")
    return {"ciphertext_authenticated":True,"receipt_state":fields(receipt),"files":files,"stages":stages,"incidents":incidents,
            "source_claims_independently_certified":False}
def replay_adaptive(root,day,lane,repair):
    """Re-open original bytes, search candidates and compare any applied proof.
    
    No network; no claims of root-cause closure or future live success.
    Record even rejected searches so unknown structure does not disappear.
    """
    root=Path(root);receipt=load(root,"receipt.json");tasks=[]
    if lane in ("pc","auxiliary"):
        claims=receipt.get("adaptive_navigation_repairs",[])
        if not isinstance(claims,list):raise ValueError("repair_claims_invalid")
        if any(not isinstance(x,dict) or x.get("stage") not in ("entry","meeting") for x in claims) or len({x["stage"] for x in claims})!=len(claims):
            raise ValueError("repair_claims_ambiguous")
        for stage,name,next_name in (("entry","official_pc_navigation_home.html","official_selection.html"),("meeting","official_selection.html","official_meeting.html")):
            claim=next((x for x in claims if x["stage"]==stage),None)
            if claim is not None or (root/name).is_file() and not (root/next_name).is_file():tasks.append((stage,name,"PC",claim))
    elif lane=="sp":
        discovery=load(root,"sp_discovery_receipt.json")
        counts=discovery.get("per_race_observed_navigation_candidates",{})
        incomplete=not isinstance(counts,dict) or not all(isinstance(counts.get(str(n)),dict) and counts[str(n)].get("candidate_count")==1 for n in range(1,13))
        for row in discovery.get("attempts",[])[:6]:
            if not isinstance(row,dict):continue
            name=row.get("file","")
            if not re.fullmatch(r"official_sp_discovery_[1-6]\.html",name):continue
            claim=row.get("adaptive_navigation_repair")
            if claim is not None or incomplete:
                tasks.append(("entry" if row.get("url")=="https://sp.jra.jp/" else "meeting",name,"SP",claim))
    result=[]
    for stage,name,channel,claim in tasks:
        row={"stage":stage,"file":name,"channel":channel,"recorded_repair":claim is not None,"root_cause_closed":False}
        try:
            p=root/name
            if not p.is_file() or p.is_symlink() or not 0<p.stat().st_size<=1_500_000:raise ValueError("repair_original_missing")
            raw=p.read_bytes();row["source_sha256"]=digest(raw)
            _,_,_,proof=repair(raw,day,channel,stage)
            if proof.get("source_sha256")!=row["source_sha256"] or proof.get("stage")!=stage or proof.get("channel")!=channel or proof.get("day")!=day or proof.get("parser_agreement") is not True or proof.get("counterexamples_rejected") is not True:
                raise ValueError("repair_proof_identity_mismatch")
            if claim is not None and proof!=claim:
                row["state"]="RECORDED_REPAIR_MISMATCH"
            else:
                row.update(state="APPLIED_REPAIR_REPRODUCED" if claim is not None else "LOCAL_CANDIDATE_VERIFIED_NOT_APPLIED",rule_sha256=proof["rule_sha256"],action_sha256=proof["action_sha256"],rule=proof["rule"])
        except Exception as exc:
            row.update(state="REPAIR_SEARCH_UNRESOLVED",error_code=label(str(exc)),error_class=label(type(exc).__name__))
        result.append(row)
    return result

def workout(root,day,rid,key):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    root=Path(root);d=load(root,"receipt.json")
    if d.get("day")!=day or str(d.get("run_id"))!=str(rid):raise ValueError("workout_identity_mismatch")
    if not re.fullmatch(r"[a-fA-F0-9]{64}",key):raise ValueError("archive_key_invalid")
    aes=AESGCM(bytes.fromhex(key));proof=[];bad=[]
    for i,m in enumerate(d.get("snapshots",[])[:300]):
        try:
            p=root/f"source_{i:03d}.aesgcm"
            if p.is_symlink() or not 0<p.stat().st_size<=4_000_000:raise ValueError()
            blob=p.read_bytes();aad=f"kyoto-workout-runtime-v1|{REPO}|{rid}|{day}|{i}".encode()
            if m["archive_aad"].encode()!=aad or digest(blob)!=m["ciphertext_sha256"]:raise ValueError()
            raw=aes.decrypt(blob[:12],blob[12:],aad)
            if digest(raw)!=m["source_sha256"]:raise ValueError()
            proof.append({"index":i,"race":small(m.get("race")),"sha256":digest(raw),"utc":stamp(m.get("captured_utc"))})
        except Exception:bad.append(i)
    rows=[fields(r) for r in d.get("races",[])[:12] if isinstance(r,dict)]
    incomplete=[r for r in rows if r.get("status")!="SOURCE_JOINED" or r.get("covered_horses")!=r.get("official_horses")]
    gap=bool(bad or incomplete or len(rows)!=12 or not proof)
    return {"ciphertext_authenticated":bool(proof) and not bad,"receipt_sha256":digest((root/"receipt.json").read_bytes()),
        "authenticated_snapshots":proof,"rejected_snapshot_indices":bad,"race_receipt_claims":rows,
        "incidents":[{"stage":"WORKOUT","cause_status":"ROOT_CAUSE_NOT_YET_PROVED","code":"WORKOUT_COVERAGE_OR_AUTHENTICATION_GAP","root_cause_closed":False,
            "diagnostic_action":REPAIR["WORKOUT"][0],"repair_direction":REPAIR["WORKOUT"][1],"required_regression":REPAIR["WORKOUT"][2]}] if gap else [],
        "source_claims_independently_certified":False}
def gh(endpoint):
    return json.loads(subprocess.check_output(["gh","api",endpoint],text=True,stderr=subprocess.DEVNULL,timeout=25))
def run_identity(run,rid):
    p=run.get("path","").split("@",1)[0]
    if run.get("id")!=rid or run.get("head_branch")!="main" or run.get("head_repository",{}).get("full_name")!=REPO or run.get("status")!="completed" or run.get("event") not in ("schedule","workflow_dispatch","workflow_run") or not p.startswith(PATH_PREFIX) or p[len(PATH_PREFIX):] not in KINDS:
        raise ValueError("untrusted_run_identity")
    if not re.fullmatch(r"[a-f0-9]{40}",run.get("head_sha","")):raise ValueError("invalid_workflow_head")
    date=str(run.get("created_at",""))[:10].replace("-","")
    lanes=KINDS[p[len(PATH_PREFIX):]]
    if lanes==("workout",):
        allowed_days=tuple(d for d in DAYS if date in (d,str(int(d)-1)))
    else:allowed_days=(date,) if date in DAYS else ()
    if not allowed_days:raise ValueError("wrong_run_day")
    return p,lanes,allowed_days
def safe_jobs(doc):
    rows=doc["jobs"]
    if doc["total_count"]!=len(rows) or len(rows)>100:raise ValueError("job_index_incomplete")
    out=[]
    for j in rows:
        errors=[]
        steps=j.get("steps")
        if steps is not None and not isinstance(steps,list):raise ValueError("invalid_job_steps")
        for s in steps or []:
            if s.get("conclusion") in ("failure","cancelled","timed_out"):
                n=str(s.get("name","")).lower()
                phase="ARCHIVE" if any(k in n for k in ("seal","upload","encrypt")) else "PRE_HTTP" if any(k in n for k in ("verify","checkout","install","guard")) else "CAPTURE_OR_OTHER"
                errors.append({"number":small(s.get("number")),"phase":phase,"conclusion":s["conclusion"]})
        out.append({"job_id":j["id"],"conclusion":j.get("conclusion") if j.get("conclusion") in ("success","failure","cancelled","skipped","timed_out","neutral") else "UNKNOWN","steps_available":steps is not None,"failed_steps":errors})
    return out
def read_aes(reader,cipher,raw,day,rid,key):
    os.environ["KYOTO_TARGET_DAY"]=day
    spec=importlib.util.spec_from_file_location("trusted_archive_reader",Path(reader)/"diagnostics/kyoto_nov15_encrypted_evidence.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.decrypt_evidence(cipher,raw,key_hex=key,repo=REPO,run_id=str(rid))
def diagnose_run(rid,reader,cushion_reader):
    run=gh(f"repos/{REPO}/actions/runs/{rid}")
    path,lanes,days=run_identity(run,rid)
    job_doc=gh(f"repos/{REPO}/actions/runs/{rid}/jobs?per_page=100")
    jobs=safe_jobs(job_doc)
    arts=gh(f"repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100")
    if arts["total_count"]!=len(arts["artifacts"]) or len(arts["artifacts"])>100:raise ValueError("artifact_index_incomplete")
    result={"schema":"kyoto_incident_recovery.v1","repo":REPO,"source_run_id":rid,"workflow_path":path,"workflow_head_sha":run["head_sha"],"event":run["event"],"created_at":stamp(run.get("created_at")),"jobs":jobs,"lanes":{},"new_source_http_requests":0,"automatic_code_promotion":False}
    for lane in lanes:
        matches=[(a,d) for d in days for a in arts["artifacts"] if a.get("name")==f"kyoto-{lane}-{rid}-{d}"]
        found=[(a,d) for a,d in matches if a.get("expired") is False]
        evidence=classify_artifact(path[len(PATH_PREFIX):],lane,rid,[a for a,d in matches],job_doc)
        meta={"artifact_authenticated":False,"artifact_evidence":evidence}
        if evidence["state"]==SKIPPED:
            meta.update(source_acquisition_state="PRODUCER_NOT_EXECUTED_SKIP_REASON_UNVERIFIED",incidents=[])
            result["lanes"][lane]=meta
            continue
        try:
            if len(found)!=1 or len(matches)!=1:raise ValueError("artifact_missing_or_ambiguous")
            a,day=found[0];meta.update(artifact_id=a["id"],target_day=day)
            with tempfile.TemporaryDirectory(prefix="kyoto_incident_") as t:
                root=Path(t);cipher=root/"cipher";cipher.mkdir();raw=root/"raw"
                subprocess.run(["gh","run","download",str(rid),"--repo",REPO,"--name",a["name"],"--dir",str(cipher)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
                key=os.environ.get("ARCHIVE_KEY","")
                if lane=="workout":meta.update(workout(cipher,day,rid,key))
                else:
                    read_aes(cushion_reader if lane=="cushion" else reader,cipher,raw,day,rid,key)
                    meta.update(inspect_source(raw,day,lane))
                    if lane in ("pc","sp","auxiliary"):
                        try:
                            spec=importlib.util.spec_from_file_location("trusted_adaptive_repair",Path(reader)/"diagnostics/kyoto_adaptive_repair.py")
                            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
                            meta["adaptive_repair_replay"]=replay_adaptive(raw,day,lane,mod.recover_action)
                        except Exception as exc:
                            meta["adaptive_repair_replay_error"]=label(type(exc).__name__)
                meta["artifact_authenticated"]=meta.get("ciphertext_authenticated") is True
        except Exception as exc:
            meta.update(error_class=label(type(exc).__name__),error_code=label(str(exc)),incidents=[{"stage":"ARCHIVE","cause_status":"ROOT_CAUSE_NOT_YET_PROVED","root_cause_closed":False,"diagnostic_action":REPAIR["ARCHIVE"][0],"repair_direction":REPAIR["ARCHIVE"][1],"required_regression":REPAIR["ARCHIVE"][2]}])
        result["lanes"][lane]=meta
    return result
def write_report(report,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    data=canonical(report);sha=digest(data);(out/"report.json").write_bytes(data+b"\n")
    rid=report["source_run_id"];marker=f"<!-- kyoto-incident:{rid}:{sha} -->"
    lines=[marker,f"### 自動障害診断 / run {rid}",f"- workflow revision: {report['workflow_head_sha']}",f"- JSON canonical SHA256: {sha}",f"- [実行原本・ログ](https://github.com/{REPO}/actions/runs/{rid})",
           "- 原本は既存暗号化保全。原因が未立証の項目を完了扱いしない。"]
    for lane,m in report["lanes"].items():
        lines.append(f"\n**{lane.upper()}** / artifact {m.get('artifact_id','MISSING')} / authenticated {m.get('artifact_authenticated',False)}")
        for i in m.get("incidents",[]):
            lines.append(f"- {i['stage']} / {i.get('code','UNKNOWN')} / {i['cause_status']} / blocked_by={i.get('blocked_by')}")
            lines.append(f"  - 再現: {i['diagnostic_action']} → 修正: {i['repair_direction']} → 検証: {i['required_regression']}")
        for r in m.get("adaptive_repair_replay",[]):
            lines.append(f"- 自動修復再検証: {r['stage']} / {r['state']} / 原本 {r.get('source_sha256','UNKNOWN')} / 規則 {r.get('rule_sha256','UNKNOWN')} / {r.get('error_code','')}")
        if m.get("adaptive_repair_replay_error"):
            lines.append("- 自動修復再検証自体が失敗: "+m["adaptive_repair_replay_error"])
        if m.get("source_acquisition_state")=="PRODUCER_NOT_EXECUTED_SKIP_REASON_UNVERIFIED":
            lines.append("- 対応取得ジョブはスキップ（理由・正当性は未確認）。取得試行後の原本消失と区別し、取得成功は認定しない。")
        elif not m.get("incidents"):lines.append("- 診断対象の欠落未検出（全取得成功の認定ではない）")
    # The durable comment retains stage worklists plus exact archive references;
    # full per-item evidence stays in the separately uploaded JSON.
    lines.append("\n全項目の証拠・レース別状態・原本ハッシュは同診断実行の report.json。次回前に再現・修正・検証・本番再照合の証拠を追記する。")
    (out/"summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
def main():
    p=argparse.ArgumentParser();p.add_argument("--run-id",type=int,required=True);p.add_argument("--reader",required=True);p.add_argument("--cushion-reader",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    if a.run_id<=0 or os.environ.get("GITHUB_REPOSITORY")!=REPO:raise ValueError("repository_or_run_invalid")
    write_report(diagnose_run(a.run_id,a.reader,a.cushion_reader),a.out)
if __name__=="__main__":main()
