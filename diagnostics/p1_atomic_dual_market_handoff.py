"""P1-04 atomic three-original prerace market handoff, offline and fail-closed.

The caller supplies three independently captured HTML byte strings and the
snapshot. This boundary does *not* acquire JRA content, prove official origin,
independently attest time/sales/withdrawals, or authorize model predictions.
It reuses the exact existing strict P1 validator; an immutable single archive
can be moved to an authorized operational verifier without data loss.
"""
from __future__ import annotations
import hashlib
import io
import json
import re
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path
from diagnostics.jra_p1_future_evidence import instant
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.p1_operator_original_handoff import assess_originals

class MarketHandoffRejected(ValueError):
    pass

KINDS=("racecard","pre_race_odds","bracket_odds")
BINDINGS={"racecard":"racecard","pre_race_odds":"odds","bracket_odds":"bracket_odds"}

def _canon(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,
            separators=(",",":"),allow_nan=False)+"\n").encode("utf8")

def _validate_fields(raw_sources, snapshot, observed_utc, channel):
    if type(raw_sources) is not dict or set(raw_sources)!=set(KINDS):
        raise MarketHandoffRejected("three_independent_sources_required")
    if type(snapshot) is not dict or channel not in ("PC","SP"):
        raise MarketHandoffRejected("snapshot_or_channel_invalid")
    try:
        observed=instant(observed_utc)
        cutoff=instant(snapshot["prediction_cutoff_utc"])
        if not observed<cutoff:
            raise MarketHandoffRejected("after_prediction_cutoff")
    except (ValueError,KeyError,TypeError) as exc:
        raise MarketHandoffRejected("prerace_timestamp_invalid") from exc
    sha=[]
    for kind in KINDS:
        record=raw_sources[kind]
        if type(record) is not dict or set(record)!={"raw","captured_utc","observed_url"}:
            raise MarketHandoffRejected("raw_capture_schema_invalid")
        if type(record["raw"]) is not bytes or not 0<len(record["raw"])<=1_800_000:
            raise MarketHandoffRejected("source_original_bytes_invalid")
        if type(record["observed_url"]) is not str or not re.fullmatch(
                r"https://(?:sp\.)?jra\.jp/[^\s#?]+(?:\?[^\s#]*)?",record["observed_url"]):
            raise MarketHandoffRejected("claimed_original_url_invalid")
        try:
            captured=instant(record["captured_utc"])
        except (TypeError,ValueError,KeyError) as exc:
            raise MarketHandoffRejected("captured_utc_invalid") from exc
        if captured>observed or captured>=cutoff:
            raise MarketHandoffRejected("post_cutoff_or_future_capture")
        if kind!="racecard" and observed-captured>timedelta(minutes=30):
            raise MarketHandoffRejected("market_capture_stale")
        sha.append(hashlib.sha256(record["raw"]).hexdigest())
    if len(set(sha))!=3:
        raise MarketHandoffRejected("originals_not_independent")

