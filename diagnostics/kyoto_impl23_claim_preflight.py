"""Read-only pre-HTTP gate for an explicitly enabled weekend Turso coordinator.

Never creates schema, updates a reservation, or makes a JRA request.
The selected target and schema must be prepared independently by the operator.
"""
from __future__ import annotations
import argparse
import json
from diagnostics.kyoto_weekend_remote_claim_runtime import active_claims_for_weekend
from diagnostics.kyoto_shared_capture_reservation import key


def check(day, *, environ=None, transport=None, now_epoch=None):
    ctx = active_claims_for_weekend(day, environ=environ, transport=transport,
                                    now_epoch=now_epoch)
    if not ctx['enabled']:
        return {'status':'COORDINATOR_INACTIVE_EXISTING_CAPTURE_PRESERVED',
                'remote_schema_verified':False, 'remote_write_verified':False}
    claim_key = key(day=day, slot=ctx['claim_slot'], race=1,
                    channel='PC', market='racecard')
    # SELECT works only when the table exists and the token has permission to read.
    # This does NOT demonstrate remote write permission or an actual race claim.
    ctx['claim_client'].observe(claim_key)
    return {'status':'REMOTE_COORDINATOR_READ_AND_TABLE_VERIFIED',
            'remote_schema_verified':True,'remote_write_verified':False,
            'claim_slot':ctx['claim_slot'], 'production_claim_certified':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--day',required=True,choices=('20261121','20261122'))
    args=parser.parse_args()
    result=check(args.day)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__': main()
