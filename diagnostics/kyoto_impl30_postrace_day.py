"""Bounded, observed-menu-only post-race collector; source evidence, not settlement.

Reuse the historical JRA result roster and payout parsers. A parsed payout is
not a final certification; unsupported ties/refunds/corrections retain originals.
The caller supplies the verified pre-race card and an official-only transport.
"""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,re
from pathlib import Path
from urllib.parse import urljoin,urlsplit,parse_qs
from bs4 import BeautifulSoup
from diagnostics.parse_jra_result_roster import extract_result_roster
from diagnostics.kyoto_p6_real_historical_final_payout_reaudit import _payout
from diagnostics.jra_market_integrity_gate import utc

MENU={'results':('/JRADB/accessS.html','レース結果'),'payout':('/JRADB/accessH.html','払戻金')}
HOST='https://jra.jp'
ACTION=re.compile(r"(?:return\s+)?doAction\s*\(\s*['\"](/JRADB/access[SH]\.html)['\"]\s*,\s*['\"](pw[0-9A-Za-z]+/[0-9A-Za-z]+)['\"]\s*\)\s*;?\s*(?:return\s+false\s*;?)?",re.I)
LIMIT=1_500_000

class PostraceRejected(ValueError):pass

def visible(raw):
    if type(raw) is not bytes or not 0<len(raw)<=LIMIT:raise PostraceRejected('invalid_source_bytes')
    return BeautifulSoup(raw.decode('cp932',errors='strict'),'html.parser')

def observed_actions(raw,path,*,origin=HOST):
    if origin not in (HOST,'https://www.jra.go.jp'):raise PostraceRejected('unapproved_source_origin')
    found=set()
    for a in visible(raw).select('a'):
        label=a.get_text(' ',strip=True)
        act=ACTION.fullmatch(a.get('onclick','').strip())
        if act and act.group(1)==path:found.add((label,act.group(2),'POST',origin+path))
        href=a.get('href','')
        u=urlsplit(urljoin(origin,href));q=parse_qs(u.query)
        if u.scheme=='https' and u.netloc in ('jra.jp','www.jra.go.jp') and u.path==path and not u.fragment and set(q)=={'CNAME'} and len(q['CNAME'])==1 and re.fullmatch(r'pw[0-9A-Za-z]+/[0-9A-Za-z]+',q['CNAME'][0]):
            found.add((label,q['CNAME'][0],'GET',u.geturl()))
    return sorted(found)

def one(candidates):
    if len(candidates)!=1:raise PostraceRejected('missing_or_ambiguous_observed_navigation')
    return candidates[0]

def select_navigation(raw,day,stage,*,origin=HOST,race=None,meeting=None):
    """Bounded self-repair of observed JRA action selection, not token generation.

    Legacy mode 00/10 and mode 01 independently observed on Nov28 are accepted.
    All eligible actions participate in the ambiguity check. The repair must
    agree with independent fixed-field decomposition of the exact observed token.
    No old CNAME, URI, or suffix can become a request for a new page/day.
    """
    if day not in ('20261128','20261129') or stage not in ('results_meeting','payout_meeting','result_race'):
        raise PostraceRejected('navigation_scope')
    family={'results_meeting':'srl','payout_meeting':'hde','result_race':'sde'}[stage]
    path=MENU['payout' if stage=='payout_meeting' else 'results'][0]
    is_race=stage=='result_race'
    if is_race and (type(race) is not int or not 1<=race<=12 or not isinstance(meeting,str) or not re.fullmatch(r'\d{4}',meeting)):
        raise PostraceRejected('navigation_race_context')
    pattern=r'pw01'+family+r'(?P<mode>00|10|01)08'+day[:4]+r'(?P<meeting>\d{4})'+(f'{race:02d}' if is_race else '')+day+r'/[A-Za-z0-9]+'
    candidates=[]
    for action in observed_actions(raw,path,origin=origin):
        label,token,method,url=action
        match=re.fullmatch(pattern,token)
        if not match:continue
        mode,key=match.group('mode','meeting')
        if not is_race:
            heading=re.fullmatch(r'(\d{1,2})回京都(\d{1,2})日',label)
            if not heading or key!=f'{int(heading[1]):02d}{int(heading[2]):02d}':continue
        elif key!=meeting:continue
        # A second representation check independent of the regex capture.
        body,suffix=token.split('/')
        fields=body[len('pw01'+family):]
        if (fields[:2]!=mode or fields[2:4]!='08' or fields[4:8]!=day[:4]
            or fields[8:12]!=key or fields[12:]!=((f'{race:02d}' if is_race else '')+day)
            or not suffix or not 1<=int(key[:2])<=12 or not 1<=int(key[2:])<=12):
            continue
        candidates.append((action,mode,key))
    if len(candidates)!=1:raise PostraceRejected('missing_or_ambiguous_observed_navigation')
    action,mode,key=candidates[0]
    proof={'stage':stage,'race':race,'day':day,'meeting':key,'mode':mode,
           'source_sha256':sha256(raw).hexdigest(),'action_sha256':sha256(action[1].encode()).hexdigest(),
           'candidate_count':1,'legacy_candidate_count':int(mode!='01'),
           'rule':'OBSERVED_MODE_01_RECOVERY' if mode=='01' else 'LEGACY_OBSERVED_ACTION',
           'independent_field_agreement':True,'source_only':True}
    return action,proof

