"""Offline operator entrypoint: saved original bundle + frozen snapshot only.

No JRA HTTP, no Turso, no Streamlit, no model release. An unsuccessful
verification never emits a success receipt.
"""
import argparse
import json
from pathlib import Path
from diagnostics.p1_three_original_dual_intake import inspect_three_original_dual_intake


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--observed-utc',required=True)
    p.add_argument('--channel',choices=('PC','SP'),required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    if a.out.resolve() in (a.bundle.resolve(),a.snapshot.resolve()):
        raise ValueError('cannot_overwrite_original_inputs')
    if a.out.exists():
        raise ValueError('immutable_receipt_already_exists')
    result=inspect_three_original_dual_intake(
        a.bundle.read_bytes(),
        json.loads(a.snapshot.read_text(encoding='utf8')),
        observed_utc=a.observed_utc,racecard_channel=a.channel,
        verify_market_originals=True)
    if not result['market_prices_original_verified'] or not result['racecard_roster_original_verified']:
        raise ValueError('strict_content_verification_missing')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive create: refuse silent overwrites or replacement.
    with a.out.open('x',encoding='utf8') as f:
        json.dump(result,f,ensure_ascii=False,sort_keys=True,indent=2)
        f.write('\n')
    print(json.dumps({'status':result['status'],
                      'race':result['race'],
                      'original_content_verified':True,
                      'prediction_ready':False},ensure_ascii=False))
    return result


if __name__=='__main__':
    main()
