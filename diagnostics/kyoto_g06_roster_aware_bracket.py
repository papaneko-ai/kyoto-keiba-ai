"""Roster-aware bracket quinella odds parsing.

JRA bracket same-frame selections are eligible only when two or more
different runners share that frame. Missing/invalid same-frame placeholders
must not be confused with missing legitimate quoted pairs.
"""
from __future__ import annotations
from collections import Counter
from diagnostics.kyoto_cancel_odds_classifier import classify_odds_cell
from hashlib import sha256
from bs4 import BeautifulSoup
from diagnostics.jra_odds_matrix_parser import OddsMatrixError

def parse_bracket_with_roster(raw,active_runners):
    if type(raw) is not bytes or not 0<len(raw)<=1_500_000:
        raise OddsMatrixError("bad_source")
    if not isinstance(active_runners,(tuple,list)) or len(active_runners)<2:
        raise OddsMatrixError("verified_active_roster_required")
    numbers=[x[0] for x in active_runners]
    frames=[x[1] for x in active_runners]
    if (len(set(numbers))!=len(numbers) or
        any(type(n) is not int or not 1<=n<=18 for n in numbers) or
        any(type(f) is not int or not 1<=f<=8 for f in frames)):
        raise OddsMatrixError("bad_active_roster")
    counts=Counter(frames)
    ordered=sorted(counts)
    if ordered!=list(range(1,max(ordered)+1)):
        raise OddsMatrixError("unexpected_frame_gap")
    expected={(i,j) for i in ordered for j in ordered if i<j}
    expected|={(i,i) for i in ordered if counts[i]>=2}
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else ""
    if "枠連オッズ" not in title:
        raise OddsMatrixError("wrong_market")
    tables=soup.select("table.basic.narrow-xy.waku")
    if len(tables)!=len(ordered):
        raise OddsMatrixError("frame_row_count_mismatch")
    pairs=[]
    seen=set()
    for i,table in enumerate(tables,1):
        tokens=table.get_text(" ",strip=True).split()
        if not tokens or tokens[0]!=str(i):
            raise OddsMatrixError("row_identity_mismatch")
        values=tokens if len(tokens)%2==0 else tokens[1:]
        if len(values)%2:
            raise OddsMatrixError("odd_row_tokens")
        last=i-1
        for k in range(0,len(values),2):
            try:j=int(values[k])
            except ValueError as e:raise OddsMatrixError("bad_frame_number") from e
            if not i<=j<=len(ordered) or j<=last:
                raise OddsMatrixError("duplicate_or_reordered_frame")
            last=j
            raw_value=values[k+1]
            if (i,j) not in expected:
                if raw_value not in ("-","--","---","発売なし","対象外"):
                    raise OddsMatrixError("ineligible_same_frame_priced")
                continue
            if raw_value in ("-","--","---","発売なし","対象外"):
                raise OddsMatrixError("eligible_pair_missing_quote")
            cell=classify_odds_cell(raw_value)
            if cell.state!="VALID":
                raise OddsMatrixError("market_cell_"+cell.state.lower())
            price=cell.odds
            if not price.is_finite() or price<1:
                raise OddsMatrixError("bad_decimal_price")
            if (i,j) in seen:raise OddsMatrixError("duplicate_pair")
            seen.add((i,j))
            pairs.append({"pair":[i,j],"odds":str(price)})
    if seen!=expected:
        raise OddsMatrixError("eligible_market_incomplete")
    return {"schema":"kyoto_roster_aware_bracket_matrix.v1",
        "market":"bracket_quinella","title":title,
        "source_sha256":sha256(raw).hexdigest(),"source_bytes":len(raw),
        "matrix_dimension":len(ordered),"eligible_pair_count":len(expected),
        "pair_count":len(pairs),"pairs":pairs,
        "historical_final_detected":"最終オッズ" in soup.get_text(" ",strip=True),
        "pre_race_quote_accepted":False,"training_ready":False,"prediction_ready":False}
