"""Turso HTTP v2 remotely shared acquisition claims.

Uses an isolated *new* table, independent of production virtual wagers.
A single UPSERT ... RETURNING is the atomic arbitration point. A read after
ambiguous network failure never silently retries a mutation. Actual remote
credentials and production deployment are NOT part of the offline tests.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from diagnostics.kyoto_shared_capture_reservation import key,ReservationError

TABLE="__kyoto_ai_weekend_claims_v1"
LAB_TABLE="__kyoto_ai_weekend_claims_isolated_lab_v1"
CREATE=(f"CREATE TABLE IF NOT EXISTS {TABLE} ("
        "claim_key TEXT PRIMARY KEY NOT NULL,"
        "owner TEXT NOT NULL,"
        "generation INTEGER NOT NULL,"
        "expires_at INTEGER NOT NULL,"
        "state TEXT NOT NULL CHECK(state IN ('LEASED','DONE')),"
        "receipt_sha256 TEXT)")
CLAIM=(f"INSERT INTO {TABLE} (claim_key,owner,generation,expires_at,state,receipt_sha256) "
       "VALUES (?, ?, 1, ?, 'LEASED', NULL) "
       "ON CONFLICT(claim_key) DO UPDATE SET "
       "owner=excluded.owner, generation=generation+1, "
       "expires_at=excluded.expires_at, state='LEASED',receipt_sha256=NULL "
       f"WHERE {TABLE}.state='LEASED' AND {TABLE}.expires_at<=? "
       "RETURNING owner,generation,expires_at,state")
READ=(f"SELECT owner,generation,expires_at,state,receipt_sha256 "
      f"FROM {TABLE} WHERE claim_key=? LIMIT 1")
COMPLETE=(f"UPDATE {TABLE} SET state='DONE',receipt_sha256=? "
          "WHERE claim_key=? AND owner=? AND generation=? AND state='LEASED' "
          "RETURNING generation,receipt_sha256")
ABANDON=(f"UPDATE {TABLE} SET expires_at=? "
         "WHERE claim_key=? AND owner=? AND generation=? AND state='LEASED' "
         "RETURNING generation")
class TursoClaimUnconfirmed(RuntimeError):pass

def _text(v):
    return {"type":"text","value":str(v)}
def _stmt(sql,args):
    return {"type":"execute","stmt":{"sql":sql,
            "args":[_text(arg) for arg in args],"want_rows":True}}
def _cell(value):
    """Decode the Hrana wire format, including NULL without a value field."""
    if type(value) is not dict:
        raise ValueError("invalid Hrana cell")
    kind=value.get("type")
    if kind=="null" and set(value)=={"type"}:
        return None
    if kind in ("text","integer") and type(value.get("value")) is str:
        return value["value"]
    # This claims table has only textual and integer columns.
    raise ValueError("unexpected Hrana cell type")

def _rows(payload):
    try:
        rows=payload["rows"]
        if not isinstance(rows,list) or len(rows)>1:raise ValueError()
        if any(not isinstance(row,list) for row in rows):raise ValueError()
        return [[_cell(v) for v in row] for row in rows]
    except (TypeError,ValueError,KeyError,IndexError):
        raise TursoClaimUnconfirmed("remote_rows_unconfirmed") from None

class TursoCaptureClaims:
    def __init__(self,*,url,token,transport,namespace="OPERATIONAL"):
        if not isinstance(url,str):raise ReservationError("db_url_required")
        p=urlsplit(url)
        # Never write P6 isolated lab or accidentally target local filesystem.
        if (p.scheme not in ("https","libsql") or not p.hostname
            or not p.hostname.endswith(".turso.io") or p.path not in ("","/")
            or p.port is not None or p.query or p.fragment or p.username or p.password):
            raise ReservationError("remote_turso_url_invalid")
        if not isinstance(token,str) or len(token)<16 or any(c.isspace() for c in token):
            raise ReservationError("remote_claim_token_required")
        if not hasattr(transport,"post"):raise ReservationError("transport_required")
        if namespace not in ("OPERATIONAL","ISOLATED_LAB"):
            raise ReservationError("unknown_turso_capture_namespace")
        self.namespace=namespace
        self.table=LAB_TABLE if namespace=="ISOLATED_LAB" else TABLE
        self.endpoint="https://"+p.hostname+"/v2/pipeline"
        self.token=token
        self.transport=transport
    def _single(self,sql,*args):
        payload={"requests":[_stmt(sql,args),{"type":"close"}]}
        try:
            response=self.transport.post(
                self.endpoint,
                headers={"Authorization":"Bearer "+self.token,
                         "Content-Type":"application/json"},
                json=payload,timeout=12,allow_redirects=False)
            if response.status_code!=200:raise ValueError()
            body=response.json()
            results=body["results"]
            # Hrana v2 reports per-statement failures inside HTTP 200.
            # Identify only an allowlisted code, never an error message.
            if (self.namespace=="ISOLATED_LAB"
                and sql.lstrip().upper().startswith("SELECT ")
                and isinstance(results,list) and len(results)==2
                and isinstance(results[0],dict) and results[0].get("type")=="error"):
                err=results[0].get("error")
                code=err.get("code") if isinstance(err,dict) else None
                allowed={"SQLITE_BUSY","SQLITE_LOCKED","SQLITE_CONSTRAINT",
                         "SQLITE_ERROR","SQLITE_SCHEMA","SQLITE_READONLY"}
                lab_error_code=code if type(code) is str and code in allowed else "OTHER"
                raise ValueError()
            if len(results)!=2 or results[0]["type"]!="ok" or results[1]["type"]!="ok":
                raise ValueError()
            output=results[0]["response"]
            if output["type"]!="execute":raise ValueError()
            return _rows(output["result"])
        except Exception:
            # Only classify isolated-lab SELECT failures. Never output a raw
            # response, SQL data, credential, URL or exception message.
            if self.namespace=="ISOLATED_LAB" and sql.lstrip().upper().startswith("SELECT "):
                if "lab_error_code" in locals():
                    category="sql_"+lab_error_code.lower()
                elif "response" not in locals():
                    category="transport"
                else:
                    status=getattr(response,"status_code",None)
                    if type(status) is int and status!=200:
                        category="http_"+str(status) if status in (400,401,403,408,409,423,429,500,502,503,504) else "http_other"
                    else:
                        category="response_shape"
                raise TursoClaimUnconfirmed("isolated_read_"+category) from None
            raise TursoClaimUnconfirmed("mutation_or_read_unconfirmed_no_blind_retry") from None
    def prepare_schema(self):
        self._single(CREATE.replace(TABLE,self.table))
        return {"schema":self.table,"prepared":True,"unrelated_tables_modified":False}
    def observe(self,claim_key):
        # The isolated laboratory can reconcile a transient failed SELECT.
        # Only reads are repeated: INSERT/UPDATE/DDL must never be blindly replayed.
        # Keep operational (production) semantics completely unchanged.
        if self.namespace=="ISOLATED_LAB":
            import time
            for attempt in range(3):
                try:
                    data=self._single(READ.replace(TABLE,self.table),claim_key)
                    break
                except TursoClaimUnconfirmed as exc:
                    if attempt==2:
                        # Exc is already a strictly allowlisted category.
                        # Include no transport payload or exception details.
                        raise TursoClaimUnconfirmed(
                            "isolated_read_unconfirmed_after_3_safe_attempts:"+str(exc)) from None
                    time.sleep(0.15*(attempt+1))
        else:
            data=self._single(READ.replace(TABLE,self.table),claim_key)
        if not data:return None
        if len(data[0])!=5:raise TursoClaimUnconfirmed("read_shape_unconfirmed")
        a,b,c,d,e=data[0]
        return {"owner":a,"generation":int(b),"expires_at":int(c),
                "state":d,"receipt_sha256":e}
    def claim(self,*,claim_key,owner,now_epoch,lease_seconds=180):
        pattern=r"2026112[12]:[0-3]:(0[1-9]|1[0-2]):(PC|SP):(racecard|quinella|bracket_quinella|profile)"
        if self.namespace=="ISOLATED_LAB":
            pattern=r"(?:lab:[0-9]{8,20}:)?"+pattern
        if not isinstance(claim_key,str) or not re.fullmatch(pattern,claim_key):
            raise ReservationError("claim_key_invalid")
        if not isinstance(owner,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{5,100}",owner):
            raise ReservationError("owner_invalid")
        if type(now_epoch) is not int or now_epoch<=0 or type(lease_seconds) is not int or not 30<=lease_seconds<=600:
            raise ReservationError("lease_parameters_invalid")
        result=self._single(CLAIM.replace(TABLE,self.table),claim_key,owner,now_epoch+lease_seconds,now_epoch)
        if len(result)==1:
            if len(result[0])!=4 or result[0][0]!=owner or result[0][3]!="LEASED":
                raise TursoClaimUnconfirmed("claim_owner_not_proven")
            return {"state":"ACQUIRED","generation":int(result[0][1]),"must_fetch":True}
        observation=self.observe(claim_key)
        if observation is None:raise TursoClaimUnconfirmed("claim_absent_after_collision")
        if observation["state"]=="DONE":
            return {"state":"DONE_REUSE_EXISTING","generation":observation["generation"],
                    "receipt_sha256":observation["receipt_sha256"],"must_fetch":False}
        if observation["expires_at"]>now_epoch:
            return {"state":"ACTIVE_LEASE","generation":observation["generation"],"must_fetch":False}
        # Another worker may release between failed insert and read; defer
        # to the next request window instead of busy-spinning.
        return {"state":"LEASE_CHANGED_RECONCILE","must_fetch":False}
    def complete(self,*,claim_key,owner,generation,sha256):
        if type(generation) is not int or generation<1 or not isinstance(sha256,str) or not re.fullmatch(r"[a-f0-9]{64}",sha256):
            raise ReservationError("completion_invalid")
        rows=self._single(COMPLETE.replace(TABLE,self.table),sha256,claim_key,owner,generation)
        return {"state":"COMMITTED" if rows else "FENCE_REJECTED","committed":bool(rows)}
    def abandon(self,*,claim_key,owner,generation,now_epoch):
        if type(generation) is not int or generation<1 or type(now_epoch) is not int:
            raise ReservationError("abandon_invalid")
        rows=self._single(ABANDON.replace(TABLE,self.table),now_epoch,claim_key,owner,generation)
        return {"released":bool(rows)}