def package_prerace_market_capture(*,raw_sources,snapshot,observed_utc,channel):
    _validate_fields(raw_sources,snapshot,observed_utc,channel)
    with tempfile.TemporaryDirectory() as t:
        root=Path(t)
        sources=[]
        for kind in KINDS:
            item=raw_sources[kind]
            filename=f"{kind}.html"
            (root/filename).write_bytes(item["raw"])
            sources.append({
                "kind":kind,"race":snapshot["race"],"path":filename,
                "captured_utc":item["captured_utc"],
                "sha256":hashlib.sha256(item["raw"]).hexdigest(),
                "official_url_observed":True
            })
        manifest={"schema":"kyoto_p1_future_race_source_evidence.v1",
                  "meeting_date":snapshot["meeting_date"],
                  "cutoff_utc":snapshot["prediction_cutoff_utc"],
                  "sources":sources}
        try:
            original_bundle=export_bundle(manifest,root,observed_utc=observed_utc)
            checked=assess_originals(original_bundle,snapshot,
                observed_utc=observed_utc,channel=channel)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            raise MarketHandoffRejected("strict_three_original_content_rejected:"+str(exc)) from exc
    if checked["source_content_verified"] is not True or checked["prediction_ready"] is not False:
        raise MarketHandoffRejected("unexpected_source_authorization")
    result={
        "schema":"kyoto_p1_atomic_prerace_original_handoff.v1",
        "scope":"SELF_ASSERTED_CAPTURE_WITH_CONTENT_VERIFIED_ONLY",
        "meeting_date":snapshot["meeting_date"],"race":snapshot["race"],
        "observed_utc":observed_utc,"channel":channel,
        "bundle_sha256":hashlib.sha256(original_bundle).hexdigest(),
        "snapshot_sha256":hashlib.sha256(_canon(snapshot)).hexdigest(),
        "source_sha256":checked["originals_sha256"],
        "source_count":3,"complete_quinella":True,"complete_bracket":True,
        "source_content_verified":True,
        "official_origin_authenticated":False,
        "official_sales_authenticated":False,
        "official_scratches_authenticated":False,
        "real_prerace_market_independently_verified":False,
        "prediction_ready":False,"paper_trade_ready":False,
        "actual_purchase_authorized":False,"network_requests":0
    }
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_STORED) as out:
        # Fixed ZIP member metadata: identical inputs must yield identical
        # archive bytes regardless of wall clock or CI runner.
        for name, value in (("source_bundle.zip",original_bundle),
                            ("snapshot.json",_canon(snapshot)),
                            ("handoff_receipt.json",_canon(result))):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_STORED
            info.external_attr=0o600 << 16
            out.writestr(info,value)
    return {"archive_bytes":buf.getvalue(),"receipt":result}

def verify_prerace_handoff_archive(data,*,expected_sha256,observed_utc,channel):
    if type(data) is not bytes or not 0<len(data)<13_000_000:
        raise MarketHandoffRejected("archive_bytes_invalid")
    if type(expected_sha256) is not str or hashlib.sha256(data).hexdigest()!=expected_sha256:
        raise MarketHandoffRejected("independent_archive_sha_required")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            inf=z.infolist()
            if len(inf)!=3 or set(x.filename for x in inf)!={
                 "source_bundle.zip","snapshot.json","handoff_receipt.json"} or any(
                 x.file_size>12_000_000 or x.compress_type!=zipfile.ZIP_STORED for x in inf):
                raise MarketHandoffRejected("archive_members_invalid")
            bundle=z.read("source_bundle.zip")
            snapshot=json.loads(z.read("snapshot.json"))
            receipt=json.loads(z.read("handoff_receipt.json"))
        checked=assess_originals(bundle,snapshot,observed_utc=observed_utc,channel=channel)
        if (receipt["bundle_sha256"]!=hashlib.sha256(bundle).hexdigest() or
            receipt["snapshot_sha256"]!=hashlib.sha256(_canon(snapshot)).hexdigest() or
            receipt["source_sha256"]!=checked["originals_sha256"] or
            receipt["observed_utc"]!=observed_utc or receipt["channel"]!=channel or
            receipt["official_origin_authenticated"] is not False or
            receipt["prediction_ready"] is not False):
            raise MarketHandoffRejected("archive_receipt_or_context_mismatch")
    except (zipfile.BadZipFile,ValueError,KeyError,TypeError) as exc:
        raise MarketHandoffRejected("archive_verification_failed:"+str(exc)) from exc
    return {"schema":"kyoto_p1_handoff_replay_verified.v1",
            "archive_sha256":expected_sha256,"source_count":3,
            "all_three_content_verified":True,
            "official_origin_authenticated":False,"prediction_ready":False,
            "actual_purchase_authorized":False}

def save_immutable_archive(path,data):
    path=Path(path)
    if path.is_symlink() or not path.parent.is_dir():
        raise MarketHandoffRejected("unsafe_archive_target")
    try:
        with path.open("xb") as out:
            out.write(data)
    except FileExistsError as exc:
        raise MarketHandoffRejected("archive_already_exists") from exc
    return hashlib.sha256(data).hexdigest()
