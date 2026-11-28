"""Fixed 25-risk obligations linked to actual source runs; no self-certification."""
import hashlib,json
# Locked exact 25-risk register at the independently pinned postrace reader.
REGISTER_BLOB="525981682c56a87b9a674d942238eabef239e0dc"
IDS=tuple(f"GAP-{n:02d}" for n in range(1,26))
ROLE={"O":"two-source-production-observer.yml","A":"auxiliary-refresh.yml","P":"postrace-evidence.yml","H":"result-handoff.yml","W":"workout-source.yml","C":"cushion-source.yml"}
MAPPING=[
 ("O","racecard","same-race PC/SP named roster original agreement"),
 ("O","racecard","SP unique observed current-day candidates"),
 ("O","racecard","complete observed SP navigation graph"),
 ("O","racecard paired_market_same_slot","both lanes independent prestart UTC"),
 ("O","quinella bracket_quinella paired_market_same_slot","both complete odds matrices and cancellations"),
 ("OAC","","cross-lane request timeline and pacing"),
 ("O","","mixed or malformed archive destructive test and salvage"),
 ("O","","runner-loss durable recovery and restore"),
 ("OA","","concurrent dispatch lease and native execution"),
 ("O","","exact native/external slot receipt and latency"),
 ("OAPHWC","","long-term encrypted original restore"),
 ("OH","","authenticated actual cross-day handoff"),
 ("OH","","reproduced defect, fixed revision and applied policy"),
 ("O","paired_market_same_slot","every SP intermediate market original"),
 ("O","paired_market_same_slot","every PC intermediate market original"),
 ("O","","interrupted request attribution and absent-source evidence"),
 ("OAPHWC","","exact installed production dependency versions"),
 ("OH","","complete handoff API and failure replay"),
 ("O","paired_market_same_slot","early-race prestart actual coverage"),
 ("OA","racecard","real HTML and refusal boundary"),
 ("OA","racecard","all 12 same-day verified racecards"),
 ("O","racecard","live partial encryption roundtrip"),
 ("O","profile prior_form","all real horse profiles and cutoff"),
 ("OAW","body_weight_kg body_weight_change_kg workout","weight publication and independent workout"),
 ("OAC","weather turf_going dirt_going turf_moisture_finish_pct turf_moisture_turn4_pct dirt_moisture_finish_pct dirt_moisture_turn4_pct","actual track measurement date and prestart comparison")]
def worklist(report,raw,expected_blob=REGISTER_BLOB):
    blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    if blob!=expected_blob:raise ValueError("risk_register_blob_mismatch")
    risks=json.loads(raw)["risks"]
    if tuple(r["id"] for r in risks)!=IDS or sum(r["severity"]=="BLOCKER" for r in risks)!=13 or len(MAPPING)!=25:raise ValueError("risk_inventory_changed")
    counts=report.get("coverage",{}).get("counts",{})
    out=[]
    for risk,(roles,families,proof) in zip(risks,MAPPING):
        evidence=[]
        for role in roles:
            w=report["workflows"].get(ROLE[role],{})
            evidence.append({"workflow":ROLE[role],"index_complete":w.get("index_complete") is True,"run_ids":[r["id"] for r in w.get("runs",[])],"artifact_ids":sorted({a for r in w.get("runs",[]) for v in r.get("artifacts",{}).values() for a in v.get("ids",[])}),"slots":w.get("native_slots",[]),"external_dispatch_slots":w.get("external_dispatch_slots",[])})
        out.append({"id":risk["id"],"severity":risk["severity"],"surfaces":risk["affected_surfaces"],"required_evidence":risk["required_evidence"],"specific_proof":proof,"evidence":evidence,"coverage":{f:counts.get(f,{"state":"NOT_EVALUATED"}) for f in families.split()},"closed":False,"state":"INDEPENDENT_CLOSURE_NOT_PROVED"})
    return {"schema":"kyoto_fixed_risk_worklist.v1","register_blob":blob,"total":25,"blockers":13,"independently_closed":0,"rows":out}

