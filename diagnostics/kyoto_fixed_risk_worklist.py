"""Fixed 25-risk obligations linked to actual source runs; no self-certification."""
import hashlib,json
REGISTER_BLOB="72856cf227e6a369f3e1650641dfacec0cdc0d73"
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
            evidence.append({"workflow":ROLE[role],"index_complete":w.get("index_complete") is True,"run_ids":[r["id"] for r in w.get("runs",[])],"artifact_ids":sorted({a for r in w.get("runs",[]) for v in r.get("artifacts",{}).values() for a in v.get("ids",[])}),"slots":w.get("native_slots",[])})
        out.append({"id":risk["id"],"severity":risk["severity"],"surfaces":risk["affected_surfaces"],"required_evidence":risk["required_evidence"],"specific_proof":proof,"evidence":evidence,"coverage":{f:counts.get(f,{"state":"NOT_EVALUATED"}) for f in families.split()},"closed":False,"state":"INDEPENDENT_CLOSURE_NOT_PROVED"})
    return {"schema":"kyoto_fixed_risk_worklist.v1","register_blob":blob,"total":25,"blockers":13,"independently_closed":0,"rows":out}
