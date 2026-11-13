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
    self.assertEqual(d["hybrid_experiment"]["state"],"INCOMPLETE_PC_ONLY_SP_MISSING")
    self.assertFalse(d["hybrid_experiment"]["full_hybrid_experiment_pass"])
    self.assertFalse(d["hybrid_experiment"]["SP"]["racecard_original_fetched"])
 def test_raw_racecard_source_evidence_propagates_without_market_claim(self):
    raw=source("<table><tr><td>saved unverified original</td></tr></table>")
    (self.root/"official_racecard.html").write_bytes(raw)
    path=self.root/"receipt.json"
    r=json.loads(path.read_text(encoding="utf8"))
    r.update({"state":"NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",
              "racecard_original_fetched":True,"http_requests_started":3,
              "racecard_number":1,"observed_racecard_url":RACE,
              "racecard_sha256":hashlib.sha256(raw).hexdigest(),
              "racecard_bytes":len(raw),
              "racecard_captured_at_utc":"2026-11-15T02:00:03+00:00"})
    path.write_text(json.dumps(r),encoding="utf8")
    result=derive_nov15_race_links(self.root)
    self.assertTrue(result["racecard_originals_fetched"])
    self.assertEqual(result["saved_racecard_original"]["sha256"],hashlib.sha256(raw).hexdigest())
    self.assertEqual(result["saved_racecard_original"]["race_number"],1)
    self.assertEqual(result["saved_racecard_original"]["existing_parser_diagnostic"]["parser"],
                     "diagnostics.jra_multi_capture_20261106.parse")
    self.assertFalse(result["saved_racecard_original"]["existing_parser_diagnostic"]["structure_diagnostic_pass"])
    self.assertFalse(result["roster_verified"])
    self.assertTrue(result["hybrid_experiment"]["PC"]["racecard_original_fetched"])
    self.assertFalse(result["hybrid_experiment"]["dual_racecard_parity_verified"])
    self.assertFalse(result["hybrid_experiment"]["full_hybrid_experiment_pass"])
    self.assertFalse(result["quinella_market_verified"])
    self.assertFalse(result["bracket_market_verified"])
    self.assertEqual(result["saved_racecard_original"]["odds_navigation_handoff"]["state"],
                     "OFFICIAL_ODDS_ACTION_MISSING_OR_AMBIGUOUS")
 def test_official_odds_handoff_reuses_existing_action_parser(self):
    action='<a onclick="return doAction(\'/JRADB/accessO.html\', \'pw15observed/AB\')">オッズ</a>'
    raw=source("2026年11月15日 京都 1R "+action)
    (self.root/"official_racecard.html").write_bytes(raw)
    p=self.root/"receipt.json"
    receipt=json.loads(p.read_text(encoding="utf8"))
    receipt.update({"state":"NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",
        "racecard_original_fetched":True,"http_requests_started":3,
        "racecard_number":1,"observed_racecard_url":RACE,
        "racecard_sha256":hashlib.sha256(raw).hexdigest(),
        "racecard_bytes":len(raw),
        "racecard_captured_at_utc":"2026-11-15T02:00:03+00:00"})
    p.write_text(json.dumps(receipt),encoding="utf8")
    result=derive_nov15_race_links(self.root)
    handoff=result["saved_racecard_original"]["odds_navigation_handoff"]
    self.assertEqual(handoff["state"],"ODDS_ACTION_OBSERVED_IN_SAVED_PC_RACECARD")
    self.assertEqual(handoff["action_cname"],"pw15observed/AB")
    self.assertEqual(handoff["official_menu_url"],
                     "https://jra.jp/JRADB/accessO.html")
    self.assertEqual(handoff["source_racecard_sha256"],hashlib.sha256(raw).hexdigest())
    self.assertFalse(handoff["odds_original_fetched"])
    self.assertEqual(handoff["network_requests"],0)
 def test_existing_real_capture_parser_reused_for_date_locked_structure(self):
    # Synthetic HTML only checks adapter integration; not 2026-11-15 proof.
    race_raw=source(
        "2026年11月15日 京都 1R"
        "<table><tr><th class='horse'>馬名</th><th class='num'>馬番</th>"
        "<th class='waku'>枠</th></tr>"
        "<tr><td class='horse'><a href='/JRADB/accessU.html?CNAME=test'>馬A</a></td>"
        "<td class='num'>1</td><td class='waku'><img alt='枠1'/></td></tr></table>")
    (self.root/"official_racecard.html").write_bytes(race_raw)
    path=self.root/"receipt.json"
    r=json.loads(path.read_text(encoding="utf8"))
    r.update({"state":"NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",
              "racecard_original_fetched":True,"http_requests_started":3,
              "racecard_number":1,"observed_racecard_url":RACE,
              "racecard_sha256":hashlib.sha256(race_raw).hexdigest(),
              "racecard_bytes":len(race_raw),
              "racecard_captured_at_utc":"2026-11-15T02:00:03+00:00"})
    path.write_text(json.dumps(r),encoding="utf8")
    d=derive_nov15_race_links(self.root)
    diagnosis=d["saved_racecard_original"]["existing_parser_diagnostic"]
    self.assertTrue(diagnosis["structure_diagnostic_pass"])
    self.assertEqual(diagnosis["parsed_runner_rows"],1)
    self.assertFalse(diagnosis["official_roster_authenticated"])
    self.assertFalse(d["quinella_market_verified"])
    self.assertFalse(d["bracket_market_verified"])
 def test_forged_saved_racecard_url_rejected_even_with_matching_sha(self):
    raw=source("<html>source</html>")
    (self.root/"official_racecard.html").write_bytes(raw)
    path=self.root/"receipt.json"
    r=json.loads(path.read_text(encoding="utf8"))
    r.update({"state":"NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",
              "racecard_original_fetched":True,"http_requests_started":3,
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
