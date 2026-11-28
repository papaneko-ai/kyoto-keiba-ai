"""Regression tests for PC/SP market-by-market recovery (no HTTP)."""
import json
import tempfile
import unittest
from pathlib import Path
from hashlib import sha256
from datetime import date
from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec, DEFAULT_RACE_SPEC
from diagnostics.jra_market_integrity_gate import normal_sales_open
from diagnostics.kyoto_g06_item_level_recovery import recover_saved_markets
from tests.test_jra_market_source_chain import html, MENU, Q, B, RUNNERS, TOKEN1, TOKEN2

RACE="2026-11-07_KYOTO_11R"
SPEC=ObservedRaceSpec("20261107",11,RACE,"京都",
    "https://jra.jp/JRADB/accessD.html?CNAME=observed",
    "https://sp.jra.jp/JRADB/accessD.html?CNAME=observed",
    normal_sales_open(date(2026,11,7)).isoformat())
TIME="2026-11-07T00:00:00Z"
START="2026-11-07T06:45:00Z"

def setup(folder, channel, markets, *, tamper=False, late=False, final=False):
    d=Path(folder)/channel.lower()
    d.mkdir(parents=True)
    prefix="sw" if channel=="SP" else "pw"
    t1=prefix+TOKEN1[2:]
    t2=prefix+TOKEN2[2:]
    menu=MENU.replace(TOKEN1,t1).replace(TOKEN2,t2)
    def page(title,body):
        return html(title,body,final=final)
    steps=[]
    def add(step,name,raw,token=None):
        (d/name).write_bytes(raw)
        steps.append({"step":step,"bytes":len(raw),"sha256":sha256(raw).hexdigest(),
            "captured_at_utc":"2026-11-07T07:00:00Z" if late and step in markets else TIME,
            "requested_url":"https://"+("sp.jra.jp" if channel=="SP" else "jra.jp")+"/JRADB/"+("accessD.html" if step=="racecard" else "accessO.html"),
            "observed_action_token":token,"method":"POST" if token else "GET"})
    add("racecard","official_racecard.html",page("出馬表","出走馬"))
    add("odds_menu","official_odds_menu.html",page("オッズ",menu))
    for market in markets:
        add(market,market+"_original.html",
            page("馬連オッズ" if market=="quinella" else "枠連オッズ",Q if market=="quinella" else B),
            t1 if market=="quinella" else t2)
    if tamper:
        (d/(markets[0]+"_original.html")).write_bytes(b"tampered")
    (d/"receipt.json").write_text(json.dumps({"race_id":RACE,"channel":channel,
        "state":"CAPTURE_BLOCKED","request_receipts":steps}),encoding="utf-8")

class Tests(unittest.TestCase):
    def test_pc_quinella_sp_bracket(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d,"PC",["quinella"])
            setup(d,"SP",["bracket_quinella"])
            x=recover_saved_markets(d,race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START)
            self.assertTrue(x["both_markets_verified"])
            self.assertTrue(x["mixed_channel"])
            self.assertFalse(x["simultaneous_snapshot_asserted"])
            self.assertEqual(x["markets"]["quinella"]["selected"]["channel"],"PC")
            self.assertEqual(x["markets"]["bracket_quinella"]["selected"]["channel"],"SP")
    def test_reverse_direction(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d,"SP",["quinella"])
            setup(d,"PC",["bracket_quinella"])
            x=recover_saved_markets(d,race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START)
            self.assertTrue(x["both_markets_verified"])
    def test_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d,"PC",["quinella"],tamper=True)
            setup(d,"SP",["bracket_quinella"])
            x=recover_saved_markets(d,race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START)
            self.assertFalse(x["both_markets_verified"])
    def test_late_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d,"PC",["quinella"],late=True)
            setup(d,"SP",["bracket_quinella"])
            x=recover_saved_markets(d,race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START)
            self.assertFalse(x["both_markets_verified"])
    def test_final_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d,"PC",["quinella"],final=True)
            setup(d,"SP",["bracket_quinella"])
            x=recover_saved_markets(d,race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START)
            self.assertFalse(x["both_markets_verified"])

