"""Turso connectivity probe; independent of Kyoto Keiba AI production application.

Dependencies already present in the repository: streamlit, requests.
Only touches the named diagnostic table, never existing production data.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
import streamlit as st

TABLE = "__kyoto_turso_probe_v1"


def endpoint(database_url):
    parsed = urlsplit(database_url.strip())
    if parsed.scheme not in ("libsql", "https") or not parsed.hostname:
        raise ValueError("Invalid Turso DB URL format")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Unexpected components in Turso DB URL")
    if not parsed.hostname.endswith(".turso.io"):
        raise ValueError("Expected a Turso-managed hostname")
    return "https://" + parsed.netloc + "/v2/pipeline"


def query(database_url, token, sql, params=()):
    args = [{"type": "text", "value": str(v)} for v in params]
    payload = {"requests": [
        {"type": "execute", "stmt": {"sql": sql, "args": args, "want_rows": True}},
        {"type": "close"},
    ]}
    response = requests.post(
        endpoint(database_url),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
        allow_redirects=False,
    )
    # Never print response contents or request headers: they can include sensitive details.
    if response.status_code != 200:
        raise RuntimeError("HTTP connection failure (status: %s)" % response.status_code)
    content = response.json()
    results = content.get("results", [])
    if not results or results[0].get("type") != "ok":
        raise RuntimeError("SQL request was rejected by server")
    return results[0]["response"]["result"]


def first_cell(result):
    return result["rows"][0][0]["value"]


def secrets():
    url = str(st.secrets.get("TURSO_DATABASE_URL", "")).strip()
    token = str(st.secrets.get("TURSO_AUTH_TOKEN", "")).strip()
    if not url or not token:
        raise ValueError("Missing TURSO_DATABASE_URL or TURSO_AUTH_TOKEN in this app's Secrets")
    return url, token


st.set_page_config(page_title="Kyoto Keiba AI | Turso diagnostic", page_icon="🧪")
st.title("Turso independent storage diagnostic (v1)")
st.caption("Independent test app. Does not import or change production app.py or v14 model code.")
st.warning("Only execute against the dedicated kyoto-keiba-ai-test database. Do not paste tokens in chat or screenshots.")

try:
    db_url, auth_token = secrets()
    # Show only a fingerprint, not connection URL, token or secrets.
    st.success("Connection settings present (values hidden).")
except Exception:
    st.info("Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in this diagnostic app's Secrets.")
    st.stop()

if st.button("1. Read-only SELECT 1"):
    try:
        value = first_cell(query(db_url, auth_token, "SELECT 1 AS ok"))
        st.success("Read test passed" if value == "1" else "Unexpected response")
    except Exception:
        st.error("Read test failed. See status in deployment logs without exposing Secrets.")

st.divider()
st.caption("Write tests only create/use one diagnostic table; run step 1 successfully first.")
if st.button("2. Create one test record and verify uniqueness"):
    try:
        query(db_url, auth_token, f"CREATE TABLE IF NOT EXISTS {TABLE} (id TEXT PRIMARY KEY, checksum TEXT NOT NULL, created_utc TEXT NOT NULL)")
        marker = str(uuid.uuid4())
        checksum = hashlib.sha256(marker.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        query(db_url, auth_token, f"INSERT INTO {TABLE} (id, checksum, created_utc) VALUES (?, ?, ?)", (marker, checksum, now))
        st.session_state["probe_id"] = marker
        st.session_state["probe_checksum"] = checksum
        found = query(db_url, auth_token, f"SELECT checksum FROM {TABLE} WHERE id = ?", (marker,))
        if first_cell(found) != checksum:
            raise RuntimeError("Readback mismatch")
        st.success("Write and readback passed; test record ID retained in current session")
        try:
            query(db_url, auth_token, f"INSERT INTO {TABLE} (id, checksum, created_utc) VALUES (?, ?, ?)", (marker, checksum, now))
        except RuntimeError:
            n = first_cell(query(db_url, auth_token, f"SELECT count(*) FROM {TABLE} WHERE id = ?", (marker,)))
            if n == "1":
                st.success("Duplicate ID rejected; exactly one row persisted")
            else:
                st.error("Duplicate prevention not proven")
        else:
            st.error("Duplicate ID was unexpectedly accepted")
    except Exception:
        st.error("Write test failed. No production data was changed.")

if "probe_id" in st.session_state:
    st.text_input("Test record ID (non-secret; save for restart check)", st.session_state["probe_id"], disabled=True)

probe_id = st.text_input("3. Previously saved test record ID (after reboot)", value="")
if st.button("3. Re-read an existing ID"):
    try:
        if not probe_id or len(probe_id) > 100:
            raise ValueError("Invalid ID")
        found = query(db_url, auth_token, f"SELECT count(*) FROM {TABLE} WHERE id = ?", (probe_id,))
        st.success("Record remains available" if first_cell(found) == "1" else "No matching record")
    except Exception:
        st.error("Re-read failed; ensure a test record exists before checking")

st.caption("A passing diagnostic does not verify prediction accuracy or tamper resistance.")
