"""G05 PC weekend evidence: actual source path, sealed originals and stale stop."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import capture,seal
from tests.test_kyoto_g03_weekend_bridge import Bridge,DAY
from tests.test_kyoto_g03_all_races import source_race
from tests.test_kyoto_g05_conditions import source
from tests.test_kyoto_g05_official_track import html
from diagnostics.kyoto_g05_official_track import KYOTO_TRACK_PAGE

class WeekendG05(Bridge):
    def test_g05_same_session_track_and_bodyweight_originals_sealed(self):
        urls=[]
        def mocked_get(opener,url):
            urls.append(url)
            if url==KYOTO_TRACK_PAGE:return html()
            return source(source_race(url))
        with patch("diagnostics.kyoto_nov15_two_original_observer.observe",self.observer),\
             patch("diagnostics.kyoto_g03_weekend_bridge._read",side_effect=mocked_get),\
             patch("diagnostics.kyoto_nov15_two_original_observer._read",side_effect=mocked_get),\
             patch("diagnostics.jra_one_shot_market_capture.RequestPacer"):
            result=capture(DAY,"PC",str(self.root/"g05_raw"),live=False,opener=object())
        self.assertTrue(result["g03_all_race_originals_observed"])
        self.assertTrue(result["g05_source_contract_saved"])
        self.assertTrue(result["g05_kyoto_track_source_saved"])
        self.assertEqual(urls.count(KYOTO_TRACK_PAGE),1)
        self.assertEqual(len(urls),12)
        self.assertEqual(json.loads((self.root/"g05_raw"/"g05_receipt.json").read_text())
                         ["races"]["1"]["track"]["weather"]["value"],"晴")
        self.assertTrue((self.root/"g05_raw"/"g05_official_kyoto_track.html").is_file())
        with patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY",DAY):
            seal(DAY,str(self.root/"g05_raw"),str(self.root/"g05_encrypted"),
                 key="ab"*32,repo="papaneko-ai/kyoto-keiba-ai",run_id="111")
        self.assertFalse((self.root/"g05_raw").exists())
        self.assertTrue((self.root/"g05_encrypted"/"originals.tar.gz.aesgcm").is_file())

    def test_stale_current_page_is_saved_but_cannot_promote_weather(self):
        urls=[]
        def mocked_get(opener,url):
            urls.append(url)
            if url==KYOTO_TRACK_PAGE:return html("20261115")
            return source(source_race(url))
        with patch("diagnostics.kyoto_nov15_two_original_observer.observe",self.observer),\
             patch("diagnostics.kyoto_g03_weekend_bridge._read",side_effect=mocked_get),\
             patch("diagnostics.kyoto_nov15_two_original_observer._read",side_effect=mocked_get),\
             patch("diagnostics.jra_one_shot_market_capture.RequestPacer"):
            result=capture(DAY,"PC",str(self.root/"g05_stale_raw"),live=False,opener=object())
        self.assertTrue(result["g05_kyoto_track_source_saved"])
        self.assertFalse(result["g05_same_day_track_heading_verified"])
        receipt=json.loads((self.root/"g05_stale_raw"/"g05_track_receipt.json").read_text())
        self.assertEqual(receipt["state"],"MISSING_OR_STALE_KYOTO_MEETING_HEADING")
        self.assertIsNone(receipt["weather"])
        self.assertTrue((self.root/"g05_stale_raw"/"g05_official_kyoto_track.html").is_file())

if __name__=="__main__":unittest.main()
