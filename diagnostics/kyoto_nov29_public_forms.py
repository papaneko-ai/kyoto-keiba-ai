"""Observed official PC public navigation; exact form tokens, never guessed."""
import re
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from urllib.request import Request

PC_HOME="https://www.jra.go.jp/"
PC_ENTRY=PC_HOME+"JRADB/accessD.html"
LIMIT=1_500_000

def observed_action(raw,day,stage):
    if not isinstance(raw,bytes) or not 0<len(raw)<=LIMIT or not re.fullmatch(r"20\d{6}",day):
        raise ValueError("invalid_public_form_original")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    forms=soup.select('form#commForm01')
    if soup.find("base") or len(forms)!=1 or str(forms[0].get("method","")).lower()!="post" or str(forms[0].get("action","")).strip() or len(forms[0].select('input[name="cname"]'))!=1:
        raise ValueError("official_public_form_not_unique")
    if stage not in ("entry","meeting"):
        raise ValueError("invalid_public_form_stage")
    found=set()
    for anchor in soup.select("a[onclick]"):
        match=re.fullmatch(r"\s*(?:return\s+)?doAction\(\s*['\"](/JRADB/accessD\.html)['\"]\s*,\s*['\"](pw[A-Za-z0-9]+/[A-Za-z0-9]+)['\"]\s*\)\s*;?\s*(?:return\s+false\s*;?)?\s*",anchor["onclick"])
        if not match:continue
        token=match.group(2)
        label=" ".join(anchor.get_text(" ",strip=True).split())
        if stage=="entry" and label=="出馬表" and re.fullmatch(r"pw01dli00/[A-Za-z0-9]{2}",token):
            found.add((token,label))
        if stage=="meeting" and "京都" in label and re.fullmatch(r"pw01drl0008[0-9]{8}"+re.escape(day)+r"/[A-Za-z0-9]{2}",token):
            found.add((token,label))
    if len(found)!=1:raise ValueError("official_public_action_not_unique")
    return next(iter(found))

def post_form(opener,token,referer):
    if referer not in (PC_HOME,PC_ENTRY) or not re.fullmatch(r"pw01(?:dli00|drl0008[0-9]{16})/[A-Za-z0-9]{2}",token):
        raise ValueError("invalid_public_form_target")
    request=Request(PC_ENTRY,data=urlencode({"cname":token}).encode("ascii"),method="POST",
        headers={"Accept":"text/html","Content-Type":"application/x-www-form-urlencoded",
                 "Referer":referer,"User-Agent":"KyotoRaceAI-Private-ReadOnly/0.1"})
    with opener.open(request,timeout=12) as reply:
        raw=reply.read(LIMIT+1)
        if reply.status!=200 or reply.geturl()!=PC_ENTRY or "html" not in reply.headers.get("Content-Type","").lower() or not 0<len(raw)<=LIMIT:
            raise ValueError("unverified_public_form_response")
    return raw
