"""Offline pre-race/result evidence gate. No network and no production writes."""
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit
import re
SHA=re.compile(r"^[0-9a-f]{64}$")
ID=re.compile(r"^\d{8,12}$")
STATUSES={"STARTER","SCRATCHED","EXCLUDED","UNCONFIRMED"}
class AuditError(ValueError):pass

def utc(value):
    try: d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (AttributeError,TypeError,ValueError) as e:raise AuditError("invalid_timestamp") from e
    if d.tzinfo is None or d.utcoffset() is None:raise AuditError("timezone_required")
    return d.astimezone(timezone.utc)

def validate_snapshot(pre,cutoff):
    if pre.get("source_type")!="PRE_RACE_RACECARD":raise AuditError("not_prerace_racecard")
    u=urlsplit(pre.get("source_url",""))
    if u.scheme!="https" or u.hostname not in ("www.jra.go.jp","jra.go.jp"):
        raise AuditError("not_official_jra")
    if not SHA.fullmatch(pre.get("source_sha256","")):raise AuditError("invalid_source_hash")
    if pre.get("raw_sha256_verified") is not True:raise AuditError("original_bytes_unverified")
    if pre.get("racecard_structure_verified") is not True:raise AuditError("racecard_structure_unverified")
    if utc(pre.get("fetched_at_utc"))>=utc(cutoff):raise AuditError("snapshot_after_cutoff")
    rows=pre.get("runners")
    if not isinstance(rows,list) or not rows or not pre.get("race_id"):
        raise AuditError("missing_runners_or_race_id")
    seen=set()
    for i,r in enumerate(rows):
        if not isinstance(r,dict):raise AuditError("invalid_row")
        n,w,name,status=(r.get(k) for k in ("horse_number","frame_number","horse_name","status"))
        if (type(n) is not int or not 1<=n<=18 or type(w) is not int or not 1<=w<=8
                or not isinstance(name,str) or not name.strip() or status not in STATUSES):
            raise AuditError(f"invalid_row_{i}")
        if n in seen:raise AuditError("duplicate_horse_number")
        seen.add(n)
        horse_id=r.get("permanent_jra_horse_id")
        if horse_id is not None and (not ID.fullmatch(str(horse_id)) or
                                     r.get("permanent_id_source_verified") is not True):
            raise AuditError("unverified_permanent_horse_id")
    return rows

def reconcile(pre,result,*,cutoff_utc,require_stable_ids=True):
    rows=validate_snapshot(pre,cutoff_utc)
    if result.get("source_type")!="POST_RACE_RESULT" or result.get("raw_sha256_verified") is not True:
        raise AuditError("unverified_result")
    if not SHA.fullmatch(result.get("source_sha256","")):raise AuditError("invalid_result_hash")
    if result.get("race_id")!=pre.get("race_id") or result.get("race_number")!=pre.get("race_number"):
        raise AuditError("race_mismatch")
    if type(pre.get("race_number")) is not int or not 1<=pre["race_number"]<=12:
        raise AuditError("race_number_invalid")
    res=result.get("runners")
    if not isinstance(res,list):raise AuditError("missing_results")
    starters={r["horse_number"]:r for r in rows if r["status"]=="STARTER"}
    found={};errors=[]
    for i,r in enumerate(res):
        n=r.get("horse_number") if isinstance(r,dict) else None
        if type(n) is not int or n in found:errors.append({"kind":"invalid_result_number","row":i})
        else:found[n]=r
    for n,r in starters.items():
        if n not in found:errors.append({"kind":"missing_result","horse_number":n});continue
        for field in ("horse_name","frame_number"):
            if r[field]!=found[n].get(field):
                errors.append({"kind":field+"_mismatch","horse_number":n})
    for n in sorted(found.keys()-starters.keys()):
        errors.append({"kind":"unexpected_result","horse_number":n})
    if any(r["status"]=="UNCONFIRMED" for r in rows):
        errors.append({"kind":"unconfirmed_status"})
    missing_ids=[r["horse_number"] for r in starters.values()
                 if not r.get("permanent_jra_horse_id")]
    if require_stable_ids and missing_ids:
        errors.append({"kind":"stable_ids_missing","horse_numbers":missing_ids})
    if pre.get("scratch_evidence_verified") is not True:
        errors.append({"kind":"scratch_evidence_unverified"})
    passed=not errors
    return {"schema_version":"jra_prerace_reconciliation.v1",
            "race_id":pre["race_id"],"race_number":pre["race_number"],
            "status":"PASS" if passed else "BLOCKED",
            "entry_count":len(rows),"expected_starters":len(starters),
            "result_count":len(res),"errors":errors,"missing_permanent_ids":missing_ids,
            "ready_for_prediction":False,
            "ready_for_training":passed and not missing_ids}

def verified_result_source(crosswalk,race_no,race_id,raw):
    if not race_id:raise AuditError("race_id_required")
    h=sha256(raw).hexdigest()
    if crosswalk.get("result_source_sha256",crosswalk.get("source_sha256"))!=h:
        raise AuditError("result_hash_mismatch")
    rows=[r for r in crosswalk["runners"] if r["race_number"]==race_no]
    return {"source_type":"POST_RACE_RESULT","source_sha256":h,
            "raw_sha256_verified":True,"race_number":race_no,
            "race_id":race_id,"runners":rows}
