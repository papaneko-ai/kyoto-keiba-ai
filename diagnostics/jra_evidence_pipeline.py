"""Read-only offline integrity and source-type verification of a saved JRA HTML capture."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import json

class EvidenceError(ValueError): pass

def utc(s):
    try:
        d=datetime.fromisoformat(s.replace('Z','+00:00'))
        if d.tzinfo is None or d.utcoffset() is None:raise ValueError('naive')
        return d.astimezone(timezone.utc)
    except (ValueError,AttributeError,TypeError) as e:
        raise EvidenceError('invalid_timestamp') from e

def identify_structure(raw):
    s=BeautifulSoup(raw.decode('cp932',errors='replace'),'html.parser')
    title=s.title.get_text(' ',strip=True) if s.title else ''
    result_tables=[t for t in s.select('table') if all(t.select_one('th.'+c) for c in ('place','num','waku','horse'))]
    if result_tables:kind='POST_RACE_RESULT'
    elif '開催選択' in title:kind='MEETING_SELECTION'
    elif '出馬表' in title and s.select('table'):kind='RACECARD_CANDIDATE'
    else:kind='UNKNOWN_STRUCTURE'
    return {'structure':kind,'title':title,'table_count':len(s.select('table')),
            'result_table_count':len(result_tables),
            'racecard_rows_confirmed':False,'runner_id_confirmed':False}

def verify_archived_capture(raw,manifest,cutoff_utc=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=2000000:raise EvidenceError('invalid_bytes')
    p=urlsplit(manifest.get('response_url',manifest.get('source_url','')))
    if p.scheme!='https' or p.hostname not in ('www.jra.go.jp','jra.go.jp') or p.username or p.password:
        raise EvidenceError('invalid_official_source')
    digest=sha256(raw).hexdigest()
    if manifest.get('source_sha256')!=digest:raise EvidenceError('source_hash_mismatch')
    if manifest.get('bytes')!=len(raw):raise EvidenceError('source_length_mismatch')
    fetched=utc(manifest.get('fetched_at_utc'))
    prior=bool(cutoff_utc is not None and fetched<utc(cutoff_utc))
    return {'schema_version':'jra_raw_evidence_verified.v1',
            'verified_raw_bytes':True,'source_sha256':digest,
            'fetched_at_utc':fetched.isoformat(),
            'structure':identify_structure(raw),
            'captured_before_cutoff':prior,
            'racecard_runners_verified':False,'official_permanent_horse_ids_verified':False,
            'prediction_ready':False,'training_ready':False,
            'reason':'integrity_only; independent racecard/roster/ID proof still required'}

def audit_capture_directory(folder,cutoff_utc=None):
    p=Path(folder)
    m=json.loads((p/'capture_report.json').read_text(encoding='utf8'))
    name=m.get('original_html_path',m.get('raw_html_path'))
    if name!='jra_racecard_response.html':raise EvidenceError('unsupported_original_path')
    return verify_archived_capture((p/name).read_bytes(),m,cutoff_utc)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--capture-directory',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--cutoff-utc')
    a=ap.parse_args()
    report=audit_capture_directory(a.capture_directory,a.cutoff_utc)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
