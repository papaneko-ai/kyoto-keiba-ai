"""Read the exact authenticated 19:02 incident originals, with no JRA HTTP."""
import hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.kyoto_impl30_postrace_day import observed_actions,MENU
REPO="papaneko-ai/kyoto-keiba-ai";DAY="20261128";RUN=46133297877;ART=15258294810
def api(path):
    return json.loads(subprocess.check_output(["gh","api",path],timeout=20))
def main():
    assert os.environ["GITHUB_REPOSITORY"]==REPO and os.environ["KYOTO_TARGET_DAY"]==DAY
    run=api(f"repos/{REPO}/actions/runs/{RUN}")
    assert run["id"]==RUN and run["head_branch"]=="main" and run["event"]=="workflow_dispatch" and run["status"]=="completed"
    assert run["path"].split("@",1)[0]==".github/workflows/kyoto-20261128-29-postrace-evidence.yml" and run["created_at"].startswith("2026-11-28T10:02:58")
    art=api(f"repos/{REPO}/actions/artifacts/{ART}")
    assert art["id"]==ART and art["name"]==f"kyoto-postrace-{RUN}-{DAY}" and not art["expired"] and art["workflow_run"]["id"]==RUN
    assert art["digest"]=="sha256:39fa95e92954de5c26b83f6582b0bdeb85d9f31f41b5a534a06ed146a408c807"
    with tempfile.TemporaryDirectory(prefix="postrace_probe_") as tmp:
        root=Path(tmp);cipher=root/"cipher";cipher.mkdir();raw=root/"raw"
        subprocess.run(["gh","run","download",str(RUN),"--repo",REPO,"--name",art["name"],"--dir",str(cipher)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
        decrypt_evidence(cipher,raw,key_hex=os.environ["ARCHIVE_KEY"],repo=REPO,run_id=str(RUN))
        receipt=json.loads((raw/"receipt.json").read_bytes())
        assert receipt["day"]==DAY and receipt["schema"]=="kyoto_impl30_postrace_day.v1"
        by={x["file"]:x for x in receipt["requests"]}
        result={"run":RUN,"artifact":ART,"archive_authenticated":True,"new_source_http_requests":0,"receipt_sha256":hashlib.sha256((raw/"receipt.json").read_bytes()).hexdigest(),"race_reasons":{},"files":{}}
        for n,x in receipt["races"].items():
            reason=x.get("reason","")
            result["race_reasons"][n]=reason if re.fullmatch(r"[A-Za-z]+:[a-z_]+",reason) else hashlib.sha256(reason.encode()).hexdigest()
        for name,kind in (("results_menu.html","results"),("results_meeting.html","results"),("payout_menu.html","payout")):
            meta=by[name];data=(raw/name).read_bytes()
            assert hashlib.sha256(data).hexdigest()==meta["sha256"] and len(data)==meta["bytes"]
            origin="https://"+urlsplit(meta["source_url"]).netloc
            path,_=MENU[kind]
            rows=[]
            for label,t,method,url in observed_actions(data,path,origin=origin):
                if "京都" in label or DAY in t or re.search(r"(?<!\d)0?[1-9]\d?\s*(?:R|レース)",label):
                    rows.append({"label":label if re.fullmatch(r"[\d回京都日曜土日月年レースR :：\t\s()（）]+",label) else ("KYOTO" if "京都" in label else "OTHER"),"token_body":t.split("/")[0],"token_sha256":hashlib.sha256(t.encode()).hexdigest(),"method":method,"host":urlsplit(url).netloc})
            soup=BeautifulSoup(data,"html.parser")
            shapes=[]
            for node in soup.select("a,form,button,input"):
                v=" ".join(str(node.get(k,"")) for k in ("onclick","href","action","value"))
                if path not in v and DAY not in v:continue
                for token in re.findall(r"pw[A-Za-z0-9]+(?:/|%2[Ff])[A-Za-z0-9]+",v):
                    b=re.split(r"/|%2[Ff]",token)[0]
                    if DAY in b:shapes.append({"tag":node.name,"body":b,"has_kyoto":"京都" in node.get_text(" ",strip=True)})
            result["files"][name]={"sha256":meta["sha256"],"origin":origin,"actions":rows[:80],"other_token_shapes":shapes[:100],"count":len(rows)}
        from diagnostics.kyoto_impl30_postrace_replay import saved_navigation_recovery
        recovery=saved_navigation_recovery(raw,DAY)
        assert len(recovery["recovery_candidates"])==13
        assert {x["race"] for x in recovery["recovery_candidates"] if x["stage"]=="result_race"}==set(range(1,13))
        assert sum(x["stage"]=="payout_meeting" for x in recovery["recovery_candidates"])==1
        assert all(x["legacy_candidate_count"]==0 and x["candidate_count"]==1 and x["independent_field_agreement"] is True for x in recovery["recovery_candidates"])
        result["candidate_source"]="5a16e23d0f2148581dbe0b965d4672b22735602e"
        result["recovery"]=recovery
        print("POSTRACE_REPAIR_REPLAY="+json.dumps(result,ensure_ascii=True,sort_keys=True,separators=(",",":")))
if __name__=="__main__":main()
