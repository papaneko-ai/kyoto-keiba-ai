import json,shutil,tempfile,os,sys
from pathlib import Path
from unittest.mock import patch
# Execute from exact trusted reader checkout with candidate closure loaded by path.
from diagnostics.kyoto_weekend_postflight import check_originals
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence
from diagnostics.kyoto_impl39_sp_market_union import standalone_roster
from diagnostics.kyoto_impl31_sp_saved_roster_audit import inspect_heading,utc
import hashlib,importlib.util
DAY="20261129";STAMP="2026-11-29T01:00:00Z";KEY="61"*32;REPO="papaneko-ai/kyoto-keiba-ai"
# Load candidate module as top-level script, matching production execution.
sys.path.insert(0,str(Path(sys.argv[1]).resolve().parent))
spec=importlib.util.spec_from_file_location("kyoto_closure_candidate",sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture(root):
    root.mkdir()
    url="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde01082026050601"+DAY+"%2FAA"
    nav=f'<a href="{url}">京都 1R</a>'.encode("cp932")
    raw=('<html><h2>2026年11月29日 京都 1R 出馬表 2頭 発走時刻：11時45分</h2><table><tr><td class="wban">1</td><td class="uban">1</td><td><a href="/JRADB/accessU.html">馬A</a></td></tr><tr><td class="wban">2</td><td class="uban">2</td><td><a href="/JRADB/accessU.html">馬B</a></td></tr></table></html>').encode("cp932")
    sha=lambda b:hashlib.sha256(b).hexdigest()
    (root/"official_sp_discovery_1.html").write_bytes(nav)
    (root/"sp_discovery_receipt.json").write_text(json.dumps({"day":DAY,"not_pc_derived":True,"attempts":[{"file":"official_sp_discovery_1.html","url":"https://sp.jra.jp/","sha256":sha(nav),"captured_at_utc":STAMP}]}))
    (root/"r01_official_sp_racecard.html").write_bytes(raw)
    (root/"r01_sp_receipt.json").write_text(json.dumps({"day":DAY,"channel":"SP","race_number":1,"local_target_race_key":f"KYOTO:{DAY}:01","observed_sp_source_url":url,"racecard_fetched":True,"racecard_sha256":sha(raw),"racecard_captured_at_utc":STAMP}))
    (root/"receipt.json").write_text(json.dumps({"day":DAY,"channel":"SP"}))
    (root/"source_verification.json").write_text(json.dumps(check_originals(root,day=DAY,channel="SP")))
    return standalone_roster(raw,DAY,1,utc(STAMP),sha(raw))
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);raw=root/"raw";cipher=root/"cipher";p=fixture(raw)
    encrypt_evidence(raw,cipher,key_hex=KEY,repo=REPO,run_id="42")
    def fake_download(cmd,**kw):
        assert cmd[:3]==["gh","run","download"] and cmd[3]=="42"
        dst=Path(cmd[cmd.index("--dir")+1])
        for x in cipher.iterdir():shutil.copyfile(x,dst/x.name)
    card={"state":"SOURCE_VERIFIED","run_id":"42",**p["racecard"]}
    coverage={"races":{str(n):{"state":"NO_VERIFIED_ROSTER"} for n in range(1,13)}}
    coverage["races"]["1"]={**p,"state":"ROSTER_VERIFIED","roster_source_channel":"SP","racecard":card}
    slots=[{"day":DAY,"run_id":"42","races":{"1":p}}]
    with patch.object(m.subprocess,"run",side_effect=fake_download):
        r,st,v=m.bridge_sp_named_rosters(DAY,coverage,slots,{1:None},{},KEY)
        assert r[1]==((1,1,"馬A"),(2,2,"馬B")) and st[1]==p["start_utc"]
        assert v["verified_races"]==[1] and "馬A" not in str(v)
        r,st,v=m.bridge_sp_named_rosters(DAY,coverage,slots,{},{},"62"*32)
        assert not r and not v["verified_races"]
    print("AUTHENTICATED_SP_NAMED_BRIDGE_PROOF=2/2; actual encrypted fixture, exact reader, zero source HTTP")