class CanonicalWeekendRecovery(unittest.TestCase):
    def test_saved_market_origin_matches_both_days(self):
        from dataclasses import replace
        for day in ("20261128","20261129"):
            iso="2026-11-"+day[-2:]
            with self.subTest(day=day), tempfile.TemporaryDirectory() as tmp:
                setup(tmp,"PC",["quinella","bracket_quinella"])
                p=Path(tmp)/"pc"
                rec=json.loads((p/"receipt.json").read_text())
                rec["race_id"]=iso+"_KYOTO_11R"
                for step in rec["request_receipts"]:
                    name={"racecard":"official_racecard.html","odds_menu":"official_odds_menu.html"}.get(step["step"],step["step"]+"_original.html")
                    raw=(p/name).read_bytes().replace(b"20261107",day.encode()).replace("11月7日".encode("cp932"),("11月"+day[-2:]+"日").encode("cp932"))
                    (p/name).write_bytes(raw)
                    step.update(bytes=len(raw),sha256=sha256(raw).hexdigest(),captured_at_utc=iso+"T00:00:00Z",requested_url=step["requested_url"].replace("https://jra.jp/","https://www.jra.go.jp/"))
                    if step["observed_action_token"]:
                        step["observed_action_token"]=step["observed_action_token"].replace("20261107",day)
                (p/"receipt.json").write_text(json.dumps(rec))
                spec=replace(SPEC,race_day=day,race_id=rec["race_id"],pc_racecard_url=SPEC.pc_racecard_url.replace("https://jra.jp/","https://www.jra.go.jp/"))
                def assess():
                    return recover_saved_markets(tmp,race_spec=spec,active_runners=RUNNERS,verified_start_utc=iso+"T06:45:00Z")
                self.assertTrue(assess()["both_markets_verified"])
                rec["request_receipts"][-1]["requested_url"]="https://example.org/JRADB/accessO.html"
                (p/"receipt.json").write_text(json.dumps(rec))
                self.assertFalse(assess()["both_markets_verified"])

