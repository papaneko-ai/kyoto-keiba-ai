"""Strict offline JRA PC odds matrix extraction from original HTML bytes.
Output contains explicit non-live tag and must pass a separate as-of source gate.
"""
from bs4 import BeautifulSoup
from diagnostics.kyoto_cancel_odds_classifier import classify_odds_cell
from hashlib import sha256

class OddsMatrixError(ValueError):pass

def parse_matrix(raw,market,*,expected_runners=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1500000:
        raise OddsMatrixError("bad_source")
    if market not in ("quinella","bracket_quinella"):
        raise OddsMatrixError("unknown_market")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else ""
    label,selector=("馬連オッズ","table.basic.narrow-xy.umaren") if market=="quinella" else ("枠連オッズ","table.basic.narrow-xy.waku")
    if label not in title:raise OddsMatrixError("different_market")
    tables=soup.select(selector)
    if not tables:raise OddsMatrixError("market_tables_absent")
    n=len(tables)+1 if market=="quinella" else len(tables)
    if not 2<=n<=18 or (market=="bracket_quinella" and n>8):
        raise OddsMatrixError("invalid_market_dimension")
    if market=="quinella" and expected_runners is not None and n!=expected_runners:
        raise OddsMatrixError("horse_count_mismatch")
    pairs=[]
    for i,t in enumerate(tables,1):
        tokens=t.get_text(" ",strip=True).split()
        if not tokens or tokens[0]!=str(i):raise OddsMatrixError("bad_market_row")
        # 馬連: first token is the base horse number and is not a pair.
        # 枠連: first token is the same-frame pair's second number.
        rest=tokens[1:] if market=="quinella" else tokens
        if len(rest)%2:raise OddsMatrixError("pair_value_misaligned")
        last=i-1 if market=="bracket_quinella" else i
        for index in range(0,len(rest),2):
            try:
                second=int(rest[index])
            except ValueError as e:
                raise OddsMatrixError("bad_pair_number") from e
            cell=classify_odds_cell(rest[index+1])
            if cell.state!="VALID":
                raise OddsMatrixError("market_cell_"+cell.state.lower())
            odds=cell.odds
            if second<=last or second>n or not odds.is_finite() or odds<1:
                raise OddsMatrixError("bad_pair_or_odds")
            last=second
            pairs.append({"pair":[i,second],"odds":str(odds)})
    expected=n*(n-1)//2 if market=="quinella" else n*(n+1)//2
    if len(pairs)!=expected or len({tuple(p["pair"]) for p in pairs})!=expected:
        raise OddsMatrixError("market_incomplete")
    txt=soup.get_text(" ",strip=True)
    return {"schema":"jra_pc_market_matrix.v1","market":market,
       "title":title,"source_sha256":sha256(raw).hexdigest(),
       "source_bytes":len(raw),"matrix_dimension":n,"pair_count":len(pairs),
       "pairs":pairs,"historical_final_detected":"最終オッズ" in txt,
       "pre_race_quote_accepted":False,"training_ready":False,"prediction_ready":False}
