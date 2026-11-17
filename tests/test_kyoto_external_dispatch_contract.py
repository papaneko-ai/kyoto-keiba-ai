"""Offline HTTP-contract tests. Never contacts JRA or GitHub."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from diagnostics.kyoto_external_dispatch_contract import PATH, CONFIRM, payload

class Handler(BaseHTTPRequestHandler):
    records=[]
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get("Content-Length","0")))
        try:
            request=json.loads(raw)
            assert self.path==PATH
            assert self.headers.get("Authorization")=="Bearer DUMMY-LOCAL-ONLY"
            assert request["ref"]=="main"
            assert request["inputs"]["confirmation"]==CONFIRM
            assert request["inputs"]["race_day"] in ("20261121","20261122")
        except (AssertionError,ValueError,KeyError,TypeError):
            self.send_response(403);self.end_headers();return
        self.records.append(request)
        self.send_response(204);self.end_headers()
    def log_message(self,*args):pass

class DispatchTests(unittest.TestCase):
    def test_only_two_agreed_days(self):
        for day in ("20261120","20261123","",None):
            with self.assertRaises(ValueError):payload(day)
    def test_json_exact_contract(self):
        d=json.loads(payload("20261121"))
        self.assertEqual(set(d),{"ref","inputs"})
        self.assertEqual(d["inputs"],{"race_day":"20261121","confirmation":CONFIRM})
    def test_mock_http_two_days_auth_rejection(self):
        Handler.records=[]
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
        url="http://127.0.0.1:"+str(server.server_port)+PATH
        try:
            for day in ("20261121","20261122"):
                req=Request(url,payload(day),headers={"Authorization":"Bearer DUMMY-LOCAL-ONLY","Content-Type":"application/json"},method="POST")
                with urlopen(req,timeout=3) as response:self.assertEqual(response.status,204)
            bad=Request(url,payload("20261121"),headers={"Authorization":"Bearer WRONG"},method="POST")
            with self.assertRaises(HTTPError) as exc:urlopen(bad,timeout=3)
            self.assertEqual(exc.exception.code,403)
            self.assertEqual(len(Handler.records),2)
        finally:
            server.shutdown();server.server_close();th.join(timeout=3)

if __name__=="__main__":unittest.main()
