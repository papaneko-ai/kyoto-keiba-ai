"""Offline safety tests: all external HTTP calls replaced with fake responses."""
import io
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from diagnostics.jra_historical_two_day_source_capture import (
 KNOWN,HistoricalRejected,parse_official_result_identity,capture_one,validate_identity
)
def html(date,race):
 y,m,d=map(int,date.split("-"))
 return (f"<html><head><title>レース結果</title></head><body>"
         f"<h1>{y}年{m}月{d}日 5回京都2日 {race}レース</h1>"
         f"<h2>レース結果</h2><table><tr><th>着順</th><th>馬名</th>"
         f"</tr><tr><td>1</td><td>検証用</td></tr></table>"
         f"</body></html>").encode("cp932")
class Response:
 def __init__(self,raw,url,content_type="text/html"):
  self.raw=io.BytesIO(raw);self.url=url;self.headers={"Content-Type":content_type}
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def read(self,n=-1):return self.raw.read(n)
 def getcode(self):return 200
 def geturl(self):return self.url
class Open:
 def __init__(self,resp):self.resp=resp
 def open(self,request,timeout):
  assert timeout==15
  return self.resp
class Safety(unittest.TestCase):
 def test_two_dates(self):
  for date,race,url in KNOWN:
   self.assertTrue(validate_identity(date,race,url))
   r=parse_official_result_identity(html(date,race),date,race,url)
   self.assertTrue(r["post_race_result_identity_verified"])
   self.assertFalse(r["official_prerace_odds"])
   self.assertFalse(r["training_ready"])
 def test_guessed_url_rejected(self):
  date,race,url=KNOWN[0]
  for other in (url+"x",url.replace("www.jra.go.jp","fake.invalid"),url.replace("accessS","accessD")):
   with self.assertRaises(HistoricalRejected):validate_identity(date,race,other)
 def test_wrong_date(self):
  date,race,url=KNOWN[0]
  with self.assertRaises(HistoricalRejected):
   parse_official_result_identity(html("2026-11-08",race),date,race,url)
 def test_wrong_race(self):
  date,race,url=KNOWN[0]
  with self.assertRaises(HistoricalRejected):
   parse_official_result_identity(html(date,5),date,race,url)
 def test_no_table(self):
  date,race,url=KNOWN[0]
  raw=html(date,race).replace(b"<table>",b"<div>").replace(b"</table>",b"</div>")
  with self.assertRaises(HistoricalRejected):parse_official_result_identity(raw,date,race,url)
 def test_missing_result_label(self):
  date,race,url=KNOWN[0]
  raw=html(date,race).replace("レース結果".encode("cp932"),"開催情報".encode("cp932"))
  with self.assertRaises(HistoricalRejected):parse_official_result_identity(raw,date,race,url)
 def test_size_cap(self):
  date,race,url=KNOWN[0]
  with self.assertRaises(HistoricalRejected):
   parse_official_result_identity(html(date,race)+b"x"*2_100_000,date,race,url)
 def test_save_receipt_no_overwrite(self):
  date,race,url=KNOWN[0]
  with tempfile.TemporaryDirectory() as temp:
   r=capture_one(date,race,url,temp,opener=Open(Response(html(date,race),url)),
     clock=lambda:datetime(2026,11,12,tzinfo=timezone.utc))
   self.assertEqual(r["date"],date)
   self.assertTrue((Path(temp)/"20261025_kyoto_10.html").is_file())
   with self.assertRaises(HistoricalRejected):
    capture_one(date,race,url,temp,opener=Open(Response(html(date,race),url)))
 def test_redirect_rejected(self):
  date,race,url=KNOWN[0]
  with tempfile.TemporaryDirectory() as temp:
   with self.assertRaises(HistoricalRejected):
    capture_one(date,race,url,temp,opener=Open(Response(html(date,race),url+"/other")))
 def test_wrong_mime_rejected(self):
  date,race,url=KNOWN[0]
  with tempfile.TemporaryDirectory() as temp:
   with self.assertRaises(HistoricalRejected):
    capture_one(date,race,url,temp,opener=Open(Response(html(date,race),url,content_type="application/pdf")))
if __name__=="__main__":unittest.main()
