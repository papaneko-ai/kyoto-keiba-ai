"""Offline discovery bridge. Never certifies retrospective racecards as pre-race snapshots."""
from dataclasses import dataclass, asdict
from urllib.parse import urlsplit, parse_qs
import re

HOSTS = frozenset(('www.jra.go.jp', 'jra.go.jp', 'sp.jra.jp'))
BADGES = ('マルガイ','マル地','マル外','外','地','父内国産')

class EvidenceError(ValueError): pass

def validate_racecard_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in HOSTS or p.username or p.password:
        raise EvidenceError('non_official_or_insecure_source')
    if p.path!='/JRADB/accessD.html':
        raise EvidenceError('not_racecard_endpoint')
    cname=parse_qs(p.query, strict_parsing=True).get('CNAME',[])
    if len(cname)!=1 or not re.fullmatch(r'[a-zA-Z0-9/]+',cname[0]):
        raise EvidenceError('invalid_racecard_navigation_token')
    return cname[0]

def clean_display_name(text):
    """Remove *separate UI badges* only; never strip inside an actual horse name."""
    if not isinstance(text,str) or not text.strip():raise EvidenceError('missing_name')
    parts=text.strip().split()
    labels=[]
    while len(parts)>1 and parts[0] in BADGES:
        labels.append(parts.pop(0))
    return {'name':' '.join(parts),'display_badges':labels}

@dataclass(frozen=True)
class Source:
    race_number:int
    url:str
    discovered_via:str
    discovery_type:str='web_search_index'

SOURCES=(
    Source(1,'https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604100120261031%2F52','2026-10-31 Kyoto 1R official indexed racecard'),
    Source(6,'https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604100620261031%2FDB','2026-10-31 Kyoto 6R official indexed racecard'),
    Source(12,'https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604101220261031%2F59','2026-10-31 Kyoto 12R official indexed racecard'),
)

def source_manifest():
    for item in SOURCES:validate_racecard_url(item.url)
    return {'schema_version':'jra_racecard_discovery.v1','race_date':'2026-10-31',
            'venue':'KYOTO','sources':[asdict(x) for x in SOURCES],
            'raw_html_captured':False,'captured_before_off':False,
            'official_permanent_id_verified':False,'ready_for_training':False,
            'block_reason':'indexed_URL_does_not_prove_as_of_snapshot_or_complete_roster'}

def compare_independent_rows(result_rows,card_rows,*,historical_snapshot_proven=False):
    def index(rows):
        if not isinstance(rows,list):raise EvidenceError('rows_required')
        output={}
        for r in rows:
            n=r.get('horse_number')
            if type(n) is not int or n in output:raise EvidenceError('duplicate_or_invalid_horse_number')
            output[n]=r
        return output
    actual,card=index(result_rows),index(card_rows)
    matched=[];discrepancies=[]
    for n in sorted(actual.keys()&card.keys()):
        a=clean_display_name(actual[n]['horse_name'])['name']
        b=clean_display_name(card[n]['horse_name'])['name']
        if a==b and actual[n].get('frame_number')==card[n].get('frame_number'):
            matched.append(n)
        else:discrepancies.append({'horse_number':n,'reason':'horse_name_or_frame_mismatch'})
    return {'schema_version':'jra_racecard_result_comparison.v1',
            'result_rows':len(actual),'racecard_rows':len(card),
            'matched_horse_numbers':matched,'discrepancies':discrepancies,
            'result_only':sorted(actual.keys()-card.keys()),
            'card_only':sorted(card.keys()-actual.keys()),
            'full_roster_match':bool(actual and len(actual)==len(card)==len(matched) and not discrepancies),
            'historical_snapshot_proven':bool(historical_snapshot_proven),
            'ready_for_training':False,
            'block_reason':'retrospective_content_is_not_pre_race_evidence'}