# A missing producer cannot trigger its own workflow_run diagnosis.
# Independent metadata checkpoint keeps those failures open without guessing
# provider causality, and does not confuse a skipped job with runner loss.
SLOT_ACTIONS={
 "DISPATCH_NOT_OBSERVED":("RECOVER_PROVIDER_DISPATCH_RECEIPT_AND_EXACT_RUN_INDEX","provider trigger/HTTP response, matching GitHub run or verified absence"),
 "DISPATCH_AMBIGUOUS":("RECONCILE_EXACT_DISPATCH_RECEIPT_TO_RUN","provider request ID and unique run binding"),
 "DISPATCH_UNSUCCESSFUL":("REOPEN_EXACT_RUN_JOBS_LOGS_AND_ARTIFACTS","job conclusions, logs and available originals"),
 "DISPATCH_INDEX_UNAVAILABLE":("RESTORE_COMPLETE_WORKFLOW_RUN_INDEX","complete authenticated run index; provider cause not inferred"),
}
ARTIFACT_ACTIONS={
 "JOB_SKIPPED_NO_ARTIFACT":("REOPEN_EXACT_JOB_CONDITION_AND_EVENT","exact job condition and triggering event; no runner loss inferred"),
 "MISSING_AFTER_JOB_SUCCESS":("RECOVER_UPLOAD_STEP_RECEIPT_AND_ARTIFACT_INDEX","exact upload logs and surviving original or backup"),
 "MISSING_AFTER_JOB_UNSUCCESSFUL":("RECOVER_RUNNER_JOB_LOGS_AND_LAST_DURABLE_CHECKPOINT","job failure/cancellation evidence and surviving encrypted originals"),
 "MISSING_JOB_STATE_UNVERIFIED":("RESTORE_EXACT_PRODUCER_JOB_INDEX","complete job index and exact job conclusion"),
 "MISSING_EXPIRED_OR_AMBIGUOUS":("RECOVER_ORIGINAL_BY_EXACT_ARTIFACT_ID_AND_DIGEST","artifact identity, digest, expiry and recoverable backup"),
}
def continuity_worklist(day,workflows):
    rows=[]
    def add(workflow,stage,code,next_action,needed,*,run_id=None,lane=None,due=None,run_ids=(),job_id=None,artifact_ids=(),head_sha=None):
        origin={"day":day,"workflow":workflow,"stage":stage,"run_id":run_id,"lane":lane,"due_utc":due}
        oid=hashlib.sha256(json.dumps(origin,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        rows.append({**origin,"obligation_id":"CONT-"+oid,"state":"OPEN_REPAIR_REQUIRED","observed_code":code,
                     "root_cause_proved":False,"source_success_certified":False,"source_head_sha":head_sha,
                     "candidate_run_ids":sorted(run_ids),"job_id":job_id,"artifact_ids":sorted(artifact_ids),
                     "next_action":next_action,"missing_evidence":needed})
    for name,w in sorted(workflows.items()):
        if w.get("index_complete") is not True:
            add(name,"RUN_INDEX","RUN_INDEX_UNAVAILABLE","RESTORE_COMPLETE_WORKFLOW_RUN_INDEX","complete run index and provider receipt; absence not established")
        for s in w.get("external_dispatch_slots",[]):
            code=s["state"]
            if code in SLOT_ACTIONS:
                action,needed=SLOT_ACTIONS[code]
                add(name,"DISPATCH_SLOT",code,action,needed,due=s["due_utc"],run_ids=s.get("run_ids",[]))
        for r in w.get("runs",[]):
            if r.get("artifact_index_error"):
                add(name,"ARTIFACT_INDEX","ARTIFACT_INDEX_UNAVAILABLE","RESTORE_EXACT_RUN_ARTIFACT_INDEX","complete artifact index and upload receipt",run_id=r["id"],head_sha=r.get("head_sha"))
            for lane,a in sorted(r.get("artifacts",{}).items()):
                code=a["state"]
                if code=="PRESENT":continue
                action,needed=ARTIFACT_ACTIONS.get(code,("REOPEN_EXACT_RUN_ARTIFACT_AND_JOB","exact source job and artifact evidence"))
                add(name,"PRODUCER_ARTIFACT",code,action,needed,run_id=r["id"],lane=lane,job_id=a.get("job_id"),artifact_ids=a.get("ids",[]),head_sha=r.get("head_sha"))
    return {"schema":"kyoto_continuity_worklist.v1","day":day,"rows":rows,"independently_closed":0,"new_source_http_requests":0}

def continuity_summary(doc):
    rows=doc["rows"]
    lines=[f"- 独立した起動・原本保全の未解決課題: {len(rows)}件（取得成功・原因閉鎖の認定なし）。"]
    for r in rows[:40]:
        lines.append(f"  - {r['obligation_id']} {r['workflow']} {r['observed_code']} / UTC {r['due_utc'] or '-'} / run {r['run_id'] or r['candidate_run_ids']} / job {r['job_id']} / lane {r['lane']} / artifact {r['artifact_ids']} / 次処置 {r['next_action']}")
    if len(rows)>40:lines.append(f"  - 残り{len(rows)-40}件は同じ実行のcontinuity_worklist.jsonに保全。")
    return lines
