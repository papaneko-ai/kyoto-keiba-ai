"""Preserve independently revalidated SP structural roster evidence in C12.
This is a separate coverage ledger, never a PC denominator or odds/finality proof.
No network, raw horse names, production settings, or model promotion.
"""
import re
from datetime import datetime,timedelta
DAYS=('20261128','20261129')
RACES=tuple(str(n) for n in range(1,13))
def _sha(v):return isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) is not None
def _stamp(v,day):
    t=datetime.fromisoformat(v.replace('Z','+00:00'))
    if t.utcoffset()!=timedelta(0) or t.strftime('%Y%m%d')!=day:raise ValueError('invalid_utc_day')
    return t.isoformat()

def aggregate(day,entries):
    if day not in DAYS:raise ValueError('invalid_day')
    by={'schedule':{n:[] for n in RACES},'workflow_dispatch':{n:[] for n in RACES}}
    seen=set();unavailable=[];audited=0
    partial={'schedule':{n:[] for n in RACES},'workflow_dispatch':{n:[] for n in RACES}}
    for e in entries:
        r=e.get('run',{});rid=r.get('id');event=r.get('event')
        if event not in by or r.get('status')!='completed':continue
        if type(rid) is not int or rid<=0 or rid in seen:raise ValueError('duplicate_or_invalid_run')
        seen.add(rid)
        a=e.get('source_assessment',{}).get('SP',{})
        d=a.get('sp_saved_roster_audit',{}) if isinstance(a,dict) else {}
        if (not isinstance(a,dict) or not isinstance(d,dict) or a.get('ciphertext_authenticated') is not True or a.get('source_original_sha_utc_checked') is not True
            or a.get('channel')!='SP' or a.get('day')!=day or d.get('schema')!='kyoto_impl31_sp_saved_roster_audit.v1'
            or d.get('day')!=day or d.get('live_acquisition_certified') is not False
            or d.get('market_verified') is not False or d.get('prestart_certified') is not False
            or not isinstance(d.get('races'),dict) or set(d['races'])!=set(RACES)):
            unavailable.append({'run_id':rid,'event':event,'state':'SP_AUDIT_UNAVAILABLE'});continue
        audited+=1
        for n in RACES:
            v=d['races'][n]
            if not isinstance(v,dict):continue
            if v.get('state') in ('SP_SPLIT_LAYOUT_OBSERVED','SP_SPLIT_LAYOUT_PARTIAL'):
                try:
                    c=v['observed_row_count'];k=v['numeric_row_count'];u=v['cancelled_number_unknown_count']
                    if any(type(x) is not int for x in (c,k,u)) or not 2<=c<=18 or not 1<=k<=c or k+u!=c or u<0 or v['declared_runner_count_verified'] is not False or not _sha(v['source_sha256']) or not _sha(v['roster_sha256']) or ((u>0)!=(v['state']=='SP_SPLIT_LAYOUT_PARTIAL')):raise ValueError('invalid_partial')
                    partial[event][n].append({'run_id':rid,'state':v['state'],'observed_row_count':c,'numeric_row_count':k,'cancelled_number_unknown_count':u,'declared_runner_count_verified':False,'source_sha256':v['source_sha256'],'roster_sha256':v['roster_sha256'],'captured_at_utc':_stamp(v['captured_at_utc'],day)})
                except (KeyError,TypeError,ValueError,AttributeError):unavailable.append({'run_id':rid,'event':event,'race':n,'state':'SP_PARTIAL_OBSERVATION_REJECTED'})
                continue
            if v.get('state')!='SP_STRUCTURAL_ROSTER_OBSERVED':continue
            try:
                if type(v['runner_count']) is not int or not 2<=v['runner_count']<=18 or not _sha(v['source_sha256']) or not _sha(v['roster_sha256']):raise ValueError('invalid_observation')
                stamp=_stamp(v['captured_at_utc'],day)
                by[event][n].append({'run_id':rid,'runner_count':v['runner_count'],'source_sha256':v['source_sha256'],'roster_sha256':v['roster_sha256'],'captured_at_utc':stamp})
            except (KeyError,TypeError,ValueError,AttributeError):
                unavailable.append({'run_id':rid,'event':event,'race':n,'state':'SP_OBSERVATION_REJECTED'})
    out={}
    for event,rs in by.items():
        summary={}
        for n,obs in rs.items():
            obs=sorted(obs,key=lambda x:(x['captured_at_utc'],x['run_id'],x['source_sha256']))
            sig={(x['runner_count'],x['roster_sha256']) for x in obs}
            state='NO_VERIFIED_SP_ROSTER' if not obs else 'SP_ROSTER_CONFLICT' if len(sig)>1 else 'SP_STRUCTURAL_ROSTER_OBSERVED'
            summary[n]={'state':state,'observations':obs,'split_layout_observations':sorted(partial[event][n],key=lambda x:(x['captured_at_utc'],x['run_id'],x['source_sha256']))}
        out[event]={'races':summary,'structural_roster_races':sum(v['state']=='SP_STRUCTURAL_ROSTER_OBSERVED' for v in summary.values()),'conflict_races':sum(v['state']=='SP_ROSTER_CONFLICT' for v in summary.values()),'split_layout_races':sum(bool(v['split_layout_observations']) for v in summary.values())}
    return {'schema':'kyoto_impl32_sp_handoff.v1','day':day,'race_denominator':12,'audited_sp_runs':audited,
        'scheduled':out['schedule'],'manual':out['workflow_dispatch'],'unavailable':sorted(unavailable,key=lambda x:(x['run_id'],x.get('race',''))),
        'pc_denominator_modified':False,'prestart_certified':False,'market_verified':False,'live_acquisition_certified':False}
