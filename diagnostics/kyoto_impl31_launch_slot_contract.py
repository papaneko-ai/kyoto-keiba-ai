"""Offline contract for sharing existing slot keys between trigger channels.

Not connected to live capture. This contract grants no production dispatch.
The caller must first authenticate the external sender and approve activation.
"""
from datetime import timedelta
from diagnostics.kyoto_impl31_launch_monitor import expected, SLOTS
from diagnostics.kyoto_shared_capture_reservation import key

DAYS=('20261128','20261129')

def resolve(day, event, cron, external_slot, now, *, external_verified=False):
    if day not in DAYS or now.utcoffset()!=timedelta(0) or now.strftime('%Y%m%d')!=day:
        raise ValueError('day_or_clock_mismatch')
    if event=='schedule':
        if external_slot is not None or cron not in SLOTS[day]:raise ValueError('schedule_identity')
        slot=SLOTS[day].index(cron)
    elif event=='workflow_dispatch':
        if external_verified is not True or cron or type(external_slot) is not int or not 0<=external_slot<4:
            raise ValueError('external_identity_unverified')
        slot=external_slot;cron=SLOTS[day][slot]
    else:raise ValueError('unrecognized_event')
    due=expected(day,cron)
    deadline=expected(day,SLOTS[day][slot+1]) if slot<3 else due.replace(hour=4,minute=0)
    if not due<=now<deadline:raise ValueError('outside_exact_slot_window')
    return {'day':day,'slot':slot,'cron':cron,'production_dispatch_authorized':False}

def market_key(identity,race,channel,market):
    return key(day=identity['day'],slot=identity['slot'],race=race,channel=channel,market=market)
