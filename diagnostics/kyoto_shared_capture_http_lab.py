"""Optional HTTP coordinator for multiple independent capture runtimes.

One shared transactional backend is required. The service is never started
implicitly and never visits JRA. Test credentials are synthetic only.
"""
import hmac,json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request,build_opener,HTTPRedirectHandler
from diagnostics.kyoto_shared_capture_reservation import SharedLedger,ReservationError

ALLOWED=frozenset(("claim","complete","abandon"))
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a):raise ReservationError("coordinator_redirect_refused")

def make_handler(database,secret):
    if not isinstance(secret,str) or len(secret)<16:raise ReservationError("shared_secret_missing")
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path!="/capture-claim/v1":
                self.send_error(404);return
            if not hmac.compare_digest(self.headers.get("X-Capture-Token",""),secret):
                self.send_error(401);return
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 1<=length<=4096:raise ReservationError("request_size_invalid")
                obj=json.loads(self.rfile.read(length))
                if type(obj) is not dict or obj.get("action") not in ALLOWED:
                    raise ReservationError("invalid_action")
                action=obj.pop("action")
                db=SharedLedger(database)
                try:
                    output=getattr(db,action)(**obj)
                finally:
                    db.close()
                raw=json.dumps(output,sort_keys=True).encode("utf8")
                self.send_response(200)
            except (TypeError,ValueError,KeyError,ReservationError):
                raw=b'{"error":"invalid_or_unconfirmed_claim"}'
                self.send_response(400)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self,*args):pass
    return Handler

def create_server(host,port,database,secret):
    if host not in ("127.0.0.1","::1"):
        raise ReservationError("lab_server_loopback_only")
    return ThreadingHTTPServer((host,port),make_handler(database,secret))

def request_claim(url,secret,action,**payload):
    if not url.startswith("http://127.0.0.1:"):
        raise ReservationError("unsupported_lab_endpoint")
    raw=json.dumps(dict(action=action,**payload),sort_keys=True).encode("utf8")
    req=Request(url,method="POST",data=raw,headers={"Content-Type":"application/json",
                "X-Capture-Token":secret})
    with build_opener(NoRedirect()).open(req,timeout=6) as r:
        if r.status!=200:raise ReservationError("remote_claim_unconfirmed")
        out=r.read(4096)
    return json.loads(out)
