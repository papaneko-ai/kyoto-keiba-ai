"""Read-only launch watchdog; not a production dispatcher or authorization gate.

Missing run records, queue delay, execution failure and source success differ.
An explicit slot identity is mandatory; a timestamp alone never assigns a run.
"""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json

SLOTS = {
    '20261125': ('0 3 25 11 *', '30 3 25 11 *'),
    '20261126': ('15 0 26 11 *', '45 0 26 11 *'),
    '20261128': ('15 0 28 11 *', '15 1 28 11 *', '5 2 28 11 *', '50 2 28 11 *'),
    '20261129': ('15 0 29 11 *', '15 1 29 11 *', '10 2 29 11 *', '55 2 29 11 *'),
}
REHEARSAL = '.github/workflows/kyoto-impl31-a2-no-jra-schedule.yml'
PRODUCTION = '.github/workflows/kyoto-20261128-29-two-source-production-observer.yml'

def utc(s):
    t = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if t.utcoffset() != timedelta(0):
        raise ValueError('utc_required')
    return t

def expected(day, cron):
    if day not in SLOTS or cron not in SLOTS[day]:
        raise ValueError('not_declared_slot')
    minute, hour, *_ = cron.split()
    return datetime.strptime(day, '%Y%m%d').replace(hour=int(hour), minute=int(minute), tzinfo=timezone.utc)

def slot_key(day, cron):
    expected(day, cron)
    return f'{day}:{SLOTS[day].index(cron)}'

def report(day, now, runs, identities, *, complete, grace_seconds=300):
    """Classify only verified exact-run identities; input is a read-only snapshot.

    identities maps run ID to actual schedule cron read from a bound receipt or
    event record. The GitHub REST list itself does not identify the cron slot.
    Unassigned records therefore block a missing-slot conclusion conservatively.
    No HTTP POST, retry, production claim, or implied source success.
    """
    if day not in SLOTS or now.utcoffset() != timedelta(0) or type(complete) is not bool:
        raise ValueError('snapshot_identity')
    if type(grace_seconds) is not int or not 60 <= grace_seconds <= 900:
        raise ValueError('grace')
    path = REHEARSAL if day in ('20261125', '20261126') else PRODUCTION
    by = {c: [] for c in SLOTS[day]}; unknown=[]; seen=set()
    for r in runs:
        if r.get('path') != path or r.get('head_branch') != 'main' or r.get('event') != 'schedule':
            continue
        created=utc(r['created_at'])
        if created.strftime('%Y%m%d') != day:
            continue
        rid=r['id']
        if type(rid) is not int or rid <= 0 or rid in seen:
            raise ValueError('duplicate_or_invalid_run')
        seen.add(rid)
        cron=identities.get(str(rid))
        if cron not in by or created < expected(day, cron):
            unknown.append(rid); continue
        by[cron].append(r)
    slots=[]
    for cron, matches in by.items():
        due=expected(day,cron); age=int((now-due).total_seconds())
        item={'slot_key':slot_key(day,cron),'cron':cron,'scheduled_utc':due.isoformat(),
              'elapsed_seconds':max(0,age),'run_ids':sorted(r['id'] for r in matches),
              'source_success_proved':False,'production_dispatch_authorized':False}
        if age < 0: state='NOT_DUE'
        elif not complete: state='HISTORY_UNVERIFIED'
        elif len(matches)>1: state='MULTIPLE_RUNS_SAME_SLOT'
        elif not matches and unknown: state='UNASSIGNED_RUN_EVIDENCE'
        elif not matches: state='WITHIN_GRACE' if age<grace_seconds else 'NO_RUN_OBSERVED_AFTER_GRACE'
        else:
            r=matches[0]; status=r.get('status'); started=r.get('run_started_at')
            item['creation_delay_seconds']=int((utc(r['created_at'])-due).total_seconds())
            if started and status in ('in_progress','completed'):
                item['start_delay_seconds']=int((utc(started)-due).total_seconds())
            if status in ('queued','requested','waiting','pending'):state='RUN_QUEUED'
            elif status=='in_progress':state='RUN_IN_PROGRESS'
            elif status=='completed':state='RUN_COMPLETED_SUCCESS_NOT_SOURCE_PROOF' if r.get('conclusion')=='success' else 'RUN_COMPLETED_NOT_SUCCESS'
            else:state='RUN_STATE_UNVERIFIED'
        item['state']=state
        item['external_no_jra_probe_candidate']=state=='NO_RUN_OBSERVED_AFTER_GRACE' and path==REHEARSAL
        slots.append(item)
    result={'schema':'kyoto_impl31_launch_watch.v1','day':day,'observed_at_utc':now.isoformat(),
            'history_complete':complete,'unassigned_run_ids':sorted(unknown),'slots':slots,
            'network_mutations':0,'production_dispatch_authorized':False}
    result['sha256']=sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result
