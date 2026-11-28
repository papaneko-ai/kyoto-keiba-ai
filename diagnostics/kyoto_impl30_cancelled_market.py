"""Cancellation-aware odds intake. Explicit current-row status only, not past form.

The registered roster remains immutable; excluded pairs never become prices.
Callers must supply the same race's verified original and capture timestamps.
"""
from collections import Counter
from hashlib import sha256
from itertools import combinations
from bs4 import BeautifulSoup
from diagnostics.kyoto_cancel_odds_classifier import classify_odds_cell,CANCELLED
from diagnostics.jra_odds_matrix_parser import OddsMatrixError,parse_matrix
from diagnostics.kyoto_g06_roster_aware_bracket import parse_bracket_with_roster
from diagnostics.jra_market_integrity_gate import utc

def parse_current_market(raw,market,registered,*,racecard=None,racecard_utc=None,market_utc=None,start_utc=None,day=None,race=None):
    registered=tuple(tuple(x) for x in registered)
    if not 2<=len(registered)<=18 or [x[0] for x in registered]!=list(range(1,len(registered)+1)) or any(type(f) is not int or not 1<=f<=8 for _,f in registered):
        raise OddsMatrixError('registered_roster_invalid')
    active=registered
    cancelled=set()
    mobile_cancellation=False
    if racecard is not None:
        soup=BeautifulSoup(racecard.decode('cp932',errors='strict'),'html.parser')
        tables=[t for t in soup.select('table') if all(t.select_one('th.'+x) for x in ('horse','num','waku'))]
        if len(tables)==1:
            for tr in tables[0].select('tr'):
                num=tr.select_one('td.num')
                if num is None: continue
                status=[s.get_text(' ',strip=True) for s in tr.select('td.status,td.horse > span,td.num > span')]
                if any(s in CANCELLED for s in status):
                    n=num.get_text(strip=True)
                    if n in CANCELLED and num.select_one("span.cap") is not None:
                        # Independently reparse the complete registered card;
                        # exact cancellation marker and row-order evidence.
                        from diagnostics.jra_multi_capture_20261106 import parse
                        rows,errors=parse(racecard,race,meeting_date=f'{day[:4]}-{day[4:6]}-{day[6:]}')
                        if errors or tuple((x["horse_number"],x["frame_number"]) for x in rows)!=registered:
                            raise OddsMatrixError('cancellation_roster_not_verified')
                        cancelled.update(x["horse_number"] for x in rows if x.get("cancelled") is True)
                    elif n.isascii() and n.isdigit():
                        cancelled.add(int(n))
                    else: raise OddsMatrixError('cancelled_row_number_invalid')
        elif day=="20261129":
            # Actual mobile cancellation cell is td.uban.keshi with a status
            # instead of the horse number. Require the independent registered
            # roster and strict row count/position, not an assumed missing pair.
            tables=soup.select("table")
            if tables:
                mobile=[tr for tr in tables[0].select("tr") if tr.select_one("td.uban") is not None]
                marked=[tr for tr in mobile if tr.select_one("td.uban").get_text(" ",strip=True) in CANCELLED]
                if marked:
                    from diagnostics.jra_pc_sp_benchmark import sp_rows
                    from diagnostics.jra_market_source_chain import _html_race_identity
                    if len(mobile)!=len(registered) or not all("keshi" in tr.select_one("td.uban").get("class",[]) for tr in marked):
                        raise OddsMatrixError("mobile_cancellation_rows_unverified")
                    try: rows=sp_rows(racecard)
                    except ValueError as exc:raise OddsMatrixError("mobile_cancellation_roster_unverified") from exc
                    if tuple((n,f) for n,f,_ in rows)!=registered or not _html_race_identity(racecard,day,"京都",race):
                        raise OddsMatrixError("mobile_cancellation_identity_unverified")
                    cancelled.update(n for n,tr in enumerate(mobile,1) if tr.select_one("td.uban").get_text(" ",strip=True) in CANCELLED)
                    mobile_cancellation=True
    if not cancelled:
        data=parse_matrix(raw,market,expected_runners=len(registered)) if market=='quinella' else parse_bracket_with_roster(raw,registered)
        return data,active
    # Existing parser checks official date/race and complete numbered/frame roster.
    from diagnostics.jra_multi_capture_20261106 import parse
    if not (utc(racecard_utc)<=utc(market_utc)<utc(start_utc)):
        raise OddsMatrixError('cancellation_evidence_time_invalid')
    if not mobile_cancellation:
        rows,errors=parse(racecard,race,meeting_date=f'{day[:4]}-{day[4:6]}-{day[6:]}')
        if errors or tuple((x['horse_number'],x['frame_number']) for x in rows)!=registered or '京都' not in soup.get_text(' ',strip=True):
            raise OddsMatrixError('cancellation_roster_not_verified')
    active=tuple(x for x in registered if x[0] not in cancelled)
    if len(active)<2 or not cancelled.issubset({n for n,f in registered}): raise OddsMatrixError('insufficient_active_roster')
    if market=='quinella':
        dimension=len(registered); expected=set(combinations([n for n,f in active],2)); label='馬連オッズ'; selector='table.basic.narrow-xy.umaren'; total=dimension-1
    elif market=='bracket_quinella':
        dimension=max(f for n,f in registered); counts=Counter(f for n,f in active); expected=set(combinations(sorted(counts),2))|{(f,f) for f in counts if counts[f]>=2}; label='枠連オッズ'; selector='table.basic.narrow-xy.waku'; total=dimension
    else: raise OddsMatrixError('unknown_market')
    doc=BeautifulSoup(raw.decode('cp932',errors='strict'),'html.parser');title=doc.title.get_text(' ',strip=True) if doc.title else ''
    tables=doc.select(selector)
    if label not in title or len(tables)!=total:raise OddsMatrixError('registered_matrix_dimension_mismatch')
    pairs=[];seen=set();excluded=[]
    for i,t in enumerate(tables,1):
        tokens=t.get_text(' ',strip=True).split()
        if not tokens or tokens[0]!=str(i):raise OddsMatrixError('bad_market_row')
        values=tokens[1:] if market=='quinella' or len(tokens)%2 else tokens
        if len(values)%2:raise OddsMatrixError('pair_value_misaligned')
        last=i if market=='quinella' else i-1
        for k in range(0,len(values),2):
            j=int(values[k]);pair=(i,j);cell=classify_odds_cell(values[k+1])
            if not last<j<=dimension or pair in seen:raise OddsMatrixError('bad_pair_order')
            last=j;seen.add(pair)
            if pair in expected:
                if cell.state!='VALID' or cell.odds<1:raise OddsMatrixError('eligible_pair_missing_quote')
                pairs.append({'pair':list(pair),'odds':str(cell.odds)})
            else:
                if cell.state!='CANCELLED' and values[k+1] not in ('-','--','---','発売なし','対象外'):raise OddsMatrixError('ineligible_pair_has_price_or_unknown_state')
                excluded.append({'pair':list(pair),'original':cell.original,'state':'INELIGIBLE_CONFIRMED_ROSTER'})
    if {tuple(p['pair']) for p in pairs}!=expected:raise OddsMatrixError('eligible_market_incomplete')
    return {'schema':'kyoto_cancelled_market.v1','source_sha256':sha256(raw).hexdigest(),'pair_count':len(pairs),'pairs':pairs,'excluded_pairs':excluded,'cancelled_horses':sorted(cancelled),'roster_sha256':sha256(racecard).hexdigest(),'historical_final_detected':'最終オッズ' in doc.get_text(' ',strip=True),'prediction_ready':False},active
