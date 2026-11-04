"""Non-production D1 API connectivity and opt-in persistence probe.

Never embed secrets here. No race data. Tests create only the dedicated
kyoto_probe_v15 table; existing user tables are not modified.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import secrets
import urllib.error
import urllib.request
from typing import Any

_ACCOUNT = re.compile(r"^[0-9a-fA-F]{32}$")
_DATABASE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class ProbeError(Exception):
    """Sanitized failure: never include HTTP response, tokens, or request URLs."""


def _call(account_id: str, database_id: str, token: str, sql: str,
          params: list[str] | None = None, *, opener=None) -> dict[str, Any]:
    if not _ACCOUNT.fullmatch(account_id) or not _DATABASE.fullmatch(database_id):
        raise ProbeError("INVALID_IDS")
    if not isinstance(token, str) or not token.strip():
        raise ProbeError("MISSING_TOKEN")
    url = ("https://api.cloudflare.com/client/v4/accounts/" + account_id
           + "/d1/database/" + database_id + "/query")
    payload = {"sql": sql, "params": params or []}
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json", "Accept": "application/json"})
    fetch = opener or urllib.request.urlopen
    try:
        with fetch(request, timeout=15) as response:
            if getattr(response, "status", 200) != 200:
                raise ProbeError("NON_200_RESPONSE")
            raw = response.read(512 * 1024)
    except urllib.error.HTTPError as exc:
        raise ProbeError("HTTP_" + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProbeError("NETWORK_ERROR") from None
    try:
        body = json.loads(raw)
        if body.get("success") is not True:
            raise ProbeError("API_REPORTED_FAILURE")
        items = body.get("result")
        if not isinstance(items, list) or not items or items[0].get("success") is not True:
            raise ProbeError("SQL_REPORTED_FAILURE")
        return items[0]
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ProbeError("INVALID_API_RESPONSE") from None


def read_only_check(*, account_id: str, database_id: str, token: str, opener=None) -> dict:
    """Runs only SELECT 1, changes neither the schema nor the rows."""
    result = _call(account_id, database_id, token, "SELECT 1 AS connection_ok", opener=opener)
    rows = result.get("results") or []
    passed = bool(rows and rows[0].get("connection_ok") == 1)
    return {"status": "PASS_READ_ONLY" if passed else "FAILED",
            "stage": "read_only_connection", "connected": passed,
            "real_database_persistence_tested": False}


def _rows(account_id, database_id, token, sql, params=None, *, opener=None):
    return _call(account_id, database_id, token, sql, params, opener=opener)


def write_once_check(*, account_id: str, database_id: str, token: str, opener=None) -> dict:
    """One opt-in synthetic record; no UPDATE/DELETE of existing data.

    Creates the dedicated test table only. A successful result is not a backup
    or a guarantee of long-term retention or immutability.
    """
    result = {"status": "FAILED", "stage": "start", "inserted": False,
              "readback": False, "duplicate_rejected": False,
              "independent_readback": False, "real_racing_data": False}
    rid = secrets.token_hex(16)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    digest = hashlib.sha256((rid + ":" + stamp).encode()).hexdigest()
    try:
        result["stage"] = "create_probe_table"
        _rows(account_id, database_id, token,
              "CREATE TABLE IF NOT EXISTS kyoto_probe_v15 ("
              "probe_id TEXT PRIMARY KEY, created_utc TEXT NOT NULL, sha256 TEXT NOT NULL)",
              opener=opener)
        result["stage"] = "insert"
        inserted = _rows(account_id, database_id, token,
                         "INSERT OR IGNORE INTO kyoto_probe_v15 "
                         "(probe_id,created_utc,sha256) VALUES (?,?,?)",
                         [rid, stamp, digest], opener=opener)
        if inserted.get("meta", {}).get("changes") != 1:
            raise ProbeError("FIRST_INSERT_NOT_CONFIRMED")
        result["inserted"] = True
        result["stage"] = "readback"
        read = _rows(account_id, database_id, token,
                     "SELECT created_utc,sha256 FROM kyoto_probe_v15 WHERE probe_id=?",
                     [rid], opener=opener)
        expected = {"created_utc": stamp, "sha256": digest}
        if read.get("results") != [expected]:
            raise ProbeError("READBACK_MISMATCH")
        result["readback"] = True
        result["stage"] = "duplicate_insert"
        duplicate = _rows(account_id, database_id, token,
                          "INSERT OR IGNORE INTO kyoto_probe_v15 "
                          "(probe_id,created_utc,sha256) VALUES (?,?,?)",
                          [rid, "ALTERED", "ALTERED"], opener=opener)
        if duplicate.get("meta", {}).get("changes") != 0:
            raise ProbeError("DUPLICATE_NOT_REJECTED")
        result["duplicate_rejected"] = True
        result["stage"] = "second_readback"
        second = _rows(account_id, database_id, token,
                       "SELECT created_utc,sha256 FROM kyoto_probe_v15 WHERE probe_id=?",
                       [rid], opener=opener)
        if second.get("results") != [expected]:
            raise ProbeError("SECOND_READBACK_MISMATCH")
        result["independent_readback"] = True
        result["stage"] = "complete"
        result["status"] = "PASS_CONNECTIVITY_ONLY"
    except ProbeError as exc:
        result["error_code"] = str(exc)
    except Exception:
        result["error_code"] = "UNEXPECTED_ERROR"
    return result
