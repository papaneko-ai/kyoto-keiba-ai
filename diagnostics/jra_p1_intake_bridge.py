"""Join a source-byte-verified offline bundle to a prerace structured snapshot.

No source parsing, network requests, betting or official-origin attestation.
A successful structural join NEVER marks data as prediction-ready.
"""
import io
import json
import zipfile
from datetime import datetime

from diagnostics.jra_p1_offline_handoff import import_bundle
from diagnostics.jra_p1_snapshot_gate import evaluate
from diagnostics.jra_p1_future_evidence import instant
from diagnostics.p1_prerace_market_coverage import inspect_quinella_coverage, MarketCoverageRejected


class IntakeRejected(ValueError):
    pass


def inspect_bundle_and_snapshot(bundle: bytes, snapshot: dict, *, observed_utc: str):
    """Validate separately and then reconcile race/date/raw-byte SHA evidence."""
    try:
        inspected = import_bundle(bundle, observed_utc=observed_utc)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            receipt = json.loads(archive.read('receipt.json'))
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise IntakeRejected('source_bundle_invalid') from exc

    if not isinstance(snapshot, dict):
        raise IntakeRejected('snapshot_invalid')
    checked = evaluate(snapshot, observed_utc=observed_utc)
    if checked['status'] != 'STRUCTURAL_CHECK_ONLY':
        raise IntakeRejected('snapshot_structural_blocked:' + ','.join(checked['reasons']))
    # Evidence and structured data must describe the SAME frozen pre-race cutoff.
    # Matching race and source hashes alone cannot establish that time contract.
    try:
        if instant(manifest.get('cutoff_utc')) != instant(snapshot.get('prediction_cutoff_utc')):
            raise IntakeRejected('cutoff_time_mismatch')
        if instant(observed_utc) >= instant(snapshot['prediction_cutoff_utc']):
            raise IntakeRejected('cutoff_already_elapsed')
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        if isinstance(exc, IntakeRejected):
            raise
        raise IntakeRejected('cutoff_timestamp_invalid') from exc
    try:
        coverage = inspect_quinella_coverage(snapshot)
    except MarketCoverageRejected as exc:
        raise IntakeRejected('market_coverage_invalid:' + str(exc)) from exc
    if coverage['market_completeness'] != 'STRUCTURAL_COMPLETE':
        raise IntakeRejected('incomplete_quinella_pairs')
    if manifest.get('meeting_date') != snapshot.get('meeting_date'):
        raise IntakeRejected('meeting_date_mismatch')
    if receipt.get('source_count') != 2 or len(manifest.get('sources', [])) != 2:
        raise IntakeRejected('requires_one_racecard_and_one_odds_original')
    wanted = {'racecard': 'racecard', 'pre_race_odds': 'odds'}
    provided = {}
    for row in manifest['sources']:
        if not isinstance(row, dict):
            raise IntakeRejected('source_row_invalid')
        key = wanted.get(row.get('kind'))
        if key is None or key in provided:
            raise IntakeRejected('source_kind_missing_or_duplicated')
        if row.get('race') != snapshot.get('race'):
            raise IntakeRejected('race_number_mismatch')
        provided[key] = row
    if set(provided) != {'racecard', 'odds'}:
        raise IntakeRejected('source_kind_missing_or_duplicated')
    for key, item in provided.items():
        claimed = snapshot['sources'][key]
        if item['sha256'] != claimed['sha256']:
            raise IntakeRejected(key + '_original_sha_mismatch')
        if datetime.fromisoformat(item['captured_utc'].replace('Z', '+00:00')) != datetime.fromisoformat(claimed['captured_utc'].replace('Z', '+00:00')):
            raise IntakeRejected(key + '_capture_time_mismatch')
    if inspected['source_count'] != 2:
        raise IntakeRejected('bundle_source_count_mismatch')
    return {'status': 'OFFLINE_SOURCE_JOIN_ONLY', 'meeting_date': snapshot['meeting_date'],
            'race': snapshot['race'], 'runner_count': checked['runner_count'],
            'expected_quinella_pairs': coverage['expected_quinella_pairs'],
            'market_coverage': coverage['market_completeness'],
            'bundle_sha256': inspected['raw_sha256'],
            'snapshot_sha256': checked['snapshot_sha256'],
            'prediction_ready': False, 'network_requests': 0,
            'unverified': checked['unverified']}



def inspect_bundle_and_dual_snapshot(bundle: bytes, snapshot: dict, *, observed_utc: str):
    """Strict offline dual-market join layered on the established byte/time gate.

    A bracket array and claimed sales states are NOT independent JRA proof.
    Until distinct official market-origin evidence and cancellation status are
    authenticated, this path remains research-only and refuses prediction.
    """
    from diagnostics.p1_dual_market_offline_audit import (
        inspect_dual_market, DualMarketRejected,
    )

    joined = inspect_bundle_and_snapshot(bundle, snapshot, observed_utc=observed_utc)
    try:
        market = inspect_dual_market(snapshot, observed_utc=observed_utc)
    except DualMarketRejected as exc:
        raise IntakeRejected('dual_market_invalid:' + str(exc)) from exc
    if market['status'] != 'STRUCTURAL_COMPLETE_ONLY':
        raise IntakeRejected('dual_market_not_structurally_complete_or_open')
    return {
        **joined,
        'status': 'OFFLINE_DUAL_MARKET_JOIN_ONLY',
        'dual_market': market,
        'expected_bracket_pairs': market['expected_bracket_pairs'],
        'bracket_market_coverage': 'STRUCTURAL_COMPLETE_ONLY',
        'withdrawals_officially_verified': False,
        'bracket_original_independently_verified': False,
        'market_sales_status_officially_verified': False,
        'prediction_ready': False,
        'actual_orders_authorized': False,
        'network_requests': 0,
    }
