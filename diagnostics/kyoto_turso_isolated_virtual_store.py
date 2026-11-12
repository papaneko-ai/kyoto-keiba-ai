"""Turso isolated test-DB-only remote virtual journal transport.

UNAUTHENTICATED LAB records only; no production writes, real bets, JRA calls,
or unattended scheduled requests. Uses HTTP v2 pipeline and strictly fixed
identifiers with bound values. No retries of ambiguous mutating requests.
A remote conflict is never silently treated as a successful identical replay.
Isolated test database must be separately approved before LIVE invocation.
"""
from __future__ import annotations
import hashlib
import json
from urllib.parse import urlsplit

from diagnostics.kyoto_virtual_sqlite_journal import (
    validate_freeze,validate_final,canonical,sha,VirtualLedgerRejected,
)

EXPECTED_HOST="kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io"
TABLE="__kyoto_ai_p6_lab_v1_events"
TIMEOUT=12

class TursoLabRejected(ValueError):pass
class TursoAmbiguous(RuntimeError):pass

def endpoint(url):
    if not isinstance(url,str):raise TursoLabRejected("url_missing")
    p=urlsplit(url)
    if p.scheme not in ("https","libsql") or p.hostname!=EXPECTED_HOST or (
        p.port is not None or p.username or p.password or p.query or p.fragment
        or p.path not in ("","/")):
        raise TursoLabRejected("non_isolated_turso_target_rejected")
    return "https://"+EXPECTED_HOST+"/v2/pipeline"

def _strval(value):
    if type(value) is not str or not value:
        raise TursoLabRejected("empty_or_nontext_sql_parameter")
    return {"type":"text","value":value}

def _stmt(sql,*args):
    return {"type":"execute","stmt":{"sql":sql,"args":[_strval(x) for x in args],"want_rows":True}}

SCHEMA_SQL=(f"CREATE TABLE IF NOT EXISTS {TABLE} ("
            "event_key TEXT PRIMARY KEY NOT NULL,"
            "race_id TEXT NOT NULL,"
            "event_type TEXT NOT NULL CHECK(event_type IN ('FREEZE','FINAL')),"
            "payload TEXT NOT NULL,"
            "payload_sha256 TEXT NOT NULL,"
            "created_scope TEXT NOT NULL CHECK(created_scope='UNAUTHENTICATED_LAB_ONLY'))")
INSERT_SQL=(f"INSERT INTO {TABLE} (event_key,race_id,event_type,payload,payload_sha256,created_scope) "
            "VALUES (?,?,?,?,?,'UNAUTHENTICATED_LAB_ONLY') "
            "ON CONFLICT(event_key) DO NOTHING")
SELECT_SQL=(f"SELECT race_id,event_type,payload,payload_sha256,created_scope "
            f"FROM {TABLE} WHERE event_key=? LIMIT 2")
RACE_SQL=(f"SELECT event_key,event_type,payload,payload_sha256 FROM {TABLE} "
          "WHERE race_id=? ORDER BY event_key LIMIT 40")

