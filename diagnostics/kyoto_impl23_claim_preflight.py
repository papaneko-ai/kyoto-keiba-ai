"""Read-only Turso coordinator probe; no JRA GET and no database mutations."""
from __future__ import annotations
import argparse
import json
import os
from diagnostics.kyoto_weekend_remote_claim_runtime import active_claims_for_weekend,CRON_SLOTS
from diagnostics.kyoto_shared_capture_reservation import key,ReservationError

CONFIRM='IMPL23-READ-ONLY-TURSO-PROBE'

def check(day, *, environ=None, transport=None, now_epoch=None):
    ctx=active_claims_for_weekend(day,environ=environ,transport=transport,now_epoch=now_epoch)
    if not ctx['enabled']:
        return {'status':'COORDINATOR_INACTIVE_EXISTING_CAPTURE_PRESERVED',
                'remote_schema_verified':False,'remote_write_verified':False,
                'production_claim_certified':False}
    claim_key=key(day=day,slot=ctx['claim_slot'],race=1,channel='PC',market='racecard')
    ctx['claim_client'].observe(claim_key)
    return {'status':'REMOTE_COORDINATOR_READ_AND_TABLE_VERIFIED',
            'remote_schema_verified':True,'remote_write_verified':False,
            'claim_slot':ctx['claim_slot'],'production_claim_certified':False}

def manual_read_only(day, *, environ=None, transport=None, now_epoch=None):
    """Inspect existing configured target without creating a schedule or claim."""
    env=dict(os.environ if environ is None else environ)
    if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch':
        raise ReservationError('manual_probe_requires_dispatch')
    if env.get('KYOTO_READONLY_PROBE_CONFIRMATION')!=CONFIRM:
        raise ReservationError('manual_probe_confirmation_required')
    if day not in CRON_SLOTS:
        raise ReservationError('manual_probe_day_invalid')
    if env.get('KYOTO_SHARED_CLAIM_ACTIVATE')!='YES':
        return {'status':'PRODUCTION_COORDINATOR_NOT_ENABLED_NO_REMOTE_IO',
                'remote_schema_verified':False,'remote_write_verified':False,
                'production_claim_certified':False}
    # Construct the existing client context without actually scheduling a capture.
    env['GITHUB_EVENT_NAME']='schedule'
    env['GITHUB_EVENT_SCHEDULE']=next(iter(CRON_SLOTS[day]))
    env['GITHUB_JOB']='impl23-read-only-probe'
    result=check(day,environ=env,transport=transport,now_epoch=now_epoch)
    result['status']='MANUAL_READ_ONLY_'+result['status']
    result['real_scheduled_slot_proven']=False
    result['production_claim_certified']=False
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--day',required=True,choices=('20261121','20261122'))
    parser.add_argument('--manual-read-only',action='store_true')
    args=parser.parse_args()
    result=manual_read_only(args.day) if args.manual_read_only else check(args.day)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
