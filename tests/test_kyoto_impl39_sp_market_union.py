import unittest,tempfile,json
from pathlib import Path
from hashlib import sha256
from diagnostics.kyoto_impl39_sp_market_union import assess,context
from diagnostics.kyoto_impl30_day_coverage import digest,proof,combine
from diagnostics.kyoto_weekend_postflight import check_originals
from diagnostics.kyoto_impl31_sp_saved_roster_audit import assess_checked
from tests.test_jra_market_source_chain import html,MENU,Q,B,RUNNERS,TOKEN1,TOKEN2
DAY="20261129";STAMP="2026-11-29T02:00:00Z";START="2026-11-29T06:45:00+00:00"
class SPUnion(unittest.TestCase):
    def test_authenticated_source_bridge_and_negative_cases(self):
        for host in ("sp.jra.jp","app.jra.jp"):
            with self.subTest(host=host),tempfile.TemporaryDirectory() as td:
                p=Path(td)
                names=tuple((n,f,"馬"+str(n)) for n,f in RUNNERS)
                row={"roster_digest":"a"*64,"named_roster_digest":digest(names),"start_utc":START,"racecard":proof("b"*64,STAMP),"horses":{str(n):{} for n,_ in RUNNERS},"track":{},"markets":{}}
                pc={"day":DAY,"run_id":"1","races":{"11":row}}
                bound=context([pc],DAY)
                url=f"https://{host}/JRADB/accessD.html?CNAME=sw01dde01082026050611{DAY}%2FAA"
                nav=f'<a href="{url}">京都 11R</a>'.encode("cp932")
                (p/"official_sp_discovery_1.html").write_bytes(nav)
                (p/"sp_discovery_receipt.json").write_text(json.dumps({"day":DAY,"not_pc_derived":True,"attempts":[{"file":"official_sp_discovery_1.html","url":f"https://{host}/","sha256":sha256(nav).hexdigest(),"captured_at_utc":STAMP}]}))
                rec={"day":DAY,"channel":"SP","race_number":11,"local_target_race_key":f"KYOTO:{DAY}:11","observed_sp_source_url":url,"racecard_fetched":True}
                def save(name,key,raw,token=None,stamp=STAMP):
                    (p/("r11_"+name)).write_bytes(raw)
                    rec.update({key+"_sha256":sha256(raw).hexdigest(),key+"_captured_at_utc":stamp})
                    if token:rec[key+"_action"]=token
                def emit(): (p/"r11_sp_receipt.json").write_text(json.dumps(rec))
                def current(title,body):return html(title,body).replace("11月7日".encode("cp932"),"11月29日".encode("cp932")).replace(b"20261107",DAY.encode())
                t1=TOKEN1.replace("pw","sw",1).replace("20261107",DAY);t2=TOKEN2.replace("pw","sw",1).replace("20261107",DAY)
                menu=MENU.replace(TOKEN1,t1).replace(TOKEN2,t2)
                card=('<html><h2>2026年11月29日 京都 11R 出馬表 6頭</h2><a onclick="return doAction(\'/JRADB/accessO.html\',\'swMenu/A0\')">オッズ</a><table>'+''.join(f'<tr><td class="wban">{f}</td><td class="uban">{n}</td><td><a href="/JRADB/accessU.html">{nm}</a></td></tr>' for n,f,nm in names)+'</table></html>').encode("cp932")
                save("official_sp_racecard.html","racecard",card)
                save("official_sp_odds_menu.html","sp_odds_menu",current("オッズ",menu),"swMenu/A0")
                save("official_sp_quinella_odds.html","sp_quinella",current("馬連オッズ",Q),t1)
                save("official_sp_bracket_quinella_odds.html","sp_bracket_quinella",current("枠連オッズ",B),t2)
                emit()
                def replay():
                    post=check_originals(p,day=DAY,channel="SP")
                    return assess(p,DAY,2,post,assess_checked(p,DAY,post),bound)
                result=replay()
                self.assertTrue(result["races"]["11"]["paired_same_slot"])
                c=combine(DAY,[pc],sp_slots=[result])
                self.assertEqual(c["totals"]["racecards"],1)
                self.assertEqual(c["totals"]["registered_horses_known"],6)
                self.assertEqual(c["totals"]["paired_same_slot_races"],1)
                self.assertEqual(c["authenticated_pc_slots"],1)
                self.assertEqual(c["races"]["11"]["markets"]["quinella"]["channel"],"SP")
                rec["sp_bracket_quinella_action"]="swBad/A0";emit()
                partial=replay();self.assertEqual(set(partial["races"]["11"]["markets"]),{"quinella"})
                self.assertEqual(combine(DAY,[pc],sp_slots=[partial])["totals"]["paired_same_slot_races"],0)
                rec["sp_quinella_captured_at_utc"]=START;emit()
                self.assertEqual(replay()["races"],{})
                self.assertEqual(combine(DAY,[],sp_slots=[result])["totals"]["racecards"],0)
if __name__=="__main__":unittest.main()
