"""Failure-driven structural repair for literal JRA navigation actions.

The candidate space comes from observed HTML, not guessed tokens. A second
HTML parser and a different action grammar must agree. No network, eval,
external actions, source mutation, or invented racing values.
"""
import hashlib,json,re
from html.parser import HTMLParser
from bs4 import BeautifulSoup

LIMIT=1_500_000
PATH="/JRADB/accessD.html"
class RepairRejected(ValueError):pass

def digest(raw):return hashlib.sha256(raw).hexdigest()
def canon(value):return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(",",":")).encode()
def norm(value):return " ".join(value.split())
def decode(raw):
    if type(raw) is not bytes or not 0<len(raw)<=LIMIT:raise RepairRejected("invalid_original")
    for enc in ("utf-8","cp932"):
        try:return raw.decode(enc),enc
        except UnicodeError:pass
    raise RepairRejected("unknown_encoding")

def identity(path,token,label,channel,day,stage):
    prefix={"PC":"pw","SP":"sw"}.get(channel)
    if not prefix or path!=PATH or not re.fullmatch(r"20[0-9]{6}",day):return False
    if stage=="entry":
        return label=="出馬表" and bool(re.fullmatch(prefix+r"01dli00/[A-Za-z0-9]{2}",token))
    if stage=="meeting":
        return "京都" in label and bool(re.fullmatch(prefix+r"01drl0008[0-9]{8}"+re.escape(day)+r"/[A-Za-z0-9]{2}",token))
    return False

def form_ok(attrs,controls):
    return (attrs.get("method","").lower()=="post" and attrs.get("action","").strip() in ("",PATH)
        and attrs.get("enctype","application/x-www-form-urlencoded").lower()=="application/x-www-form-urlencoded"
        and attrs.get("target","") in ("","_self") and len(controls)==1
        and controls[0][0]=="input" and controls[0][1].get("name")=="cname"
        and controls[0][1].get("type","text").lower() in ("hidden","text")
        and "form" not in controls[0][1] and "disabled" not in controls[0][1])

def carrier(attrs):
    if any(k in attrs for k in ("disabled","hidden","formaction","formmethod","formtarget","formenctype")):return None
    href=attrs.get("href","").strip()
    if attrs.get("onclick"):
        if href.lower().startswith("javascript:"):return None
        return "onclick",attrs["onclick"]
    if href.startswith("javascript:"):return "href",href
    return None

def lexical_call(text):
    if not isinstance(text,str) or len(text)>260:return None
    text=text.strip()
    if text.startswith("javascript:"):text=text[len("javascript:"):].strip()
    lex=re.compile(r"""\s*(?:(?P<id>[A-Za-z_$][A-Za-z0-9_$]*)|(?P<s>'[A-Za-z0-9/._-]+'|"[A-Za-z0-9/._-]+")|(?P<p>[(),;]))""")
    tokens=[];i=0
    while i<len(text):
        m=lex.match(text,i)
        if not m:return None
        tokens.append((m.lastgroup,m.group(m.lastgroup)));i=m.end()
    if tokens and tokens[0]==("id","return"):tokens.pop(0)
    if tokens and tokens[-1]==("p",";"):tokens.pop()
    if tokens[-2:]==[("id","return"),("id","false")]:
        tokens=tokens[:-2]
        if tokens and tokens[-1]==("p",";"):tokens.pop()
    if len(tokens)!=6 or tokens[0]!=("id","doAction") or tokens[1]!=("p","(") or tokens[2][0]!="s" or tokens[3]!=("p",",") or tokens[4][0]!="s" or tokens[5]!=("p",")"):return None
    return tokens[2][1][1:-1],tokens[4][1][1:-1]

_RX=re.compile(r"""\s*(?:javascript:\s*)?(?:return\s+)?doAction\s*\(\s*(['"])(/JRADB/accessD\.html)\1\s*,\s*(['"])([ps]w[A-Za-z0-9]+/[A-Za-z0-9]+)\3\s*\)\s*;?\s*(?:return\s+false\s*;?)?\s*""")
def regex_call(text):
    m=_RX.fullmatch(text) if isinstance(text,str) and len(text)<=260 else None
    return (m[2],m[4]) if m else None

class Scanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms=[];self.active=None;self.current=None;self.controls=[];self.bad=False
    def handle_starttag(self,tag,attrs):
        a={k:(v or "") for k,v in attrs}
        if len(a)!=len(attrs) or tag=="base" or "form" in a:self.bad=True
        if tag=="form":
            if self.active is not None:self.bad=True
            self.active=(a,[]);self.forms.append(self.active)
        elif self.active is not None and tag in ("input","select","textarea","button") and a.get("name") and "disabled" not in a:
            self.active[1].append((tag,a))
        if tag in ("a","button"):
            if self.current is not None:self.bad=True
            c=carrier(a)
            if c:self.current=[tag,c[0],c[1],[]]
    def handle_data(self,data):
        if self.current is not None and data.strip():self.current[3].append(data.strip())
    def handle_endtag(self,tag):
        if tag=="form":self.active=None
        if self.current is not None and tag==self.current[0]:
            t,k,a,parts=self.current;self.controls.append((t,k,a,norm(" ".join(parts))));self.current=None

def recover_action(raw,day,channel,stage):
    """Generate, independently check and apply one literal navigation candidate."""
    text,enc=decode(raw)
    soup=BeautifulSoup(text,"html.parser")
    if soup.find("base") or soup.select("[form]"):raise RepairRejected("untrusted_form_context")
    forms=[]
    for f in soup.find_all("form"):
        a={k:str(v) for k,v in f.attrs.items()}
        controls=[(x.name,{k:str(v) for k,v in x.attrs.items()}) for x in f.find_all(("input","select","textarea","button")) if x.get("name") and not x.has_attr("disabled")]
        if form_ok(a,controls):forms.append(a)
    if len(forms)!=1:raise RepairRejected("unique_post_form_not_proved")
    dom=[]
    for el in soup.find_all(("a","button")):
        c=carrier({k:str(v) for k,v in el.attrs.items()})
        if c:dom.append((el.name,c[0],c[1],norm(el.get_text(" ",strip=True))))
    scan=Scanner();scan.feed(text);scan.close()
    if scan.bad or scan.current is not None or scan.active is not None or sum(form_ok(a,c) for a,c in scan.forms)!=1:
        raise RepairRejected("independent_form_scan_disagrees")
    inventories=[]
    for controls,parser in ((dom,lexical_call),(scan.controls,regex_call)):
        found={}
        for tag,attr,action,label in controls:
            pair=parser(action)
            if pair and identity(*pair,label,channel,day,stage):
                found.setdefault((*pair,label),set()).add((tag,attr))
        inventories.append(found)
    left,right=inventories
    if len(left)!=1 or left!=right:raise RepairRejected("candidate_missing_ambiguous_or_disagrees")
    (path,token,label),shapes=next(iter(left.items()))
    for p,t,l,c,d,s in (("/other",token,label,channel,day,stage),(path,token,label,"PC" if channel=="SP" else "SP",day,stage),(path,token,"別開催",channel,day,stage),(path,token,label,channel,day,"entry" if stage=="meeting" else "meeting")):
        if identity(p,t,l,c,d,s):raise RepairRejected("counterexample_accepted")
    if stage=="meeting" and identity(path,token,label,channel,"20991231" if day!="20991231" else "20991230",stage):raise RepairRejected("wrong_day_accepted")
    rule={"encoding":enc,"form_selector":"UNIQUE_POST_CNAME","legacy_form_id":forms[0].get("id")=="commForm01","explicit_same_path":forms[0].get("action","").strip()==PATH,"shapes":[list(x) for x in sorted(shapes)],"grammar":"DUAL_SCANNER_V1"}
    proof={"schema":"kyoto_adaptive_navigation_repair.v1","source_sha256":digest(raw),"channel":channel,"day":day,"stage":stage,"candidate_count":1,"rule":rule,"rule_sha256":digest(canon(rule)),"action_sha256":digest(canon([path,token,label])),"parser_agreement":True,"counterexamples_rejected":True,"new_http_requests":0,"race_data_certified":False}
    return path,token,label,proof
