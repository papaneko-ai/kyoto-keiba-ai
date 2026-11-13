"""Offline observation-link extraction: no network, no guessing, fail-closed."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_nov15_offline_race_links import derive_nov15_race_links,OfflineRaceLinkRejected
from diagnostics.jra_official_link_repair import OFFICIAL_ENTRY

DAY="20261115"
MEETING="https://jra.jp/JRADB/accessD.html?CNAME=pw00abc00%2F20261115"
RACE="https://jra.jp/JRADB/accessD.html?CNAME=pw020aaa01%2F0120261115"
def source(content):
    return ("<html><head><meta charset='shift_jis'></head><body>"+content+"</body></html>").encode("cp932")

class OfflineRaceLinksTests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory()
    self.addCleanup(self.tmp.cleanup)
    self.root=Path(self.tmp.name)
    selection=source('<a href="/JRADB/accessD.html?CNAME=pw00abc00%2F20261115">京都 20261115</a>')
    meeting=source('<a href="/JRADB/accessD.html?CNAME=pw020aaa01%2F0120261115">京都 1R</a>')
    (self.root/"official_selection.html").write_bytes(selection)
    (self.root/"official_meeting.html").write_bytes(meeting)
    (self.root/"receipt.json").write_text(json.dumps({
      "state":"NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD",
      "observed_meeting_url":MEETING,"meeting_label":"京都 20261115",
      "selection_sha256":hashlib.sha256(selection).hexdigest(),"selection_bytes":len(selection),
      "meeting_sha256":hashlib.sha256(meeting).hexdigest(),"meeting_bytes":len(meeting),
      "http_requests_started":2}),encoding="utf8")
 def test_observed_race_link_only(self):
    d=derive_nov15_race_links(self.root)
    self.assertEqual(d["race_links"][0]["race_number"],1)
    self.assertEqual(d["race_links"][0]["url"],RACE)
    self.assertEqual(d["http_requests"],0)
    self.assertFalse(d["start_times_verified"])
    self.assertFalse(d["roster_verified"])
 def test_tampered_meeting_rejected(self):
    (self.root/"official_meeting.html").write_bytes(b"tamper")
    with self.assertRaises(OfflineRaceLinkRejected):derive_nov15_race_links(self.root)
 def test_no_guessed_race_links(self):
    (self.root/"official_meeting.html").write_bytes(source("京都 1R"))
    receipt=json.loads((self.root/"receipt.json").read_text())
    raw=(self.root/"official_meeting.html").read_bytes()
    receipt["meeting_sha256"]=hashlib.sha256(raw).hexdigest()
    receipt["meeting_bytes"]=len(raw)
    (self.root/"receipt.json").write_text(json.dumps(receipt))
    self.assertEqual(derive_nov15_race_links(self.root)["race_links"],[])
 def test_ambiguous_link_refused(self):
    raw=source('<a href="/JRADB/accessD.html?CNAME=pw020aaa01%2F0120261115">京都 1R</a><a href="/JRADB/accessD.html?CNAME=pw020bbb01%2F0120261115">京都 1R</a>')
    (self.root/"official_meeting.html").write_bytes(raw)
    receipt=json.loads((self.root/"receipt.json").read_text())
    receipt["meeting_sha256"]=hashlib.sha256(raw).hexdigest()
    receipt["meeting_bytes"]=len(raw)
    (self.root/"receipt.json").write_text(json.dumps(receipt))
    with self.assertRaises(OfflineRaceLinkRejected):derive_nov15_race_links(self.root)
 def test_has_no_external_http_import_or_live_flag(self):
    code=Path("diagnostics/kyoto_nov15_offline_race_links.py").read_text()
    self.assertNotIn("urlopen(",code)
    self.assertNotIn("requests.get(",code)
    self.assertNotIn("authorized_live_http",code)
if __name__=="__main__":unittest.main()
