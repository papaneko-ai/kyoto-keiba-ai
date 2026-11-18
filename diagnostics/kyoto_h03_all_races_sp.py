"""H03 bounded twelve-race SP collection from a saved, independent SP navigation.

Experimental-only. Never derive SP URLs from PC CNAME; missing links fail closed.
No direct network I/O: the caller explicitly supplies a bounded opener/pacer.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from datetime import datetime, timezone
import json
from diagnostics.jra_pc_sp_benchmark import observed_sp_race_links_from_saved_navigation, sp_rows
from diagnostics.kyoto_sp_observed_source import capture_observed_sp

class H03Error(ValueError): pass

def plan_all_races(nav_original, *, nav_url, day, captured_utc):
    try:
        stamp=datetime.fromisoformat(captured_utc.replace('Z','+00:00'))
        if stamp.tzinfo is None or stamp.utcoffset()!=timezone.utc.utcoffset(None):
            raise ValueError('not_utc')
        result=observed_sp_race_links_from_saved_navigation(
            nav_original,source_url=nav_url,source_sha256=sha256(nav_original).hexdigest(),race_day=day)
    except (ValueError, TypeError, AttributeError) as exc:
        raise H03Error('invalid_independent_navigation') from exc
    links={row['race_number']:row['url'] for row in result['race_links']}
    return {'schema':'kyoto_h03_sp_twelve_race_plan.v1','day':day,
            'navigation_sha256':result['source_sha256'],'navigation_url':nav_url,
            'navigation_captured_utc':captured_utc,'observed':links,
            'missing_races':[i for i in range(1,13) if i not in links],
            'complete_navigation':len(links)==12,'network_requests':0,
            'source':'INDEPENDENT_SAVED_SP_ANCHORS','experimental_only':True}

def collect_all_races(root, *, nav_original,nav_url,day,captured_utc,opener,pacer=None):
    """One observed racecard per race, zero guessed URLs; persist each outcome.

    Never overwrite a pre-existing directory. A roster parser success is NOT
    proof of actual runners being complete until independently reconciled.
    """
    base=Path(root)
    if base.exists() or base.is_symlink() or not base.parent.is_dir():
        raise H03Error('output_not_fresh')
    plan=plan_all_races(nav_original,nav_url=nav_url,day=day,captured_utc=captured_utc)
    base.mkdir()
    (base/'official_sp_navigation.html').write_bytes(nav_original)
    receipts=[]
    for race in range(1,13):
        if race not in plan['observed']:
            receipts.append({'race_number':race,'state':'UNOBSERVED_LINK','network_requests_started':0})
            continue
        receipt=capture_observed_sp(base/f'race_{race:02d}',navigation_original=nav_original,
                                    navigation_url=nav_url,race_day=day,
                                    navigation_captured_utc=captured_utc,race_number=race,
                                    opener=opener,pacer=pacer)
        if receipt['racecard_fetched']:
            try:
                rows=sp_rows((base/f'race_{race:02d}'/'official_sp_racecard.html').read_bytes())
                receipt['parsed_horse_count']=len(rows)
                receipt['horse_numbers']=[row[0] for row in rows]
                receipt['state']='SP_ROSTER_PARSED_NEEDS_INDEPENDENT_PARITY'
            except (ValueError,TypeError,IndexError) as exc:
                receipt['state']='SP_ROSTER_UNVERIFIED'
                receipt['parser_error_class']=type(exc).__name__
        receipts.append(receipt)
    summary={'schema':'kyoto_h03_all_races_offline_plan_capture.v1','day':day,
             'navigation_sha256':plan['navigation_sha256'],
             'observed_race_links':len(plan['observed']),
             'captured_races':sum(bool(x.get('racecard_fetched')) for x in receipts),
             'parsed_rosters':sum(x['state']=='SP_ROSTER_PARSED_NEEDS_INDEPENDENT_PARITY' for x in receipts),
             'missing_races':plan['missing_races'],'receipts':receipts,
             'network_requests_started':sum(x['network_requests_started'] for x in receipts),
             'all_races_live_verified':False,'all_horses_parity_verified':False,
             'h03_certified':False,'experimental_only':True}
    (base/'h03_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return summary
