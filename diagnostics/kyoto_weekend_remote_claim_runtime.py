"""Opt-in Turso shared source claim client for weekend G06.

All eight scheduled slots derive from the ACTUAL workflow cron, never from
guessing clock hours. When NOT explicitly activated the entire source
capture keeps its original, unrestricted path. No DB schema creation,
credential mutation or JRA HTTP happens during configuration.
"""
from __future__ import annotations
import json,os,re,time
from urllib.request import Request,build_opener,HTTPRedirectHandler
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
from diagnostics.kyoto_shared_capture_reservation import ReservationError
from diagnostics.kyoto_turso_isolated_virtual_store import EXPECTED_HOST

CRON_SLOTS={
 "20261121":{"15 0 21 11 *":0,"15 1 21 11 *":1,
             "5 2 21 11 *":2,"50 2 21 11 *":3},
 "20261122":{"15 0 22 11 *":0,"15 1 22 11 *":1,
             "10 2 22 11 *":2,"55 2 22 11 *":3},
}
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):
        raise ReservationError("coordinator_redirect_forbidden")
class Response:
    def __init__(self,status,raw):
        self.status_code=status
        self.raw=raw
    def json(self):
        return json.loads(self.raw)
class UrllibTransport:
    def __init__(self):
        self.client=build_opener(NoRedirect())
    def post(self,url,headers,json,timeout,allow_redirects):
        if allow_redirects is not False:
            raise ReservationError("redirects_must_be_disabled")
        body=__import__("json").dumps(json,separators=(",",":")).encode("utf8")
        request=Request(url,data=body,headers=headers,method="POST")
        with self.client.open(request,timeout=timeout) as reply:
            return Response(reply.status,reply.read(1_000_000))

def active_claims_for_weekend(day,*,environ=None,transport=None,now_epoch=None):
    env=environ if environ is not None else os.environ
    if env.get("KYOTO_SHARED_CLAIM_ACTIVATE")!="YES":
        return {"enabled":False,"reason":"OPTIONAL_NOT_CONFIGURED"}
    if day not in CRON_SLOTS or env.get("GITHUB_EVENT_NAME")!="schedule":
        return {"enabled":False,"reason":"NON_SCHEDULED_EVENT_NO_ARBITRARY_SLOT"}
    cron=env.get("GITHUB_EVENT_SCHEDULE","")
    if cron not in CRON_SLOTS[day]:
        raise ReservationError("scheduled_slot_not_recognized")
    url=env.get("KYOTO_SHARED_CLAIM_TURSO_URL","")
    expected="libsql://"+EXPECTED_HOST
    if url!=expected:
        raise ReservationError("isolated_remote_database_not_approved")
    token=env.get("KYOTO_SHARED_CLAIM_TURSO_TOKEN","")
    if not isinstance(token,str) or len(token)<16:
        raise ReservationError("shared_claim_token_missing")
    run=env.get("GITHUB_RUN_ID","")
    job=env.get("GITHUB_JOB","")
    owner="github_"+run+"_"+job
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,100}",owner):
        raise ReservationError("unverified_lease_owner")
    client=TursoCaptureClaims(url=url,token=token,
           transport=transport or UrllibTransport())
    return {"enabled":True,"claim_client":client,
            "claim_slot":CRON_SLOTS[day][cron],"claim_owner":owner,
            "claim_now_epoch":int(time.time()) if now_epoch is None else now_epoch}
