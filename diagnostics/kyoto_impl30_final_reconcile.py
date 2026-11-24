"""Post-race evidence reconciliation; no settlement/prediction authorization.

Two independently fetched official pages, matching identity and amounts, are
required. Unknown layouts, ambiguous refund or correction markers stay pending.
Synthetic fixtures are not evidence of the live official format.
"""
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations, product
from pathlib import Path
import json,re
from bs4 import BeautifulSoup
from diagnostics.parse_jra_result_roster import extract_result_roster
from diagnostics.p6_virtual_settlement_fixture_lab import _utc

class FinalEvidenceRejected(ValueError): pass

MARKETS={'quinella':('馬連','馬単',18),'bracket_quinella':('枠連','ワイド',8)}

def _text(raw):
    if type(raw) is not bytes or not 0<len(raw)<=1_500_000:raise FinalEvidenceRejected('invalid_original')
    try:s=raw.decode('cp932','strict')
    except UnicodeDecodeError:s=raw.decode('utf8','strict')
    return BeautifulSoup(s,'html.parser').get_text(' ',strip=True)

def _identity(text,day,race=None):
    y,m,d=map(int,(day[:4],day[4:6],day[6:]))
    if not re.search(fr'{y}年\s*{m}月\s*{d}日.{{0,50}}京都',text):raise FinalEvidenceRejected('wrong_meeting')
    if race is not None and not re.search(fr'京都.{{0,50}}(?<!\d){race}\s*(?:R|レース)(?!\d)',text):raise FinalEvidenceRejected('wrong_race')

def _pairs(text,market):
    label,end,limit=MARKETS[market]
    blocks=re.findall(r'(?<!\S)'+label+r'\s+(.+?)\s+'+end+r'(?=\s|$)',text)
    if len(blocks)!=1:raise FinalEvidenceRejected('market_section_not_unique:'+market)
    rest=blocks[0].strip();result={}
    pattern=re.compile(r'(\d{1,2})\s*[-－]\s*(\d{1,2})\s+((?:\d{1,3}(?:,\d{3})+|\d+))\s*円(?:\s+\d+\s+番人気)?(?:\s+|$)')
    while rest:
        m=pattern.match(rest)
        if not m:raise FinalEvidenceRejected('unrecognized_payout_fields:'+market)
        a,b,y=map(int,(m[1],m[2],m[3].replace(',','')));pair=(a,b)
        if not 1<=a<=b<=limit or (market=='quinella' and a==b) or not 100<=y<=20_000_000 or pair in result:raise FinalEvidenceRejected('invalid_or_duplicate_payout_pair')
        result[pair]=y;rest=rest[m.end():].strip()
    if not result:raise FinalEvidenceRejected('empty_payouts')
    return result

def _refunds(text):
    """Recognize explicit market-qualified pair refunds only; never infer frame refunds from horse withdrawal alone."""
    if not re.search(r'返還',text):return {'quinella':set(),'bracket_quinella':set()}
    # Recognize explicit no-refund statement or an unambiguous pair list.
    if re.search(r'返還\s*[:：]?\s*(?:なし|ありません)(?=\s|$)',text) and len(re.findall('返還',text))==1:return {'quinella':set(),'bracket_quinella':set()}
    matches=list(re.finditer(r'返還\s*(馬連|枠連)\s*[:：]\s*((?:\d{1,2}[-－]\d{1,2}(?:\s+|$))+)',text))
    if len(matches)!=len(re.findall('返還',text)):raise FinalEvidenceRejected('refund_layout_unverified')
    out={'quinella':set(),'bracket_quinella':set()}
    for m in matches:
        market='quinella' if m[1]=='馬連' else 'bracket_quinella';limit=MARKETS[market][2]
        for a,b in re.findall(r'(\d{1,2})[-－](\d{1,2})',m[2]):
            a,b=int(a),int(b)
            if not 1<=a<=b<=limit or (a==b and market=='quinella') or (a,b) in out[market]:raise FinalEvidenceRejected('invalid_refund_pair')
            out[market].add((a,b))
    return out

