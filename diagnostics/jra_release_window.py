"""JRA publication-window opportunities; never asserts actual publication."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass

JST=ZoneInfo('Asia/Tokyo')
class PublicationGateError(ValueError):pass

@dataclass(frozen=True)
class PublicationOpportunity:
    event:str
    candidate_after_jst:datetime|None
    status:str
    source_evidence_required:bool=True
    ready_for_prediction:bool=False

def _aware(t):
    if not isinstance(t,datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise PublicationGateError('timezone_aware_clock_required')
    return t.astimezone(JST)

def publication_opportunity(race_day:date,at:datetime,*,event:str,
                            exceptional_race:bool=False,exceptional_override_jst:datetime|None=None):
    now=_aware(at)
    if not isinstance(race_day,date) or isinstance(race_day,datetime):
        raise PublicationGateError('race_day_required')
    if event not in ('ENTRIES_UNNUMBERED','DRAW_NUMBERED'):
        raise PublicationGateError('unknown_event')
    if exceptional_race or race_day.weekday() not in (5,6):
        if exceptional_override_jst is None:
            return PublicationOpportunity(event,None,'EXCEPTION_NEEDS_OFFICIAL_OVERRIDE')
        when=_aware(exceptional_override_jst)
    elif exceptional_override_jst is not None:
        raise PublicationGateError('unexpected_override_for_normal_race')
    elif event=='ENTRIES_UNNUMBERED':
        thursday=race_day-timedelta(days=(race_day.weekday()-3)%7)
        when=datetime.combine(thursday,time(16,0),JST)
    else:
        when=datetime.combine(race_day-timedelta(days=1),time(10,0),JST)
    return PublicationOpportunity(event,when,'MAY_CHECK_PUBLICATION' if now>when else 'WAIT_FOR_PUBLICATION_WINDOW')

def certify_publication(opportunity:PublicationOpportunity,evidence:dict):
    if opportunity.status!='MAY_CHECK_PUBLICATION':
        return {'status':'BLOCKED','reason':opportunity.status,'available':False}
    if not isinstance(evidence,dict) or evidence.get('structure_verified') is not True:
        return {'status':'BLOCKED','reason':'racecard_structure_not_verified','available':False}
    if not evidence.get('raw_sha256') or not evidence.get('fetched_at_utc'):
        return {'status':'BLOCKED','reason':'raw_bytes_or_timestamp_missing','available':False}
    if evidence.get('event')!=opportunity.event:
        return {'status':'BLOCKED','reason':'publication_stage_mismatch','available':False}
    return {'status':'PUBLICATION_EVIDENCE_PRESENT_NOT_FULLY_AUDITED',
            'reason':'requires_independent_raw_byte_and_runner_verification','available':False}
