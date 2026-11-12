"""Read-only, fail-closed archive inspection for an official JRA selection proof.

Consumes only bytes uploaded by an operator. Does not contact JRA, modify
production state, or certify racecards/odds/real paper-trades. Reuses the
existing independent one-shot receipt/original checker verbatim.
"""
from __future__ import annotations
import hashlib
import io
import json
import stat
import tempfile
import zipfile
from pathlib import Path
from diagnostics.kyoto_p1_nov14_receipt_handoff import (
    assess_saved_selection, HandoffRejected
)

class SourceStatusRejected(ValueError):
    pass

MAX_ZIP_BYTES=6_000_000
MAX_TOTAL_UNCOMPRESSED=4_000_000
ALLOWED={"official_selection.html","receipt.json","verified_meeting_handoff.json"}

def inspect_official_selection_archive(data:bytes):
    if type(data) is not bytes or not 0<len(data)<=MAX_ZIP_BYTES:
        raise SourceStatusRejected("zip_size_invalid")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries=z.infolist()
            if not 1<=len(entries)<=5:
                raise SourceStatusRejected("archive_member_count_invalid")
            files={}
            total=0
            for member in entries:
                name=member.filename
                if (member.is_dir() or name.startswith("/") or "\\" in name
                    or any(part in (".","..","") for part in name.split("/"))
                    or len(name.split("/"))>2 or name.split("/")[-1] not in ALLOWED):
                    raise SourceStatusRejected("archive_member_path_invalid")
                # Reject UNIX special files and symlinks, while also accepting
                # standard ZipFile and GitHub Actions regular-file members.
                mode=(member.external_attr >> 16) & 0o170000
                if mode not in (0,stat.S_IFREG):
                    raise SourceStatusRejected("archive_member_not_regular_file")
                basename=name.split("/")[-1]
                if basename in files:
                    raise SourceStatusRejected("archive_member_duplicate")
                total+=member.file_size
                if total>MAX_TOTAL_UNCOMPRESSED:
                    raise SourceStatusRejected("archive_expanded_size_exceeded")
                raw=z.read(member)
                if len(raw)!=member.file_size:
                    raise SourceStatusRejected("archive_member_size_conflict")
                files[basename]=raw
    except (OSError,ValueError,zipfile.BadZipFile,RuntimeError) as exc:
        if isinstance(exc,SourceStatusRejected):
            raise
        raise SourceStatusRejected("archive_unreadable") from exc
    if "receipt.json" not in files or "official_selection.html" not in files and len(files)>2:
        raise SourceStatusRejected("required_receipt_or_original_missing")
    try:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,raw in files.items():
                with (root/name).open("xb") as out:
                    out.write(raw)
            proof=assess_saved_selection(root)
    except (HandoffRejected, OSError, ValueError) as exc:
        raise SourceStatusRejected("original_receipt_independent_validation_failed:"+str(exc)) from exc
    supplied=files.get("verified_meeting_handoff.json")
    if supplied is not None:
        try:
            recorded=json.loads(supplied.decode("utf-8"))
        except (ValueError,UnicodeError) as exc:
            raise SourceStatusRejected("archived_handoff_unreadable") from exc
        if recorded!=proof:
            raise SourceStatusRejected("archived_handoff_does_not_match_recomputed")
    return {
        "schema":"kyoto_p8_official_source_status.v1",
        "classification":proof["state"],
        "archive_sha256":hashlib.sha256(data).hexdigest(),
        "selection_sha256":proof.get("selection_sha256"),
        "official_meeting_url":proof.get("official_meeting_url"),
        "source_only":True,
        "live_racecard_verified":False,
        "prerace_quinella_verified":False,
        "prerace_bracket_verified":False,
        "prediction_ready":False,
        "paper_trade_authorized":False,
        "operational_progress_credit":0,
        "network_requests":0,
    }
