"""Offline structure proof: locate SP actual horse identity in two SHA-sealed profiles."""
import argparse,json,hashlib
from pathlib import Path
from bs4 import BeautifulSoup
FILES=[("モンドプリューム","sp_11r_horse01.html","sp_profile_receipt.json"),
       ("エティエンヌ","sp_11r_horse02.html","sp_profile_second_receipt.json")]
ROOT=Path("docs/diagnostics/jra_p1_fb_offline_20261106")
def inspect(first,second):
    results=[]
    for (name,filename,receipt),root in zip(FILES,(first,second)):
        r=json.loads((ROOT/receipt).read_text(encoding="utf8"))
        paths=list(Path(root).rglob(filename))
        if len(paths)!=1:raise ValueError("missing_sp_original")
        raw=paths[0].read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r["source_sha256"]:raise ValueError("SHA_mismatch")
        soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
        matches=[]
        for x in soup.find_all(string=lambda s: s and name in s):
            node=x.parent
            context=[]
            for depth in range(3):
                if node is None:break
                context.append({"tag":node.name,"class":node.get("class",[]),
                                "id":node.get("id"),"text":node.get_text(" ",strip=True)[:90]})
                node=node.parent
            matches.append({"raw":str(x).strip()[:90],"ancestors":context})
        results.append({"name":name,"source_sha256":r["source_sha256"],
                        "matching_text_nodes":len(matches),"first_matches":matches[:9]})
    return {"schema":"p1_fb_sp_profile_identity_dom_audit.v1","sources":results,"new_http":0}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--first",required=True);p.add_argument("--second",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    d=inspect(a.first,a.second);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"sources":len(d["sources"]),"http":0}))