class SundaySPOrigin(unittest.TestCase):
    def test_saved_actual_origin_and_related_recovery_paths(self):
        from dataclasses import replace
        from unittest.mock import patch
        from diagnostics.kyoto_g06_market_link_evidence import observed_market_links
        from diagnostics.kyoto_g06_missing_market_retry import recover_one
        day="20261129";iso="2026-11-29";stamp=iso+"T02:00:00Z";start=iso+"T06:45:00Z"
        for host in ("sp.jra.jp","app.jra.jp"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as tmp:
                setup(tmp,"SP",["quinella"])
                p=Path(tmp)/"sp";rp=p/"receipt.json";rec=json.loads(rp.read_text())
                rec["race_id"]=iso+"_KYOTO_11R"
                url=f"https://{host}/JRADB/accessD.html?CNAME=sw01dde01082026050611{day}%2FAA"
                post=f"https://{host}/JRADB/accessO.html";token="swMenu/A0"
                for step in rec["request_receipts"]:
                    k=step["step"];name={"racecard":"official_racecard.html","odds_menu":"official_odds_menu.html"}.get(k,k+"_original.html")
                    raw=(p/name).read_bytes().replace(b"20261107",day.encode()).replace("11月7日".encode("cp932"),"11月29日".encode("cp932"))
                    if k=="racecard":
                        raw=raw.replace(b"</body>",'<a onclick="return doAction(\'/JRADB/accessO.html\',\'swMenu/A0\')">オッズ</a></body>'.encode("cp932"))
                    (p/name).write_bytes(raw)
                    step.update(bytes=len(raw),sha256=sha256(raw).hexdigest(),captured_at_utc=stamp,requested_url=url if k=="racecard" else post,response_url=url if k=="racecard" else post,method="GET" if k=="racecard" else "POST")
                    if k=="odds_menu":step["observed_action_token"]=token
                    elif k!="racecard":step["observed_action_token"]=step["observed_action_token"].replace("20261107",day)
                def emit():rp.write_text(json.dumps(rec))
                emit()
                spec=replace(SPEC,race_day=day,race_id=rec["race_id"],sp_racecard_url="")
                def assess():return recover_saved_markets(tmp,race_spec=spec,active_runners=RUNNERS,verified_start_utc=start)
                self.assertEqual(assess()["markets"]["quinella"]["selected"]["source_url"],post)
                self.assertTrue(observed_market_links(tmp,race_spec=spec,verified_start_utc=start)["SP"]["observed"])
                raw=html("枠連オッズ",B).replace(b"20261107",day.encode()).replace("11月7日".encode("cp932"),"11月29日".encode("cp932"))
                def mock(client,channel,uri,**kw):
                    self.assertEqual(uri,post)
                    return {"raw":raw,"sha256":sha256(raw).hexdigest(),"bytes":len(raw),"captured_at_utc":stamp,"requested_url":uri,"response_url":uri,"observed_action_token":kw["cname"],"method":"POST"}
                with patch("diagnostics.kyoto_g06_missing_market_retry.http_fetch",side_effect=mock) as fetch:
                    recover_one(root=tmp,channel="SP",market="bracket_quinella",race_spec=spec,active_runners=RUNNERS,verified_start_utc=start,now_utc=stamp,opener=object())
                    self.assertEqual(fetch.call_count,1)
                self.assertTrue(assess()["both_markets_verified"])
                import shutil
                shutil.rmtree(Path(tmp)/"sp_recovery")
                for field,bad in (("requested_url","https://jra.jp/JRADB/accessO.html"),("response_url","https://example.org/JRADB/accessO.html"),("observed_action_token","swWrong/A0"),("captured_at_utc","2026-11-28T02:00:00Z")):
                    st=rec["request_receipts"][1];old=st[field];st[field]=bad;emit()
                    self.assertIsNone(assess()["markets"]["quinella"]["selected"])
                    self.assertFalse(observed_market_links(tmp,race_spec=spec,verified_start_utc=start)["SP"]["observed"])
                    with patch("diagnostics.kyoto_g06_missing_market_retry.http_fetch") as fetch:
                        with self.assertRaises(ValueError):
                            recover_one(root=tmp,channel="SP",market="bracket_quinella",race_spec=spec,active_runners=RUNNERS,verified_start_utc=start,now_utc=stamp,opener=object())
                        fetch.assert_not_called()
                    st[field]=old;emit()

class BatchIntegration(unittest.TestCase):
    def test_batch_keeps_both_saved_markets(self):
        from diagnostics.kyoto_g06_all12_capture import run_twelve
        def runner(out,**kwargs):
            setup(out,"PC",["quinella"])
            setup(out,"SP",["bracket_quinella"])
            return {"state":"SAFE_STOP","selected_channel":None}
        item={"race_spec":DEFAULT_RACE_SPEC,"verified_start_utc":START,
              "active_runners":RUNNERS,
              "expected_named_runners":tuple((n,f,"馬"+str(n)) for n,f in RUNNERS),
              "primary_channel":"PC"}
        with tempfile.TemporaryDirectory() as d:
            records={i:None for i in range(1,13)}
            records[11]=item
            report=run_twelve(Path(d)/"output",records=records,runner=runner)
            self.assertEqual(report["verified_dual_market_races"],1)
            self.assertEqual(report["unobserved_link_races"],11)
            self.assertFalse(report["g06_certified"])
            self.assertTrue(report["records"][10]["item_level_recovery"]["mixed_channel"])
            self.assertTrue(report["records"][10]["cross_source_times_not_equated"])
if __name__=="__main__":
    unittest.main()