def parse_result(raw,*,day,race,url,registered):
    doc=visible(raw);text=doc.get_text(' ',strip=True)
    y,m,d=map(int,(day[:4],day[4:6],day[6:]))
    if not re.search(fr'{y}年\s*{m}月\s*{d}日.{{0,50}}京都.{{0,50}}(?<!\d){race}\s*(?:レース|R)(?!\d)',text):raise PostraceRejected('result_race_identity_mismatch')
    if 'レース結果' not in text or '着順' not in text:raise PostraceRejected('result_table_not_published')
    parsed=extract_result_roster(raw,url)
    if parsed['parse_errors'] or parsed['race_count']!=1:raise PostraceRejected('result_roster_invalid')
    rows=[{**x,'race_number':race,'race_day':day} for x in parsed['races'][0]['rows']]
    expected=sorted(tuple(x) for x in registered)
    actual=sorted((x['horse_number'],x['frame_number'],x['horse_name']) for x in rows)
    if actual!=expected:raise PostraceRejected('result_vs_registered_roster_mismatch')
    first=[x for x in rows if x['placing']=='1'];second=[x for x in rows if x['placing']=='2']
    result={'state':'RESULT_ROWS_OBSERVED_PAYOUT_UNVERIFIED','rows':rows,'source_sha256':sha256(raw).hexdigest(),'final_status_verified':False,'settlement_authorized':False}
    if len(first)!=1 or len(second)!=1:return {**result,'reason':'DEAD_HEAT_OR_NONUNIQUE_PLACINGS_REVIEW'}
    if len(re.findall(r'払戻金\s+単勝',text))!=1:return {**result,'reason':'PAYOUT_SECTION_MISSING_OR_AMBIGUOUS'}
    try:
        q=_payout(text,'馬連','馬単');b=_payout(text,'枠連','ワイド')
    except ValueError:return {**result,'reason':'PAYOUT_FORMAT_NEEDS_REVIEW'}
    if q['pair']!=sorted([first[0]['horse_number'],second[0]['horse_number']]) or b['pair']!=sorted([first[0]['frame_number'],second[0]['frame_number']]):return {**result,'reason':'PAYOUT_VS_PLACING_CONFLICT'}
    if any(x['placing'] in ('取消','除外','中止','失格') for x in rows) or re.search(r'返還\s*[:：]|訂正|同着',text):
        return {**result,'quinella':q,'bracket_quinella':b,'reason':'REFUND_CORRECTION_OR_EXCEPTION_REVIEW'}
    return {**result,'state':'RESULT_AND_PAYOUT_PARSED_FINAL_NOT_CERTIFIED','quinella':q,'bracket_quinella':b}

