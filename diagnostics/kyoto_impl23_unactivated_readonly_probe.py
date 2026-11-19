"""Read-only Turso readiness probe without enabling production capture.

No source HTTP, schema creation or database mutation.  This diagnostic must
never set KYOTO_SHARED_CLAIM_ACTIVATE or authorize scheduled claims.
"""
from __future__ import annotations
import json,os,re
from urllib.parse import urlsplit
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims,TursoClaimUnconfirmed
from diagnostics.kyoto_weekend_remote_claim_runtime import UrllibTransport
from diagnostics.kyoto_turso_isolated_virtual_store import EXPECTED_HOST
from diagnostics.kyoto_shared_capture_reservation import key,ReservationError

CONFIRM = 'IMPL23-READ-ONLY-TURSO-PROBE'
NEEDED = ('KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST',
          'KYOTO_SHARED_CLAIM_TURSO_URL','KYOTO_SHARED_CLAIM_TURSO_TOKEN')

def probe(day,*,environ=None,transport=None):
    env=dict(os.environ if environ is None else environ)
    if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch':
        raise ReservationError('manual_only_no_schedule')
    if env.get('KYOTO_READONLY_PROBE_CONFIRMATION')!=CONFIRM:
        raise ReservationError('manual_confirmation_required')
    if day not in ('20261121','20261122'):
        raise ReservationError('invalid_target_day')
    missing=[name for name in NEEDED if not env.get(name)]
    status={'schema':'kyoto_impl23_readonly_probe.v2',
            'capture_activation_unchanged':True,
            'production_claim_certified':False,'remote_write_verified':False,
            'real_scheduled_slot_proven':False}
    if missing:
        return {**status,'status':'READ_ONLY_CONFIGURATION_INCOMPLETE_NO_REMOTE_IO',
                'missing_variable_names':missing,'remote_schema_verified':False}
    host=env['KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST']
    url=env['KYOTO_SHARED_CLAIM_TURSO_URL']
    p=urlsplit(url)
    if (not re.fullmatch(r'[a-z0-9-]+(?:\\.[a-z0-9-]+)*\\.turso\\.io',host)
        or host==EXPECTED_HOST or p.hostname!=host
        or p.scheme not in ('libsql','https') or p.path not in ('','/')
        or p.query or p.fragment or p.port is not None or p.username or p.password):
        raise ReservationError('production_host_not_independently_verified')
    client=TursoCaptureClaims(url=url,token=env['KYOTO_SHARED_CLAIM_TURSO_TOKEN'],
                              transport=transport or UrllibTransport())
    # A synthetic key for a non-existent race acquisition: SELECT only.
    client.observe(key(day=day,slot=0,race=1,channel='PC',market='racecard'))
    return {**status,'status':'PRODUCTION_TURSO_READ_AND_TABLE_VERIFIED_ONLY',
            'remote_schema_verified':True,'missing_variable_names':[]}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--day',required=True,choices=('20261121','20261122'))
    a=p.parse_args()
    print(json.dumps(probe(a.day),sort_keys=True))

if __name__=='__main__':main()
