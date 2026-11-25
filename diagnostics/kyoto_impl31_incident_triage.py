"""A4: deterministic evidence-bound incident triage, no code promotion.

Separate observed execution failure, missing evidence, and data gaps. Produce
an isolated diagnostic/reproduction worklist, not a speculative root cause.
No network, credentials, URLs, external writes, or runtime code mutation.
"""
from hashlib import sha256
import json
import re

STAGES = {
    'PRE_HTTP_GUARD': ('CHECK_EVENT_DAY_CLOCK_PIN', 'REPLAY_PRE_HTTP_GUARD_OFFLINE'),
    'OFFLINE_REGRESSION': ('CHECK_TEST_RUNTIME_CLOCK_AND_DEPENDENCIES', 'REPLAY_FAILED_TEST_OUTSIDE_LIVE_SLOT'),
    'PC_CAPTURE': ('CHECK_OBSERVED_PC_LINK_AND_HTTP_STATE', 'REPLAY_PC_SAVED_ORIGINAL_OFFLINE'),
    'SP_CAPTURE': ('CHECK_OBSERVED_SP_LINK_AND_HTTP_STATE', 'REPLAY_SP_SAVED_ORIGINAL_OFFLINE'),
    'ENCRYPTION_OR_STOP': ('CHECK_ARCHIVE_MANIFEST_AND_BINDING', 'REPLAY_ARCHIVE_SEAL_OFFLINE'),
    'ARTIFACT': ('CHECK_EXACT_ARTIFACT_ID_AND_RETENTION', 'REPLAY_ARTIFACT_TRANSFER_OFFLINE'),
}
SOURCE_ERRORS = {
    'DECRYPT_OR_SOURCE_EVIDENCE_REJECTED', 'SOURCE_SHA_UTC_MISMATCH',
    'POSTFLIGHT_DAY_OR_CHANNEL_MISMATCH', 'RAW_RECEIPT_DAY_MISMATCH',
    'SP_RACEWISE_POSTFLIGHT_MISMATCH', 'DECRYPTED_WITHOUT_POSTFLIGHT_RECORD',
    'POSTFLIGHT_NO_SOURCE_ROWS', 'MALFORMED_SAFE_STOP', 'ENCRYPTED_ARTIFACT_INCOMPLETE',
}

def digest(obj):
    return sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def token(value):
    return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_]{1,100}',value) else 'UNKNOWN'

def diagnose(report):
    day=report.get('day')
    if day not in ('20261128','20261129') or report.get('schema')!='kyoto_impl25_c12_all_runs_day22_handoff.v1':
        raise ValueError('incident_report_identity')
    incidents=[]
    def add(rid,lane,kind,stage,state,head,checks):
        identity={'day':day,'run_id':rid,'lane':lane,'kind':kind,'stage':stage,'evidence_state':state,'head_sha':head}
        incidents.append({**identity,'incident_id':digest(identity),
            'root_cause_status':'NOT_YET_PROVED','diagnostic_checks':list(checks),
            'repair_candidate_state':'ISOLATED_REPRODUCTION_REQUIRED',
            'adoption_requires':['ORIGINAL_EVIDENCE','REPRODUCIBLE_FAILURE','ISOLATED_FIX','INDEPENDENT_REGRESSION','EXPLICIT_APPROVAL'],
            'automatic_code_change_authorized':False})
    if report.get('github_run_listing_complete') is not True:
        add(None,'INDEX','EVIDENCE_UNAVAILABLE','UNKNOWN','INCOMPLETE_INDEX',None,('CHECK_PAGINATION_AND_API','REOPEN_RUN_INDEX'))
    if report.get('missing_run_count_lower_bound',0)>0:
        add(None,'SCHEDULE','EXPECTED_RECORD_NOT_OBSERVED','UNKNOWN','MISSING_SCHEDULE_RECORD',None,('CHECK_CRON_AND_EVENT_HISTORY','DISTINGUISH_NOT_STARTED_FROM_FAILED'))
    seen=set()
    for item in report.get('scheduled_runs',[]):
        run=item['run'];rid=run['id']
        if type(rid) is not int or rid<=0 or rid in seen or run.get('event')!='schedule' or str(run.get('created_at',''))[:10]!=f'{day[:4]}-{day[4:6]}-{day[6:]}':
            raise ValueError('incident_run_identity')
        seen.add(rid)
        head=run.get('head_sha');head=head if isinstance(head,str) and re.fullmatch(r'[0-9a-f]{40}',head) else None
        state=token(item.get('state'))
        if state!='ALL_LANES_CLASSIFIED':
            add(rid,'RUN','EVIDENCE_UNAVAILABLE' if state=='RUN_METADATA_UNAVAILABLE' else 'RUN_NOT_CLASSIFIED','UNKNOWN',state,head,('CHECK_RUN_STATUS_AND_API','REOPEN_EXACT_RUN_METADATA'))
            continue
        for lane in ('PC','SP'):
            row=item['lanes'][lane]
            stage=token(row.get('failure_stage'));ev=token(row.get('artifact_evidence_state'))
            if row.get('job_conclusion')=='failure':
                add(rid,lane,'OBSERVED_EXECUTION_FAILURE',stage,ev,head,STAGES.get(stage,('INSPECT_EXACT_FAILED_STEP_AND_ORIGINALS','ISOLATE_UNKNOWN_FAILURE_OFFLINE')))
            elif ev=='PRE_HTTP_SAFE_STOP_NO_SOURCE':
                add(rid,lane,'PRE_HTTP_STOP_OBSERVED','PRE_HTTP_GUARD',ev,head,STAGES['PRE_HTTP_GUARD'])
            if ev in SOURCE_ERRORS:
                add(rid,lane,'EVIDENCE_REJECTED',stage,ev,head,('REOPEN_EXACT_ARCHIVE_OFFLINE','CHECK_IDENTITY_SHA_UTC_AND_AUTHENTICATION'))
            elif row.get('ciphertext_authenticated') is not True or row.get('source_original_sha_utc_checked') is not True:
                add(rid,lane,'EVIDENCE_UNAVAILABLE',stage,ev,head,('CHECK_ARTIFACT_EXISTENCE_AND_BINDING','DO_NOT_INFER_HTTP_FAILURE_OR_SUCCESS'))
            elif row.get('both_raw_market_originals_sha_utc_verified') is not True:
                add(rid,lane,'OBSERVED_SOURCE_GAP',stage,ev,head,('CHECK_PER_RACE_MARKET_ORIGINALS','REPRODUCE_MISSING_MARKET_PATH_OFFLINE'))
    incidents.sort(key=lambda i:(i['run_id'] or 0,i['lane'],i['kind'],i['incident_id']))
    return {'schema':'kyoto_impl31_incident_triage.v1','day':day,'input_report_sha256':digest(report),
        'incident_count':len(incidents),'incidents':incidents,
        'root_causes_certified':0,'code_promotion_authorized':False,'new_jra_http_requests':0}
