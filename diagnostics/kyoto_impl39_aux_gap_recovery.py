"""Nov29 afternoon recovery of only unresolved prestart market/profile evidence.

Preserve the initial 15-call/180-second refresh, same no-redirect client and
pacer. A separately bounded recovery phase shares refusal state and seals
the original receipt and G06 bundle. No source request in prior-archive replay.
"""
import json,subprocess,tempfile,time
from pathlib import Path
from datetime import timedelta
from urllib.error import HTTPError
from urllib.parse import urlsplit
from diagnostics.kyoto_g04_all_horse_profiles import _utc
from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
from diagnostics.kyoto_impl30_day_coverage import extract_slot
from diagnostics.kyoto_impl30_profile_resume import candidates
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.kyoto_nov15_two_original_observer import _read

DAY="20261129"
REPO="papaneko-ai/kyoto-keiba-ai"
MAX_EXTRA=20
MAX_TOTAL=35
INITIAL_SECONDS=180
TOTAL_SECONDS=300
RECOVERY_SECONDS=120
MARKETS=("quinella","bracket_quinella")
def load_prior(day,repo,key,run_id,*,monotonic=time.monotonic):
    from diagnostics.kyoto_impl25_c12_all_runs_handoff import WEEKENDS,_date,run_name_matches
    from diagnostics.kyoto_impl30_auxiliary_refresh import WORKFLOW,NAME
    result={"starts":{},"profiles":{},"slots":[],"errors":[]}
    if day!=DAY or repo!=REPO or not str(run_id).isdigit():
        raise ValueError("aux_recovery_identity")
    end=monotonic()+45
    def timeout(cap):
        left=end-monotonic()
        if left<=0:raise TimeoutError("prior_recovery_budget")
        return min(left,cap)
    def api(path):
        return json.loads(subprocess.check_output(["gh","api",path],text=True,stderr=subprocess.DEVNULL,timeout=timeout(8)))
    observed=[]
    name,wf,_=WEEKENDS[day]
    for name,wf,lane in ((name,wf,"pc"),(NAME,WORKFLOW,"auxiliary")):
        try:
            index=api(f"repos/{repo}/actions/workflows/{wf}/runs?created={_date(day)}&per_page=100")
            rows=index["workflow_runs"]
            if index["total_count"]!=len(rows) or len(rows)>100 or len({r["id"] for r in rows})!=len(rows):raise ValueError("incomplete_prior_index")
            for r in rows:
                if (type(r.get("id")) is int and r["id"]>0 and str(r["id"])!=str(run_id)
                    and r.get("head_repository",{}).get("full_name")==repo and r.get("head_branch")=="main"
                    and r.get("path","").split("@",1)[0]==".github/workflows/"+wf
                    and run_name_matches(r,name,wf,day) and r.get("created_at","")[:10]==_date(day)
                    and r.get("status")=="completed" and r.get("event") in ("schedule","workflow_dispatch")):
                    observed.append((r["id"],lane))
        except Exception as exc:result["errors"].append({"lane":lane,"error_class":type(exc).__name__})
    conflicts=set()
    for rid,lane in sorted(observed,reverse=True):
        if monotonic()>=end:break
        try:
            arts=api(f"repos/{repo}/actions/runs/{rid}/artifacts?per_page=100")
            name=f"kyoto-{lane}-{rid}-{day}"
            if arts["total_count"]!=len(arts["artifacts"]) or len([a for a in arts["artifacts"] if a.get("name")==name and a.get("expired") is False])!=1:continue
            with tempfile.TemporaryDirectory(prefix="kyoto_aux_recovery_prior_") as tmp:
                base=Path(tmp);cipher=base/"cipher";cipher.mkdir();raw=base/"raw"
                subprocess.run(["gh","run","download",str(rid),"--repo",repo,"--name",name,"--dir",str(cipher)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=timeout(12))
                decrypt_evidence(cipher,raw,key_hex=key,repo=repo,run_id=str(rid))
                slot=extract_slot(raw,day,rid)
                if slot["day"]!=day or slot["run_id"]!=str(rid):raise ValueError("prior_slot_identity")
                result["slots"].append(slot)
                for race,row in slot["races"].items():
                    n=int(race);start=row["start_utc"]
                    if n in result["starts"] and result["starts"][n]!=start:conflicts.add(n)
                    else:result["starts"][n]=start
                try:
                    for k,item in candidates(raw,day,rid).items():
                        result["profiles"].setdefault(k,item)
                except (OSError,ValueError,KeyError,TypeError):pass
        except Exception as exc:result["errors"].append({"run_id":rid,"error_class":type(exc).__name__})
    for n in conflicts:result["starts"].pop(n,None)
    return result

class RecoveryTransport:
    def __init__(self,client,within,pacer,state,*,start,monotonic=time.monotonic,read=_read):
        self.client,self.within,self.pacer,self.state=client,within,pacer,state
        self.monotonic,self.read=monotonic,read
        self.initial=state["requests"]
        self.end=min(start+TOTAL_SECONDS,monotonic()+RECOVERY_SECONDS)
        self.refused=False
        self.race_cutoff=None
        self.clock=None
        self.profile_cutoffs={}
        self.market_cap=MAX_EXTRA
        self.market_end=self.end
    def check(self,url,*,profile=False):
        u=urlsplit(url)
        paths=("/JRADB/accessU.html",) if profile else ("/JRADB/accessD.html","/JRADB/accessO.html")
        if (u.scheme!="https" or u.netloc not in ("jra.jp","www.jra.go.jp") or u.path not in paths or u.fragment):
            raise ValueError("aux_recovery_origin")
        if (self.refused or self.state["refused"] or not self.within()
            or self.state["requests"]>=MAX_TOTAL or self.state["requests"]-self.initial>=MAX_EXTRA
            or self.monotonic()>=self.end):
            raise ValueError("aux_recovery_boundary")
        cutoff=self.profile_cutoffs.get(url) if profile else self.race_cutoff
        if cutoff is None or self.clock is None or _utc(self.clock())>=cutoff:
            raise ValueError("aux_recovery_race_cutoff")
        if not profile and (self.state["requests"]-self.initial>=self.market_cap or self.monotonic()>=self.market_end):
            raise ValueError("aux_market_reserve_for_profiles")
    def open(self,request,timeout=20):
        url=request.full_url
        profile=urlsplit(url).path=="/JRADB/accessU.html"
        self.check(url,profile=profile)
        limit=self.end if profile else self.market_end
        cutoff=self.profile_cutoffs[url] if profile else self.race_cutoff
        remaining=min(limit-self.monotonic(),(cutoff-_utc(self.clock())).total_seconds())
        if remaining<=0:raise ValueError("aux_recovery_boundary")
        self.state["requests"]+=1
        try:return self.client.open(request,timeout=min(timeout,remaining))
        except HTTPError as exc:
            if exc.code in (401,403,429) or 300<=exc.code<400:self.state["refused"]=True
            raise
        except ValueError:
            self.state["refused"]=True;raise
    def profile(self,url):
        self.check(url,profile=True);self.pacer.before_request();self.check(url,profile=True)
        try:return self.read(self,url)
        except HTTPError as exc:
            if exc.code in (401,403,429) or 300<=exc.code<400:self.state["refused"]=True
            raise
        except ValueError as exc:
            if not str(exc).startswith("aux_"):self.state["refused"]=True
            raise

def missing_records(records,current,prior,roster,clock):
    """Keep only unstarted races without a prior exact dual-market proof."""
    result={}
    for n,item in records.items():
        row=current.get(str(n))
        if not item or not row or _utc(clock())>=_utc(item["verified_start_utc"])-timedelta(minutes=10):
            result[n]=None;continue
        cancelled=sorted(h["number"] for h in roster[str(n)]["runners"] if h.get("cancelled") is True)
        def same(old):
            if not isinstance(old,dict) or old.get("paired_same_slot") is not True:return False
            if any(old.get(k)!=row.get(k) for k in ("roster_digest","named_roster_digest","start_utc")):return False
            try:return all(old["markets"][m]["cancelled_horses"]==cancelled and _utc(old["markets"][m]["utc"])<_utc(row["start_utc"]) for m in MARKETS)
            except (KeyError,TypeError,ValueError):return False
        result[n]=None if any(same(s["races"].get(str(n))) for s in prior["slots"]) else item
    return result

def repair(root,*,day,prior,transport,clock):
    from diagnostics.kyoto_g06_all12_capture import run_twelve
    from diagnostics.kyoto_g06_nested_bundle import bundle_g06,bundle_interrupted_g06,BundleError
    from diagnostics.jra_pending_profile_plan import trusted_url
    from diagnostics.kyoto_g04_all_horse_profiles import capture
    root=Path(root)
    out={"schema":"kyoto_aux_gap_recovery.v1","prior_slots":len(prior["slots"]),"prior_errors":prior["errors"],"markets_attempted":False,"profiles_attempted":False,"source_only":True}
    if day!=DAY:raise ValueError("aux_recovery_day")
    transport.clock=clock
    try:
        current=extract_slot(root,day,0)
        records=records_from_g03(root,day=day,skip_invalid_races=True)
        roster=json.loads((root/"g03_receipt.json").read_text())["races"]
        missing=missing_records(records,current["races"],prior,roster,clock)
        out["market_target_races"]=[n for n,v in missing.items() if v is not None]
        # Bind each exact, independently verified profile link to its race
        # cutoff. Duplicates use the earlier cutoff, never a guessed URL.
        for n,item in records.items():
            if not item or str(n) not in current["races"]:continue
            for h in roster[str(n)]["runners"]:
                try:
                    parent="www.jra.go.jp" if item["race_spec"].pc_racecard_url.startswith("https://www.jra.go.jp/") else "jra.jp"
                    url=trusted_url(h["profile_navigation"],parent_host=parent)
                    cutoff=_utc(item["verified_start_utc"])
                    transport.profile_cutoffs[url]=min(cutoff,transport.profile_cutoffs.get(url,cutoff))
                except (ValueError,TypeError,KeyError):continue
        # Preserve profile opportunity even if G06 repeatedly fails. A
        # complete earlier market pair is not fetched again by this phase.
        if transport.profile_cutoffs:
            transport.market_cap=12
            transport.market_end=max(transport.monotonic(),transport.end-35)
        if out["market_target_races"] and not transport.state["refused"]:
            stage=root/"g06_unsealed"
            def before_race(item):
                transport.race_cutoff=_utc(item["verified_start_utc"])-timedelta(minutes=10)
            try:
                out["markets_attempted"]=True
                summary=run_twelve(stage,records=missing,authorized_live_http=True,
                    before_race=before_race,openers={"PC":transport},request_pacer=transport.pacer,
                    capture_deadline_monotonic=transport.market_end,monotonic_clock=transport.monotonic)
                out["paired_market_races"]=summary["verified_dual_market_races"]
            except Exception as exc:out["market_error_class"]=type(exc).__name__
            finally:
                if stage.is_dir():
                    try:bundle_g06(stage,root/"g06_source_bundle.tar.gz")
                    except BundleError as exc:
                        if str(exc)!="batch_receipt_missing":raise
                        bundle_interrupted_g06(stage,root/"g06_source_bundle.tar.gz")
        if current["races"] and not transport.state["refused"]:
            out["profiles_attempted"]=True
            summary=capture(root=root,day=day,fetch=transport.profile,clock=clock,allowed=True,
                allow_partial=True,isolate_invalid_links=True,deadline_monotonic=transport.end,
                monotonic=transport.monotonic,prior_profiles=prior["profiles"])
            out["profiles_verified"]=summary["profile_verified_count"]
            out["profiles_reused"]=summary["profiles_reused_count"]
    except Exception as exc:out["recovery_error_class"]=type(exc).__name__
    out["extra_http_requests"]=transport.state["requests"]-transport.initial
    out["source_success_certified"]=False
    return out
