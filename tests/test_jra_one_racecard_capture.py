import unittest
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from diagnostics.jra_one_racecard_capture import validate_url,capture
URL='https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604100120261031%2F52'
class Fake:
 status=200
 headers={'Content-Type':'text/html; charset=Shift_JIS'}
 def __init__(self,b,url=URL):self.b=b;self.url=url;self.calls=0
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def geturl(self):return self.url
 def read(self,n):self.calls+=1;return self.b[:n]
class TestManualCapture(unittest.TestCase):
 def test_single_get_and_proof(self):
  r=Fake('<title>出馬表 JRA</title><table></table>'.encode('cp932'));calls=[]
  def op(req,timeout):calls.append((req.get_method(),timeout));return r
  with TemporaryDirectory() as d:
   report=capture(URL,d,opener=op,at=lambda:datetime(2026,11,6,tzinfo=timezone.utc))
   self.assertEqual(calls,[('GET',15)]);self.assertEqual(r.calls,1)
   self.assertTrue((Path(d)/'jra_racecard_response.html').exists())
   self.assertFalse(report['ready_for_prediction'])
 def test_untrusted_urls(self):
  for u in ('https://bad.example/JRADB/accessD.html?CNAME=x','https://www.jra.go.jp/JRADB/accessR.html?CNAME=x'):
   with self.assertRaises(ValueError):validate_url(u)
 def test_empty_rejected(self):
  with TemporaryDirectory() as d:
   with self.assertRaises(ValueError):capture(URL,d,opener=lambda *a,**kw:Fake(b''))
 def test_external_redirect(self):
  with TemporaryDirectory() as d:
   with self.assertRaises(ValueError):capture(URL,d,opener=lambda *a,**kw:Fake(b'<title>X</title><table></table>','https://bad.example'))
 def test_no_false_receipt(self):
  with TemporaryDirectory() as d:
   with self.assertRaises(ValueError):capture(URL,d,opener=lambda *a,**kw:Fake(b'not html'))
   self.assertEqual(list(Path(d).iterdir()),[])
if __name__=='__main__':unittest.main()
