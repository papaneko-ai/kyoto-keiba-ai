"""R02 pre-race feature contract: reuse existing P2/P3 bridge; LAB only."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
import json, math, re
from diagnostics.p2_p3_p5_offline_feature_bridge import FEATURE_SCHEMA,_feature_row,FeatureBridgeRejected

FAMILIES=("course","distance","pace","ground","rest","jockey","horse")
MISSING_REASONS=frozenset(("SOURCE_NOT_QUERIED","VERIFIED_NO_HISTORY","SOURCE_UNAVAILABLE","NOT_PUBLISHED"))
_SHA=re.compile(r"[0-9a-f]{64}\Z")
class FeatureContractRejected(ValueError):pass

def _utc(value):
    if type(value) is not str or not(value.endswith("Z") or value.endswith("+00:00")):
        raise FeatureContractRejected("utc_required")
    try: stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise FeatureContractRejected("utc_invalid") from exc
    if stamp.utcoffset()!=timezone.utc.utcoffset(None):
        raise FeatureContractRejected("utc_required")
    return stamp

def _sha(value):
    if type(value) is not str or not _SHA.fullmatch(value):
        raise FeatureContractRejected("sha256_required")
    return value

def freeze_feature_envelope(envelope):
    """Seven-family evidence to existing four-feature P3 input, never imputing.
    
    Source hashes here are structural receipts, not independent JRA authentication.
    All missing categories force SKIP and never authorize a trade.
    """
    expected={"schema","race_id","source_scope","race_start_utc",
              "feature_cutoff_utc","racecard_source_sha256","runners"}
    if (type(envelope) is not dict or set(envelope)!=expected
        or envelope["schema"]!="kyoto_p2_seven_family_envelope.v1"):
        raise FeatureContractRejected("envelope_schema_invalid")
    if (envelope["source_scope"]!="LAB_OFFLINE_ONLY" or type(envelope["race_id"]) is not str
        or not envelope["race_id"].startswith("LAB-")):
        raise FeatureContractRejected("nonlab_scope_forbidden")
    cutoff,start=_utc(envelope["feature_cutoff_utc"]),_utc(envelope["race_start_utc"])
    if cutoff>=start:raise FeatureContractRejected("cutoff_not_before_start")
    race_sha=_sha(envelope["racecard_source_sha256"])
    runners=envelope["runners"]
    if type(runners) is not list or not 3<=len(runners)<=18:
        raise FeatureContractRejected("runner_count_invalid")
    seen=set();rows=[];missing=[];sha_receipts=[];value_receipts=[]
    for row in runners:
        if type(row) is not dict or set(row)!={"number","frame","families"}:
            raise FeatureContractRejected("runner_schema_invalid")
        n,frame=row["number"],row["frame"]
        if (type(n) is not int or not 1<=n<=18 or n in seen
            or type(frame) is not int or not 1<=frame<=8):
            raise FeatureContractRejected("runner_identity_invalid")
        seen.add(n)
        families=row["families"]
        if type(families) is not dict or set(families)!=set(FAMILIES):
            raise FeatureContractRejected("family_missing_or_forbidden")
        values={}
        for name in FAMILIES:
            ev=families[name]
            if type(ev) is not dict or set(ev)!={"value","missing_reason","captured_utc","source_sha256"}:
                raise FeatureContractRejected("family_evidence_schema_invalid")
            captured=_utc(ev["captured_utc"])
            if captured>cutoff or captured>=start:
                raise FeatureContractRejected("future_feature_leakage")
            sha=_sha(ev["source_sha256"])
            sha_receipts.append([n,name,sha,ev["captured_utc"]])
            value,reason=ev["value"],ev["missing_reason"]
            if value is None:
                if reason not in MISSING_REASONS:
                    raise FeatureContractRejected("missing_reason_required")
                missing.append({"number":n,"family":name,"reason":reason})
            else:
                if (reason is not None or type(value) not in (float,int)
                    or not math.isfinite(value) or not 0<=value<=1):
                    raise FeatureContractRejected("feature_value_invalid")
                values[name]=float(value)
            value_receipts.append([n,name,value,reason])
        if len(values)==len(FAMILIES):
            features={"course_fit":(values["course"]+values["ground"])/2,
                      "distance_fit":values["distance"],
                      "pace_fit":(values["pace"]+values["jockey"])/2,
                      "recent_form":(values["horse"]+values["rest"])/2}
            rows.append({"number":n,"frame":frame,"features":features})
    body={"schema":"kyoto_p2_seven_family_contract_receipt.v1",
          "race_id":envelope["race_id"],"source_scope":"LAB_OFFLINE_ONLY",
          "racecard_source_sha256":race_sha,
          "feature_cutoff_utc":envelope["feature_cutoff_utc"],
          "race_start_utc":envelope["race_start_utc"],
          "family_names":list(FAMILIES),"missing":missing,
          "source_evidence":sha_receipts,"observed_feature_values":value_receipts,
          "runner_count":len(runners),"market_data_used":False,
          "post_race_labels_used":False,"real_jra_authenticated":False,
          "production_ready":False,"network_requests":0,"spend_authorized":False}
    blob=json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    receipt={**body,"receipt_sha256":sha256(blob).hexdigest()}
    if missing:
        return {"status":"SKIP_INCOMPLETE_PRERACE_FEATURES","receipt":receipt,"p3_snapshot":None}
    snapshot={"race_id":envelope["race_id"],"source_scope":"LAB_OFFLINE_ONLY",
              "feature_source_sha256":receipt["receipt_sha256"],
              "feature_cutoff_utc":envelope["feature_cutoff_utc"],
              "race_start_utc":envelope["race_start_utc"],"runners":rows}
    try:_feature_row(snapshot,expected_keys=FEATURE_SCHEMA)
    except FeatureBridgeRejected as exc:
        raise FeatureContractRejected("existing_p3_bridge_rejected") from exc
    return {"status":"P3_LAB_FEATURES_VALIDATED_NOT_PRODUCTION",
            "receipt":receipt,"p3_snapshot":snapshot}