def reconcile(*,result_raw,payout_raw,day,race,registered,result_url,result_utc,payout_utc,start_utc):
    """Compare independently acquired result and payout originals; explicit finality still required."""
    if type(race) is not int or not 1<=race<=12:raise FinalEvidenceRejected('invalid_race')
    if not (_utc(start_utc)<_utc(result_utc) and _utc(start_utc)<_utc(payout_utc)):raise FinalEvidenceRejected('not_post_start')
    if sha256(result_raw).digest()==sha256(payout_raw).digest():raise FinalEvidenceRejected('not_independent_pages')
    a,b=_text(result_raw),_text(payout_raw)
    _identity(a,day,race);_identity(b,day)
    # Meeting payout page must identify each race separately. Reject duplicate
    # sections instead of borrowing the closest or first race's prices.
    sections=list(re.finditer(r'(?<!\d)(1[0-2]|[1-9])\s*(?:R|レース)(?!\d)',b))
    chosen=[i for i,m in enumerate(sections) if int(m[1])==race]
    if len(chosen)!=1:raise FinalEvidenceRejected('payout_race_section_ambiguous')
    i=chosen[0];section=b[sections[i].end():sections[i+1].start() if i+1<len(sections) else len(b)]
    roster=extract_result_roster(result_raw,result_url)
    if roster['parse_errors'] or roster['race_count']!=1:raise FinalEvidenceRejected('result_roster_invalid')
    rows=roster['races'][0]['rows'];actual=sorted((r['horse_number'],r['frame_number'],r['horse_name']) for r in rows)
    if actual!=sorted(tuple(x) for x in registered):raise FinalEvidenceRejected('registered_roster_mismatch')
    def rank(row):
        match=re.fullmatch(r'(\d{1,2})(?:\s*同着)?',row['placing'])
        return int(match[1]) if match else None
    first=[r for r in rows if rank(r)==1];second=[r for r in rows if rank(r)==2]
    if len(first)>=2 and not second:winning=list(combinations(first,2))
    elif len(first)==1 and second:winning=list(product(first,second))
    else:raise FinalEvidenceRejected('unresolved_placing')
    expected={'quinella':{tuple(sorted((x['horse_number'],y['horse_number']))) for x,y in winning},'bracket_quinella':{tuple(sorted((x['frame_number'],y['frame_number']))) for x,y in winning}}
    refund_a,refund_b=_refunds(a),_refunds(section)
    if refund_a!=refund_b:raise FinalEvidenceRejected('independent_refunds_disagree')
    cancelled={r['horse_number'] for r in rows if r['placing'] in ('取消','除外','出走取消','競走除外')}
    registered_numbers={r['horse_number'] for r in rows}
    expected_cancel_refunds={p for p in combinations(sorted(registered_numbers),2) if set(p)&cancelled}
    if not expected_cancel_refunds<=refund_a['quinella']:raise FinalEvidenceRejected('cancelled_refunds_unproved')
    for m,field in (('quinella','horse_number'),('bracket_quinella','frame_number')):
        allowed={r[field] for r in rows}
        if any(not set(p)<=allowed for p in refund_a[m]):raise FinalEvidenceRejected('refund_outside_roster')
    markets={}
    for market in MARKETS:
        pa,pb=_pairs(a,market),_pairs(section,market)
        if pa!=pb or set(pa)!=expected[market] or set(pa)&refund_a[market]:raise FinalEvidenceRejected('payout_or_placing_conflict:'+market)
        markets[market]={'payout_per_100':{'-'.join(map(str,p)):v for p,v in sorted(pa.items())},'refunded_pairs':[list(p) for p in sorted(refund_a[market])]}
    # Explicit finality of BOTH sections, never infer from evening time.
    final=all(re.search(r'(?<![未不非])確定(?:結果|払戻|着順)|(?:結果|払戻金|着順)\s*確定',s)
              and not re.search(r'未確定|確定前|確定待ち|速報|審議中',s) for s in (a,section))
    correction=any('訂正' in s for s in (a,section))
    if correction and not all('訂正' in s for s in (a,section)):raise FinalEvidenceRejected('correction_not_independently_confirmed')
    return {'schema':'kyoto_impl30_reconciled_postrace.v1','day':day,'race':race,'markets':markets,'result_sha256':sha256(result_raw).hexdigest(),'payout_sha256':sha256(payout_raw).hexdigest(),'result_utc':result_utc,'payout_utc':payout_utc,'state':'DUAL_PAGE_EXPLICIT_FINAL' if final else 'DUAL_PAGE_MATCH_FINALITY_UNPROVEN','correction':correction,'settlement_authorized':False}

def append_revision(directory,observation):
    """Immutable per-race sequence. Repeat identical payload is idempotent; change requires later explicit correction."""
    if observation.get('state')!='DUAL_PAGE_EXPLICIT_FINAL':raise FinalEvidenceRejected('finality_unproven')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if directory.is_symlink():raise FinalEvidenceRejected('unsafe_revision_directory')
    def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    prior=None;head='0'*64;versions=sorted(directory.glob('revision-*.json'))
    for i,path in enumerate(versions,1):
        if path.is_symlink() or path.name!=f'revision-{i:04d}.json':raise FinalEvidenceRejected('revision_sequence_invalid')
        row=json.loads(path.read_bytes());payload=row['observation'];body={'version':i,'previous_sha256':head,'observation':payload}
        if row!={**body,'sha256':sha256(canonical(body)).hexdigest()}:raise FinalEvidenceRejected('revision_chain_invalid')
        head=row['sha256'];prior=payload
    if prior is not None:
        if (prior['day'],prior['race'])!=(observation['day'],observation['race']):raise FinalEvidenceRejected('cross_race_revision')
        if prior['markets']==observation['markets']:return {'state':'UNCHANGED','version':len(versions),'sha256':head}
        if not observation['correction'] or min(_utc(observation[k]) for k in ('result_utc','payout_utc'))<=max(_utc(prior[k]) for k in ('result_utc','payout_utc')):raise FinalEvidenceRejected('unproven_or_stale_correction')
    body={'version':len(versions)+1,'previous_sha256':head,'observation':observation};row={**body,'sha256':sha256(canonical(body)).hexdigest()}
    with (directory/f'revision-{body["version"]:04d}.json').open('xb') as f:f.write(canonical(row)+b'\n')
    return {'state':'APPENDED','version':body['version'],'sha256':row['sha256']}
