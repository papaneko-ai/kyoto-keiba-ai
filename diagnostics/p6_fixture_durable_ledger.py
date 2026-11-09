"""P6 offline FIXTURE ONLY hash-chained append journal, with restart replay.

Never a real-trade ledger; never attests external source authenticity. Every
write is checked before append, then fsync'ed. A crash/torn record fails closed.
The optional expected_head prevents accidental concurrent stale writes; external
file locking / concurrent writers are NOT supported. No automatic repair.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

from diagnostics.p6_virtual_settlement_fixture_lab import settle_fixture, LabRejected

SCHEMA = "kyoto_p6_fixture_journal.v1"
MAX_JOURNAL = 4_000_000
MAX_EVENT = 40_000

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def read_journal(path, *, expected_head=None):
    path = Path(path)
    if path.is_symlink():
        raise LabRejected("journal_symlink_forbidden")
    if not path.exists():
        if expected_head is not None and expected_head != "0"*64:
            raise LabRejected("journal_head_anchor_mismatch")
        return {"entries": [], "head": "0"*64, "state": "EMPTY", "result": None}
    if not path.is_file() or path.stat().st_size > MAX_JOURNAL:
        raise LabRejected("journal_size_invalid")
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise LabRejected("torn_journal_record")
    chain = "0"*64
    entries = []
    frozen = None
    event_versions = {}
    for line in raw.splitlines():
        if len(line) > MAX_EVENT:
            raise LabRejected("journal_entry_too_large")
        try:
            entry = json.loads(line)
        except (ValueError, UnicodeDecodeError) as exc:
            raise LabRejected("journal_json_invalid") from exc
        if not isinstance(entry, dict) or set(entry) != {"schema", "sequence", "prev_sha256", "payload", "entry_sha256"}:
            raise LabRejected("journal_entry_schema_invalid")
        if entry["schema"] != SCHEMA or type(entry["sequence"]) is not int or entry["sequence"] != len(entries)+1:
            raise LabRejected("journal_sequence_invalid")
        if entry["prev_sha256"] != chain:
            raise LabRejected("journal_chain_broken")
        body = {key:entry[key] for key in ("schema","sequence","prev_sha256","payload")}
        if digest(body) != entry["entry_sha256"]:
            raise LabRejected("journal_entry_tampered")
        payload = entry["payload"]
        if not isinstance(payload, dict) or payload.get("type") not in ("FROZEN", "RESULT_EVENT"):
            raise LabRejected("journal_payload_invalid")
        if payload["type"] == "FROZEN":
            if frozen is not None or len(entries) != 0:
                raise LabRejected("journal_duplicate_freeze")
            frozen = payload.get("record")
            try:
                settle_fixture(frozen, [])
            except (LabRejected,TypeError,ValueError) as exc:
                raise LabRejected("journal_freeze_invalid") from exc
        else:
            if frozen is None:
                raise LabRejected("journal_event_without_freeze")
            event = payload.get("record")
            if not isinstance(event,dict):
                raise LabRejected("journal_event_invalid")
            version = event.get("version")
            if type(version) is not int or version < 1:
                raise LabRejected("journal_event_version_invalid")
            if version in event_versions:
                if digest(event_versions[version]) != digest(event):
                    raise LabRejected("journal_event_version_conflict")
                raise LabRejected("journal_duplicate_event_append")
            event_versions[version] = event
            try:
                settle_fixture(frozen,list(event_versions.values()))
            except (LabRejected,TypeError,ValueError) as exc:
                raise LabRejected("journal_result_event_invalid") from exc
        chain = entry["entry_sha256"]
        entries.append(entry)
    if entries and frozen is None:
        raise LabRejected("journal_freeze_missing")
    if expected_head is not None and chain != expected_head:
        raise LabRejected("journal_head_anchor_mismatch")
    result = settle_fixture(frozen,list(event_versions.values())) if frozen else None
    return {"entries": entries, "head": chain, "state": "FROZEN" if frozen else "EMPTY", "result": result}

def append_record(path, kind, record, *, expected_head):
    """One-writer fixture-only API. Duplicate events must be handled by caller."""
    path = Path(path)
    if not isinstance(expected_head,str) or len(expected_head) != 64:
        raise LabRejected("expected_head_required")
    current = read_journal(path)
    if current["head"] != expected_head:
        raise LabRejected("journal_head_changed")
    if kind == "FROZEN":
        if current["entries"]:
            raise LabRejected("journal_already_frozen")
        try:
            settle_fixture(record,[])
        except (LabRejected,TypeError,ValueError) as exc:
            raise LabRejected("freeze_invalid") from exc
    elif kind == "RESULT_EVENT":
        if not current["entries"]:
            raise LabRejected("journal_freeze_required")
        frozen=current["entries"][0]["payload"]["record"]
        prior = [e["payload"]["record"] for e in current["entries"][1:]]
        if any(e == record for e in prior):
            raise LabRejected("journal_duplicate_event_append")
        try:
            settle_fixture(frozen,prior+[record])
        except (LabRejected,TypeError,ValueError) as exc:
            raise LabRejected("event_invalid") from exc
    else:
        raise LabRejected("journal_kind_invalid")
    body={"schema":SCHEMA,"sequence":len(current["entries"])+1,
          "prev_sha256":current["head"],"payload":{"type":kind,"record":record}}
    entry={**body,"entry_sha256":digest(body)}
    encoded=canonical(entry)+b"\n"
    if len(encoded)>MAX_EVENT or (path.stat().st_size if path.exists() else 0)+len(encoded)>MAX_JOURNAL:
        raise LabRejected("journal_storage_limit")
    path.parent.mkdir(parents=True,exist_ok=True)
    if current["entries"]:
        with path.open("ab") as f:
            f.write(encoded);f.flush();os.fsync(f.fileno())
    else:
        try:
            with path.open("xb") as f:
                f.write(encoded);f.flush();os.fsync(f.fileno())
        except FileExistsError as exc:
            raise LabRejected("journal_already_exists") from exc
    verified=read_journal(path)
    if verified["head"]!=entry["entry_sha256"]:
        raise LabRejected("journal_commit_verification_failed")
    return verified
