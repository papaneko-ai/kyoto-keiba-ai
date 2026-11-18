"""Single-request historical auxiliary-source feasibility proof; no predictions."""
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlsplit
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
import json,re
from bs4 import BeautifulSoup
from diagnostics.jra_pc_sp_benchmark import frozen

# Exact observed public page, not an invented race-id template.
URL="https://race.netkeiba.com/race/oikiri.html?race_id=202608050102&rf=shutuba_submenu&type=2"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def run():
    out=Path("h04_single_source_evidence");out.mkdir(exist_ok=False)
    u=urlsplit(URL)
    assert u.scheme=="https" and u.hostname=="race.netkeiba.com" and u.path=="/race/oikiri.html"
    receipt={"schema":"kyoto_h04_single_public_auxiliary_probe.v1",
       "url":URL,"historical_day":"2026-11-07","target":"京都2R",
       "independent_primary_jra_roster":True,
       "permission_for_bulk_automation_verified":False,
       "free_unauthed_page_observed":False,
       "pre_race_capture_proven":False,
       "prediction_ready":False,"h04_certified":False,"requests_started":1}
    try:
        req=Request(URL,headers={"User-Agent":"Mozilla/5.0 (compatible; KyotoResearchEvidence/1.0)",
                                 "Accept":"text/html"},method="GET")
        with build_opener(NoRedirect()).open(req,timeout=18) as response:
            raw=response.read(1_500_001)
            final_url=response.geturl()
            receipt["http_status"]=response.status
            typ=response.headers.get("Content-Type","")
            if response.status!=200 or final_url!=URL or not 0<len(raw)<=1_500_000 or "html" not in typ:
                raise ValueError("unexpected_redirect_size_or_content_type")
        (out/"observed_auxiliary_page.html").write_bytes(raw)
        receipt.update(source_sha256=sha256(raw).hexdigest(),source_bytes=len(raw),
            captured_at_utc=datetime.now(timezone.utc).isoformat())
        soup=BeautifulSoup(raw,"html.parser")
        text=soup.get_text(" ",strip=True)
        reference=frozen(2)["runners"]
        names=[r["horse_name"] for r in reference]
        recognized=[name for name in names if name in text]
        receipt.update(source_headline=soup.title.get_text(" ",strip=True) if soup.title else "",
                       official_jra_horse_names_in_page=len(recognized),
                       official_roster_horses=len(names),
                       training_date_20261104_observed="2026/11/04" in text,
                       source_page_has_training_label="調教タイム" in text,
                       time_sample_observed=bool(re.search(r"5[0-9]\.[0-9]\([0-9]{2}\.[0-9]\)",text)))
        receipt["free_unauthed_page_observed"]=len(recognized)>=3 and receipt["source_page_has_training_label"]
        receipt["state"]="HISTORICAL_AUXILIARY_ORIGINAL_OBSERVED" if receipt["free_unauthed_page_observed"] else "PAGE_PRESENT_CONTENT_UNVERIFIED"
    except Exception as exc:
        receipt.update(state="SOURCE_FETCH_OR_PARSE_FAILED",error_class=type(exc).__name__,
                       error_message=str(exc)[:180])
    (out/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,ensure_ascii=False))
    return 0 if receipt["free_unauthed_page_observed"] else 2
if __name__=="__main__":raise SystemExit(run())