class TursoLabStore:
    def __init__(self, *, database_url, token, transport):
        self.endpoint=endpoint(database_url)
        if not isinstance(token,str) or len(token)<16 or any(ch.isspace() for ch in token):
            raise TursoLabRejected("credential_required")
        if not hasattr(transport,"post"):
            raise TursoLabRejected("http_transport_required")
        self._token=token
        self._transport=transport

    def _pipeline(self,actions):
        # Do not log credentials or echo transport exceptions (which may
        # contain Authorization/header or URL details). No automatic retries.
        request={"requests":actions+[{"type":"close"}]}
        try:
            response=self._transport.post(
                self.endpoint,
                headers={"Authorization":"Bearer "+self._token,"Content-Type":"application/json"},
                json=request,timeout=TIMEOUT,allow_redirects=False)
        except Exception:
            raise TursoAmbiguous("remote_transport_unconfirmed_no_retry") from None
        if getattr(response,"status_code",None)!=200:
            raise TursoAmbiguous("remote_http_status_unconfirmed_no_retry")
        try:
            body=response.json()
            results=body["results"]
            if type(results) is not list or len(results)!=len(actions)+1 or results[-1].get("type")!="ok":
                raise ValueError("pipeline envelope")
            answers=[]
            for item in results[:-1]:
                if item.get("type")!="ok" or item.get("response",{}).get("type")!="execute":
                    raise ValueError("query not confirmed")
                answers.append(item["response"]["result"])
            return answers
        except (ValueError,TypeError,KeyError,IndexError,AttributeError):
            raise TursoAmbiguous("remote_response_unconfirmed_no_retry") from None

    def _single(self,sql,*args):
        return self._pipeline([_stmt(sql,*args)])[0]

    @staticmethod
    def _cells(result):
        try:
            return [[col["value"] for col in row] for row in result["rows"]]
        except (KeyError,TypeError,IndexError):
            raise TursoAmbiguous("remote_row_format_unconfirmed") from None

    def prepare_isolated_namespace(self):
        # This is a WRITE; explicit opt-in from operator required for REAL use.
        self._single(SCHEMA_SQL)
        return {"scope":"TURSO_ISOLATED_LAB_NAMESPACE_SCHEMA_PREPARED",
                "production_operational_ready":False}

    def _read_event(self,key):
        values=self._cells(self._single(SELECT_SQL,key))
        if len(values)>1:raise TursoAmbiguous("duplicate_remote_primary_key")
        if not values:return None
        if len(values[0])!=5:
            raise TursoAmbiguous("remote_event_shape_invalid")
        race,kind,raw,digest,scope=values[0]
        if scope!="UNAUTHENTICATED_LAB_ONLY" or not isinstance(raw,str):
            raise TursoAmbiguous("remote_scope_changed")
        try:p=json.loads(raw)
        except (TypeError,ValueError):
            raise TursoAmbiguous("remote_payload_not_json") from None
        if canonical(p)!=raw or sha(p)!=digest:
            raise TursoAmbiguous("remote_event_hash_mismatch")
        return {"race_id":race,"event_type":kind,"payload":p,
                "payload_sha256":digest}

    def append_freeze_lab(self,freeze):
        validate_freeze(freeze)
        key="freeze:"+freeze["race_id"]
        return self._append(key,freeze["race_id"],"FREEZE",freeze)

    def append_final_lab(self,final):
        if not isinstance(final,dict) or not isinstance(final.get("race_id"),str):
            raise TursoLabRejected("result_identity_invalid")
        race=final["race_id"]
        parent=self._read_event("freeze:"+race)
        if not parent or parent["event_type"]!="FREEZE" or parent["race_id"]!=race:
            raise TursoLabRejected("result_without_remote_freeze")
        validate_final(final,parent["payload"])
        if type(final["result_version"]) is not int:
            raise TursoLabRejected("result_version_invalid")
        version=final["result_version"]
        if version>1 and self._read_event("final:"+race+":"+str(version-1)) is None:
            raise TursoLabRejected("result_version_gap")
        return self._append("final:"+race+":"+str(version),race,"FINAL",final)

    def _append(self,key,race,kind,payload):
        before=self._read_event(key)
        expected={"race_id":race,"event_type":kind,"payload":payload,
                  "payload_sha256":sha(payload)}
        if before is not None:
            if before!=expected:
                raise TursoLabRejected("immutable_idempotency_conflict")
            return {"status":"ALREADY_PRESENT","payload_sha256":expected["payload_sha256"]}
        # A UNIQUE key is the cross-client arbitration point.
        # Timeout or 5xx is an ambiguous result: operator MUST reconcile
        # by read-only lookup; DO NOT retry automatically.
        result=self._single(INSERT_SQL,key,race,kind,canonical(payload),sha(payload))
        affected=result.get("affected_row_count")
        if str(affected) not in ("0","1"):
            raise TursoAmbiguous("affected_count_unconfirmed")
        saved=self._read_event(key)
        if saved!=expected:
            if saved is None:raise TursoAmbiguous("insert_not_visible")
            raise TursoLabRejected("immutable_idempotency_conflict")
        return {"status":"APPENDED" if str(affected)=="1" else "ALREADY_PRESENT",
                "payload_sha256":expected["payload_sha256"]}

    def read_race_lab(self,race_id):
        if not isinstance(race_id,str) or len(race_id)>40:
            raise TursoLabRejected("race_identity_invalid")
        data=self._cells(self._single(RACE_SQL,race_id))
        found=[]
        for row in data:
            if len(row)!=4:raise TursoAmbiguous("remote_race_shape_invalid")
            key,kind,raw,digest=row
            try:p=json.loads(raw)
            except (ValueError,TypeError):
                raise TursoAmbiguous("invalid_saved_json") from None
            if not key.startswith(("freeze:"+race_id,"final:"+race_id+":")) or canonical(p)!=raw or sha(p)!=digest:
                raise TursoAmbiguous("saved_race_event_invalid")
            found.append({"key":key,"type":kind,"payload":p,"sha256":digest})
        return {"race_id":race_id,"events":found,
                "source_scope":"UNAUTHENTICATED_LAB_ONLY",
                "production_validated":False}
