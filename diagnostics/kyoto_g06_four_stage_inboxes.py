"""Create immutable input inboxes for G07/P4/P5/P6 from actual verified G06 stages.

The external models remain separate. These four files enable reproducible
handoff and explicitly preserve missing probabilities, probabilities never
inferred from odds, and the prohibition on predictive deployment.
"""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import json
from diagnostics.jra_market_source_chain import SourceChainError

NAMES={"G07":"g07_roster_and_missingness.json",
       "P4":"p4_market_source_intake.json",
       "P5":"p5_model_dependency_inbox.json",
       "P6":"p6_preresult_freeze_dependency_inbox.json"}
def _encode(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,
                       indent=2,allow_nan=False)+"\n").encode("utf-8")

def publish_inboxes(root, *, source_receipt):
    root=Path(root)
    if not isinstance(source_receipt,dict) or source_receipt.get("schema")!="kyoto_g06_g07_p4_p5_p6_source_intake.v1":
        raise SourceChainError("g06_stage_intake_required")
    races=source_receipt.get("races")
    if not isinstance(races,list) or len(races)!=12 or [r.get("race") for r in races]!=list(range(1,13)):
        raise SourceChainError("exact_twelve_races_required")
    if source_receipt.get("eligible_for_prediction") is not False:
        raise SourceChainError("unlicensed_prediction_claim")
    packets={}
    for stage in NAMES:
        rows=[]
        for race in races:
            value=race.get(stage)
            if not isinstance(value,dict) or "state" not in value:
                raise SourceChainError("missing_stage_state_"+stage)
            item={"race":race["race"],"state":value["state"],
                  "source_state":race["state"],"payload":value}
            if stage=="P4":
                markets=value.get("markets",{})
                if set(markets)-{"quinella","bracket_quinella"}:
                    raise SourceChainError("unknown_market")
                for market,v in markets.items():
                    if not isinstance(v,dict) or not isinstance(v.get("pairs"),list) or not v["pairs"]:
                        raise SourceChainError("unverified_p4_source_rows")
            if stage in ("P5","P6") and "WAIT" not in value["state"]:
                raise SourceChainError("early_prediction_or_trade_promotion")
            rows.append(item)
        packets[stage]={"schema":"kyoto_g06_"+stage.lower()+"_source_inbox.v1",
                         "stage":stage,"races":rows,
                         "real_model_supplied":False,
                         "prediction_or_trade_authorized":False,
                         "source_originals_must_be_reopened":True}
    # Prevent partial overwrites in a resumed or parallel task. A second
    # invocation is an explicit error, never silently replace stage output.
    target=root/"next_stage_inboxes"
    if target.exists() or target.is_symlink():
        raise SourceChainError("stage_inboxes_already_published")
    target.mkdir()
    manifest={"schema":"kyoto_g06_four_stage_handoff.v1",
              "g07_p4_p5_p6_wired":True,"official_http_requests":0,
              "prediction_or_trade_authorized":False,
              "files":{}}
    for stage,name in NAMES.items():
        path=target/name
        data=_encode(packets[stage])
        with path.open("xb") as f:f.write(data)
        manifest["files"][stage]={"name":name,"sha256":sha256(data).hexdigest(),
                                  "races":len(packets[stage]["races"])}
    with (target/"manifest.json").open("xb") as f:f.write(_encode(manifest))
    return manifest

def read_inboxes(root):
    root=Path(root)/"next_stage_inboxes"
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema")!="kyoto_g06_four_stage_handoff.v1" or set(manifest.get("files",{}))!=set(NAMES):
        raise SourceChainError("stage_manifest_invalid")
    loaded={}
    for stage,name in NAMES.items():
        meta=manifest["files"][stage]
        file=root/name
        if file.is_symlink() or not file.is_file() or meta["name"]!=name:
            raise SourceChainError("stage_inbox_missing")
        raw=file.read_bytes()
        if sha256(raw).hexdigest()!=meta["sha256"]:
            raise SourceChainError("stage_inbox_tampered")
        item=json.loads(raw)
        if item.get("stage")!=stage or item.get("prediction_or_trade_authorized") is not False:
            raise SourceChainError("stage_inbox_identity_or_authorization")
        if len(item.get("races",[]))!=12 or [r.get("race") for r in item["races"]]!=list(range(1,13)):
            raise SourceChainError("stage_inbox_race_mismatch")
        loaded[stage]=item
    return loaded
