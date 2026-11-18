"""Twelve truly reparsed market pairs, not a forged 'SOURCE_FROZEN' flag."""
import json,tempfile,unittest
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.kyoto_g06_four_stage_inboxes import read_inboxes
from diagnostics.kyoto_g06_nested_bundle import bundle_g06,verify_bundle
from tests.test_kyoto_g06_all12_capture import spec
from tests.test_jra_market_source_chain import Q,B,RUNNERS

DAY="20261121"
TIME="2026-11-21T01:00:00Z"
START="2026-11-21T06:45:00Z"
def html(r,title,body):
    return (f"<html><title>{title} JRA</title><body>2026年11月21日 京都 {r}レース "
            +body+"</body></html>").encode("cp932")
def records():
    return {r:{"race_spec":spec(r),"verified_start_utc":START,
              "active_runners":RUNNERS,
              "expected_named_runners":tuple((n,f,f"Horse{n}") for n,f in RUNNERS),
              "primary_channel":"PC"} for r in range(1,13)}
def capture_mock(out,**kw):
    r=kw["race_spec"].race_number
    root=Path(out)/"pc";root.mkdir(parents=True)
    tok1=f"pw154ou100820260501{r:02d}{DAY}Z/AA"
    tok2=f"pw153ou100820260501{r:02d}{DAY}Z/BB"
    menu=html(r,"オッズ",(
       f'<a onclick="return doAction(\'/JRADB/accessO.html\',\'{tok1}\')">馬連</a>'
       f'<a onclick="return doAction(\'/JRADB/accessO.html\',\'{tok2}\')">枠連</a>'))
    paths=[("racecard","official_racecard.html",html(r,"出馬表","出走馬"),None),
           ("odds_menu","official_odds_menu.html",menu,None),
           ("quinella","quinella_original.html",html(r,"馬連オッズ",Q),tok1),
           ("bracket_quinella","bracket_quinella_original.html",html(r,"枠連オッズ",B),tok2)]
    steps=[]
    for step,name,raw,token in paths:
        (root/name).write_bytes(raw)
        steps.append({"step":step,"bytes":len(raw),"sha256":sha256(raw).hexdigest(),
                     "captured_at_utc":TIME,"method":"POST" if token else "GET",
                     "observed_action_token":token,"requested_url":
                     "https://jra.jp/JRADB/"+("accessD.html" if step=="racecard" else "accessO.html")})
    receipt={"race_id":kw["race_spec"].race_id,"channel":"PC",
             "state":"SOURCE_FROZEN","pre_race_prices_accepted":True,
             "request_receipts":steps,
             "market_receipt":{"classification":"VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED",
                "markets":{m:{"phase":"LIVE_PRE_RACE","pre_race_usable":True,
                        "source_sha256":next(x["sha256"] for x in steps if x["step"]==m)}
                         for m in ("quinella","bracket_quinella")}}}
    (root/"receipt.json").write_text(json.dumps(receipt))
    return {"state":"SOURCE_ONLY_PRIMARY","selected_channel":"PC",
            "attempts":[{"channel":"PC","state":"SOURCE_FROZEN","reason":None}]}
class All12SourceReparse(unittest.TestCase):
    def test_twelve_races_parse_and_publish_next_stage_with_encrypted_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"g06"
            with patch("diagnostics.kyoto_g06_all12_capture.capture_hybrid",side_effect=capture_mock):
                report=run_twelve(root,records=records(),authorized_live_http=True)
            self.assertEqual(report["verified_dual_market_races"],12)
            self.assertTrue(report["all_twelve_source_originals_verified"])
            self.assertTrue(report["downstream_intake_created"])
            self.assertEqual(report["downstream_source_ready_races"],12)
            downstream=read_inboxes(root)
            self.assertEqual(sum(len(r["payload"]["markets"])==2 for r in downstream["P4"]["races"]),12)
            self.assertEqual(sum(len(r["payload"]["markets"]["quinella"]["pairs"])==15
                            for r in downstream["P4"]["races"]),12)
            self.assertFalse(report["g06_certified"])
            self.assertFalse(downstream["P5"]["prediction_or_trade_authorized"])
            self.assertFalse(downstream["P6"]["prediction_or_trade_authorized"])
            archive=Path(td)/"g06_source_bundle.tar.gz"
            staged=bundle_g06(root,archive)
            self.assertFalse(root.exists())
            self.assertGreater(staged["source_file_count"],50)
            self.assertGreater(verify_bundle(archive)["verified_file_count"],50)
    def test_bad_one_market_preserves_other_eleven(self):
        def one_bad(out,**kw):
            r=capture_mock(out,**kw)
            if kw["race_spec"].race_number==6:
                (Path(out)/"pc"/"bracket_quinella_original.html").write_bytes(b"tampered")
            return r
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"g06"
            with patch("diagnostics.kyoto_g06_all12_capture.capture_hybrid",side_effect=one_bad):
                report=run_twelve(root,records=records(),authorized_live_http=True)
            self.assertEqual(report["verified_dual_market_races"],11)
            self.assertEqual(report["downstream_source_ready_races"],11)
            self.assertEqual(report["records"][5]["both_markets_verified"],False)
            self.assertEqual(len(read_inboxes(root)["G07"]["races"]),12)
if __name__=="__main__":unittest.main()