def collect_day(root,*,day,seed_raw,seed_sha256,registered,fetch,clock,not_before_utc,verified_starts=None,seed_origin=HOST,prior_navigation=()):
    """All 12 slots retained; observed raw pages saved before any parsing.

    fetch(method,url,token) returns {raw, captured_at_utc, requested_url, method,
    observed_action_token}; the transport must enforce same-origin/no redirect.
    No fabricated URL, no settlement, no authentication claim from hash alone.
    """
    if day not in ('20261128','20261129') or set(registered)!=set(range(1,13)):raise PostraceRejected('day_or_roster_contract')
    if seed_origin not in (HOST,'https://www.jra.go.jp'):raise PostraceRejected('unapproved_seed_origin')
    if sha256(seed_raw).hexdigest()!=seed_sha256:raise PostraceRejected('seed_hash_mismatch')
    now=utc(clock());cutoff=utc(not_before_utc)
    # This entry point is for a separate evening observation, not live pre-race.
    if now<cutoff or now.strftime('%Y%m%d')!=day or cutoff.strftime('%Y%m%d')!=day or cutoff.hour<10:raise PostraceRejected('postrace_window_not_proven')
    root=Path(root)
    if root.exists() or root.is_symlink() or not root.parent.is_dir():raise PostraceRejected('fresh_root_required')
    root.mkdir();report={'schema':'kyoto_impl30_postrace_day.v1','day':day,'seed_sha256':seed_sha256,'seed_origin':seed_origin,'requests':[],'races':{},'source_only':True,'settlement_authorized':False}
    def save(name,action):
        label,token,method,url=action
        response=fetch(method,url,token)
        raw=response['raw'];stamp=response['captured_at_utc']
        if type(raw) is not bytes or not 0<len(raw)<=LIMIT or response['requested_url']!=url or response['method']!=method or response['observed_action_token']!=token or utc(stamp)<cutoff or utc(stamp).strftime('%Y%m%d')!=day:raise PostraceRejected('transport_evidence_mismatch')
        with (root/name).open('xb') as f:f.write(raw)
        report['requests'].append({'file':name,'sha256':sha256(raw).hexdigest(),'bytes':len(raw),'captured_at_utc':stamp,'source_url':url,'method':method,'action_token':token})
        return raw,url
    report['navigation_recovery']=[]
    prior_modes={(p.get('stage'),p.get('mode')) for p in prior_navigation
                 if isinstance(p,dict) and p.get('rule')=='OBSERVED_MODE_01_RECOVERY'
                 and p.get('independent_field_agreement') is True}
    def selected(data,stage,**kw):
        action,proof=select_navigation(data,day,stage,**kw)
        proof['prior_failure_revalidated']=((stage,proof['mode']) in prior_modes)
        report['navigation_recovery'].append(proof)
        return action,proof['meeting']
    result_meeting=None
    result_meeting_key=None
    payout_meeting=None
    payout_stamp=None
    try:
        for market,(path,label) in MENU.items():
            try:
                raw,menu_url=save(market+'_menu.html',one([a for a in observed_actions(seed_raw,path,origin=seed_origin) if a[0]==label]))
                action,key=selected(raw,market+'_meeting',origin='https://'+urlsplit(menu_url).netloc)
                meeting,meeting_url=save(market+'_meeting.html',action)
                report[market+'_meeting_state']='ORIGINAL_OBSERVED_NOT_FINAL_PROOF'
                if market=='results':result_meeting=meeting;result_meeting_origin='https://'+urlsplit(meeting_url).netloc;result_meeting_key=key
                else:
                    payout_meeting=meeting
                    payout_stamp=report['requests'][-1]['captured_at_utc']
            except Exception as exc:report[market+'_meeting_state']=type(exc).__name__+':'+str(exc)[:80]
        for race in range(1,13):
            row={'state':'RESULT_NOT_OBSERVED'}
            try:
                if result_meeting is None:raise PostraceRejected('result_meeting_not_available')
                action,_=selected(result_meeting,'result_race',origin=result_meeting_origin,race=race,meeting=result_meeting_key)
                raw,url=save(f'r{race:02d}_result.html',action)
                if registered[race] is None:raise PostraceRejected('independent_registered_roster_missing')
                row=parse_result(raw,day=day,race=race,url=url,registered=registered[race])
                # Independently parse both original pages, including cases the
                # legacy single-payout parser cannot resolve (ties/refunds).
                if verified_starts is not None and verified_starts.get(race) and payout_meeting is not None:
                    try:
                        from diagnostics.kyoto_impl30_final_reconcile import reconcile
                        row["independent_reconciliation"]=reconcile(result_raw=raw,payout_raw=payout_meeting,
                            day=day,race=race,registered=registered[race],result_url=url,
                            result_utc=report['requests'][-1]['captured_at_utc'],
                            payout_utc=payout_stamp,start_utc=verified_starts[race])
                    except (ValueError,TypeError,KeyError) as exc:
                        row["independent_reconciliation"]={"state":"RECONCILIATION_PENDING","reason":str(exc)[:100]}
            except Exception as exc:row={'state':'RESULT_SOURCE_OR_PARSE_FAILED','reason':type(exc).__name__+':'+str(exc)[:100], 'raw_result_saved':(root/f'r{race:02d}_result.html').is_file()}
            report['races'][str(race)]=row
    finally:
        report['structured_result_payout_races']=sum(x['state']=='RESULT_AND_PAYOUT_PARSED_FINAL_NOT_CERTIFIED' for x in report['races'].values())
        report['dual_page_explicit_final_races']=sum(x.get('independent_reconciliation',{}).get('state')=='DUAL_PAGE_EXPLICIT_FINAL' for x in report['races'].values())
        report['dual_page_published_source_races']=sum(x.get('independent_reconciliation',{}).get('official_payout_publication_verified') is True for x in report['races'].values())
        report['raw_result_races']=sum((root/f'r{n:02d}_result.html').is_file() for n in range(1,13))
        report['raw_payout_meeting_saved']=(root/'payout_meeting.html').is_file()
        report['confirmed_final_races']=0
        with (root/'receipt.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,sort_keys=True,indent=2)
    return report
