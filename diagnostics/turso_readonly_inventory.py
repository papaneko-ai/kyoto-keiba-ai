"""Turso dedicated test DB read-only metadata probe (no Secrets output).

This module never changes data. External access requires explicit credentials
supplied by an authorized operator; running unit tests makes no HTTP requests.
"""
from __future__ import annotations
import json
import os
import re
from urllib.parse import urlsplit
import requests

EXPECTED_HOST="kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io"
EXPECTED_URL="libsql://"+EXPECTED_HOST
ALLOWED_SQL=(
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name LIMIT 100",
    "PRAGMA query_only",
)

def validate_url(url):
    if not isinstance(url,str):
        raise ValueError("Turso URL required")
    p=urlsplit(url.strip())
    if (p.scheme not in ("libsql","https") or
        p.hostname != EXPECTED_HOST or p.port is not None or p.username or
        p.password or p.query or p.fragment or p.path not in ("","/")):
        raise ValueError("Only isolated Kyoto Turso test database permitted")
    return "https://"+EXPECTED_HOST+"/v2/pipeline"

def validate_token(token):
    if (not isinstance(token,str) or len(token)<16 or
       re.search(r"\s",token):
        raise ValueError("A nonempty secret token is required")
    return token

def read_only_sql(sql):
    if sql not in ALLOWED_SQL:
        raise ValueError("Only fixed read-only metadata statements allowed")
    return sql

def inventory(*,database_url,auth_token,timeout=15):
    endpoint=validate_url(database_url)
    token=validate_token(auth_token)
    statement=read_only_sql(ALLOWED_SQL[0])
    req={"requests":[{"type":"execute","stmt":{"sql":statement,
         "args":[],"want_rows":True}},{"type":"close"}]}
    try:
        resp=requests.post(endpoint,
            headers={"Authorization":"Bearer "+token,
                     "Content-Type":"application/json"},
            json=req,timeout=timeout,allow_redirects=False)
        if resp.status_code!=200:
            raise RuntimeError("Turso read-only endpoint unavailable")
        entries=resp.json().get("results")
        if (not isinstance(entries,list) or len(entries)!=2 or
           entries[0].get("type")!="ok" or entries[1].get("type")!="ok"):
            raise RuntimeError("Turso response structure was not verified")
        result=entries[0].get("response",{}).get("result",{})
        table_names=[]
        for row in result.get("rows",[]):
            if not isinstance(row,list) or len(row)!=1:
                raise RuntimeError("Unexpected schema row")
            name=row[0].get("value")
            if (not isinstance(name,str) or
               re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",name) is None):
                raise RuntimeError("Invalid schema name")
            table_names.append(name)
        # Do not publish table or row contents, tokens, or SQL data as artifacts.
        return {"scope":"ISOLATED_TEST_DB_READONLY",
                "database":"kyoto-keiba-ai-test",
                "connection_verified":True,
                "table_count_visible":len(table_names),
                "full_database_backup_verified":False,
                "production_readiness_verified":False,
                "secrets_logged":False}
    except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
        raise RuntimeError("Read-only Turso inspection did not complete") from None

def main():
    url=os.environ.get("TURSO_DATABASE_URL","")
    token=os.environ.get("TURSO_AUTH_TOKEN","")
    # Neither print nor persist the credential values.
    report=inventory(database_url=url,auth_token=token)
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
