"""Reparse EXISTING GitHub Actions Nov 6 original sources, without any JRA GET.

Use the old artifact ZIP and the same 148-runner registry. Missing originals are
reported, never inferred or silently replaced with parsed JSON.
"""
import argparse
import hashlib
import io
import json
import tarfile
import zipfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from diagnostics.jra_prior_form_offline import parse_horse_history


def digest(b):
    return hashlib.sha256(b).hexdigest()


def replay(archive: bytes, rows: list):
    if not isinstance(archive, bytes) or not 0 < len(archive) <= 10_000_000:
        raise ValueError('archive_size_invalid')
    if not isinstance(rows, list) or len(rows) != 148:
        raise ValueError('expected_148_horse_registry')
    with zipfile.ZipFile(io.BytesIO(archive)) as outer:
        if outer.namelist() != ['kyoto_ai_20261106_eod_complete_bundle.zip']:
            raise ValueError('outer_archive_schema_invalid')
        inner_bytes = outer.read(outer.namelist()[0])
    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
        if set(inner.namelist()) != {'git_snapshot.zip','source_originals.tar.gz','integrity_manifest.json'}:
            raise ValueError('inner_archive_schema_invalid')
        manifest = json.loads(inner.read('integrity_manifest.json'))
        source_tar = inner.read('source_originals.tar.gz')
        snapshot_zip = inner.read('git_snapshot.zip')
    if manifest.get('artifact_groups_downloaded') != 18 or manifest.get('schema') != 'kyoto_eod_final_bundle.v1':
        raise ValueError('archive_manifest_invalid')
    if digest(source_tar) != manifest.get('archive_sources_sha256') or digest(snapshot_zip) != manifest.get('archive_git_sha256'):
        raise ValueError('archive_digest_conflict')
    with zipfile.ZipFile(io.BytesIO(snapshot_zip)) as snap:
        original_rows=json.loads(snap.read('docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json'))
    if rows != original_rows:
        raise ValueError('registry_does_not_match_locked_snapshot')
    html={}
    with tarfile.open(fileobj=io.BytesIO(source_tar),mode='r:gz') as tf:
        members=tf.getmembers()
        if len(members)>500:
            raise ValueError('tar_entries_limit')
        for item in members:
            path=Path(item.name)
            if path.is_absolute() or '..' in path.parts or not(item.isdir() or item.isfile()):
                raise ValueError('tar_member_unsafe')
            if item.isfile() and item.name.endswith('.html'):
                if not 0 < item.size <= 2_000_000:
                    raise ValueError('html_size_invalid')
                raw=tf.extractfile(item).read()
                html.setdefault(digest(raw),[]).append((item.name,raw))
    states=Counter()
    out=[]
    used=set()
    for row in sorted(rows,key=lambda x:(x['race_number'],x['horse_number'])):
        identity=(row['race_number'],row['horse_number'])
        if identity in used:
            raise ValueError('duplicate_horse_identity')
        used.add(identity)
        profile_state=row['source_coverage']['horse_profile']
        if profile_state=='NOT_QUERIED':
            if row.get('profile_source_sha256'):
                raise ValueError('unqueried_profile_sha_invalid')
            continue
        if profile_state not in ('VERIFIED_SOURCE_ROWS','VERIFIED_EMPTY_HISTORY'):
            raise ValueError('unknown_profile_state')
        items=html.get(row['profile_source_sha256'],[])
        result={'race':identity[0], 'horse_number':identity[1], 'name':row['horse_name'],
                'profile_sha256':row['profile_source_sha256'], 'original_count':len(items),
                'status':'ORIGINAL_NOT_IN_RECOVERY','valid_prior_rows':None, 'verified_feature_fields':0}
        if len(items)==1:
            result['original_path']=items[0][0]
            try:
                parsed=parse_horse_history(items[0][1],
                    source_url='https://www.jra.go.jp'+row['profile_href'],
                    fetched_at_utc=datetime.fromisoformat(row['profile_captured_at_utc'].replace('Z','+00:00')),
                    prediction_cutoff_utc=datetime(2026,11,7,tzinfo=timezone.utc),
                    target_date=date(2026,11,7),expected_horse_name=row['horse_name'],
                    allow_verified_no_history=(profile_state=='VERIFIED_EMPTY_HISTORY'))
                result['valid_prior_rows']=parsed['prior_row_count']
                expected_count=(row.get('performance_features') or {}).get('prior_valid_finishes_available',0)
                if parsed['invalid_rows'] or parsed['history_status']!=row['profile_status'] or parsed['prior_row_count']!=expected_count:
                    raise ValueError('parser_count_or_history_state_disagreement')
                if not parsed['profile_captured_before_cutoff']:
                    raise ValueError('not_captured_before_cutoff')
                if profile_state=='VERIFIED_SOURCE_ROWS':
                    last=parsed['prior_rows'][:3]
                    expected={'prior_valid_finishes_available':parsed['prior_row_count'],
                        'recent_three_mean_distance_m':round(sum(x['distance_m'] for x in last)/len(last),2),
                        'recent_three_mean_finish_percentile':round(sum(x['finish_percentile'] for x in last)/len(last),6),
                        'recent_three_wins':sum(x['finish_position']==1 for x in last),
                        'recent_three_surface_counts':{s:sum(x['surface']==s for x in last) for s in ('芝','ダ','ダート','芝ダ','障')}}
                    if row['performance_features']!=expected:
                        raise ValueError('feature_bytes_to_registry_mismatch')
                    result['verified_feature_fields']=5
                result['status']='REPARSE_MATCH'
            except (ValueError,KeyError,TypeError,ZeroDivisionError) as exc:
                result['status']='REPARSE_CONFLICT'
                result['error']=str(exc)
        states[result['status']]+=1
        out.append(result)
    ok=[x for x in out if x['status']=='REPARSE_MATCH']
    return {'schema':'kyoto_p1_existing_originals_replay.v1',
        'source_artifact_id':13482994623, 'archive_sha256':digest(archive),
        'source_tar_sha256':digest(source_tar),'html_originals':sum(map(len,html.values())),
        'registered_profiles':len(out), 'reparsed_matching_profiles':len(ok),
        'reparsed_valid_prior_rows':sum(x['valid_prior_rows'] for x in ok),
        'verified_feature_fields':sum(x['verified_feature_fields'] for x in ok),
        'statuses':dict(states),'items':out, 'prediction_ready':False,
        'training_ready':False,'new_jra_http_requests':0}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--registry',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=replay(a.archive.read_bytes(),json.loads(a.registry.read_text(encoding='utf-8')))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('OFFLINE_REPARSE',result['statuses'],'prior_rows',result['reparsed_valid_prior_rows'])
    if result['statuses'].get('REPARSE_CONFLICT',0):
        raise SystemExit('REPARSE_CONFLICT')

if __name__=='__main__':main()
