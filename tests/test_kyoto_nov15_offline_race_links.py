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
      "selection_source":OFFICIAL_ENTRY,"day":DAY,"racecard_original_fetched":False,
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
 def test_raw_racecard_source_evidence_propagates_without_market_claim(self):
    raw=source("<table><tr><td>saved unverified original</td></tr></table>")
    (self.root/"official_racecard.html").write_bytes(raw)
    path=self.root/"receipt.json"
    r=json.loads(path.read_text(encoding="utf8"))
    r.update({"state":"NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",
              "racecard_original_fetched":True,
              "racecard_number":1,"observed_racecard_url":RACE,
              "racecard_sha256":hashlib.sha256(raw).hexdigest(),
              "racecard_bytes":len(raw),
              "racecard_captured_at_utc":"2026-11-15T02:00:03+00:00"})
    path.write_text(json.dumps(r),encoding="utf8")
    result=derive_nov15_race_links(self.root)
    self.assertTrue(result["racecard_originals_fetched"])
    self.assertEqual(result["saved_racecard_original"]["sha256"],hashlib.sha256(raw).hexdigest())
    self.assertEqual(result["saved_racecard_original"]["race_number"],1)
    self.assertFalse(result["roster_verified"])
    self.assertFalse(result["quinella_market_verified"])
    self.assertFalse(result["bracket_market_verified"])
 def test_forged_saved_racecard_url_rejected_even_with_matching_sha(self):
    raw=source("<html>source</html>")
    (self.root/"official_racecard.html").write_bytes(raw)
    path=self.root/"receipt.json"
    r=json.loads(path.read_text(encoding="utf8"))
    r.update({"state":"NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",
              "racecard_original_fetched":True,
              "racecard_number":1,"observed_racecard_url":"https://jra.jp/JRADB/accessD.html?CNAME=pw020abc01%2F0120261115",
              "racecard_sha256":hashlib.sha256(raw).hexdigest(),
              "racecard_bytes":len(raw)})
    path.write_text(json.dumps(r),encoding="utf8")
    with self.assertRaises((OfflineRaceLinkRejected,ValueError)):
        derive_nov15_race_links(self.root)
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
 def test_downstream_handoff_retains_link_evidence_prior_to_market_http(self):
    wf=Path(".github/workflows/kyoto-nov15-second-day-observed-oneshot.yml").read_text(encoding="utf8")
    self.assertIn("--output nov15_pc_one_shot/observed_race_links.json",wf)
    self.assertIn("python -m diagnostics.kyoto_nov15_offline_race_links",wf)
    self.assertLess(wf.index("python -m diagnostics.kyoto_nov15_offline_race_links"),
      wf.index("Single bounded Nov15 observed PC racecard and market fetch"))
    self.assertIn("python -m diagnostics.kyoto_nov15_full_capture_seal",wf)
 def test_has_no_external_http_import_or_live_flag(self):
    code=Path("diagnostics/kyoto_nov15_offline_race_links.py").read_text()
    self.assertNotIn("urlopen(",code)
    self.assertNotIn("requests.get(",code)
    self.assertNotIn("authorized_live_http",code)
if __name__=="__main__":unittest.main()
