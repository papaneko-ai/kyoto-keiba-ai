"""Mandatory fail-closed capacity/content gate before calling migration backups COMPLETE.

This rejects the implementation25 document-only regression by design.
CLI: python -m diagnostics.kyoto_impl25_migration_release_gate NEW.zip --previous PREVIOUS.zip
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

def sha(x): return hashlib.sha256(x).hexdigest()

def safe_zip(data, label):
    try:
        z=zipfile.ZipFile(io.BytesIO(data))
        names=z.namelist()
        if z.testzip() is not None: raise ValueError(label+':BAD_CRC')
        if len(names)!=len(set(names)): raise ValueError(label+':DUPLICATE_MEMBER')
        if any(n.startswith('/') or '..' in n.split('/') or '\\' in n for n in names):
            raise ValueError(label+':UNSAFE_PATH')
        return z
    except zipfile.BadZipFile as exc:
        raise ValueError(label+':BAD_ZIP') from exc

def sources_in_nested_zip(data):
    """Walk every nested ZIP; cap traversal and reject source omissions."""
    maximum=0
    queue=[(data,0)]
    seen=set()
    while queue:
        blob,depth=queue.pop()
        if sha(blob) in seen: continue
        seen.add(sha(blob))
        if depth>32 or len(seen)>80: raise ValueError('NESTED_ARCHIVE_LIMIT')
        with safe_zip(blob,'nested') as z:
            maximum=max(maximum,sum(i.filename.endswith('.py') and '/' in i.filename
                              for i in z.infolist() if not i.is_dir()))
            for i in z.infolist():
                if i.filename.lower().endswith('.zip') and not i.is_dir():
                    if i.file_size>300_000_000: raise ValueError('INNER_ARCHIVE_TOO_LARGE')
                    queue.append((z.read(i),depth+1))
    return maximum

def verify(new,previous,*,minimum_ratio=0.8,minimum_sources=1000,require_current=False):
    if not 0.5<=minimum_ratio<=1: raise ValueError('INVALID_RATIO')
    new_bytes=Path(new).read_bytes()
    old_bytes=Path(previous).read_bytes()
    if len(old_bytes)<1_000_000: raise ValueError('BASELINE_TOO_SMALL')
    ratio=len(new_bytes)/len(old_bytes)
    if ratio<minimum_ratio:
        raise ValueError('CAPACITY_COLLAPSE_FAIL_CLOSED:%.6f'%ratio)
    with safe_zip(new_bytes,'new') as z:
        names=z.namelist()
        if not any('START_HERE' in n.upper() for n in names):
            raise ValueError('START_HERE_MISSING')
        if not any('INSTRUCTIONS' in n.upper() and n.lower().endswith(('.md','.docx','.txt')) for n in names):
            raise ValueError('INSTRUCTIONS_MISSING')
        priors=[n for n in names if n.lower().endswith('.zip') and
                len(z.read(n))==len(old_bytes) and sha(z.read(n))==sha(old_bytes)]
        if len(priors)!=1: raise ValueError('PREVIOUS_FULL_SOURCE_NOT_EMBEDDED_EXACTLY')
        if '06_RECOVERY_BASELINE_AND_LIMITS.json' in names:
            m=json.loads(z.read('06_RECOVERY_BASELINE_AND_LIMITS.json'))
            if m.get('historical_full_source_sha256')!=sha(old_bytes):
                raise ValueError('PRIOR_SHA_MISMATCH')
            if m.get('historical_full_source_size_bytes')!=len(old_bytes):
                raise ValueError('PRIOR_BYTES_MISMATCH')
            entries=m.get('zip_contents_sha256',{})
            if not isinstance(entries,dict) or not entries: raise ValueError('EMPTY_MANIFEST')
            for name,digest in entries.items():
                if name not in names or sha(z.read(name))!=digest:
                    raise ValueError('MANIFEST_SHA_MISMATCH:'+name)
        elif 'SHA256_MANIFEST.json' in names:
            m=json.loads(z.read('SHA256_MANIFEST.json')).get('contents',{})
            if not isinstance(m,dict) or not m: raise ValueError('EMPTY_MANIFEST')
            for name,entry in m.items():
                if name not in names: raise ValueError('MANIFEST_MISSING:'+name)
                raw=z.read(name)
                digest=entry.get('sha256') if isinstance(entry,dict) else entry
                if sha(raw)!=digest: raise ValueError('MANIFEST_SHA_MISMATCH:'+name)
                if isinstance(entry,dict) and entry.get('bytes')!=len(raw):
                    raise ValueError('MANIFEST_LENGTH_MISMATCH:'+name)
        else:
            raise ValueError('CONTENT_MANIFEST_MISSING')
        if require_current:
            additions=[n for n in names if n.lower().endswith('.zip') and n not in priors]
            covered=False
            for n in additions:
                with safe_zip(z.read(n),'source') as source:
                    sub=source.namelist()
                    if (any('/source/main/' in x for x in sub)
                        and any('/source/development/' in x for x in sub)
                        and any(x.endswith('repository-all-refs.bundle') for x in sub)):
                        covered=True
            if not covered: raise ValueError('LATEST_MAIN_DEV_GIT_BUNDLE_MISSING')
    source_count=sources_in_nested_zip(new_bytes)
    if source_count<minimum_sources:
        raise ValueError('SOURCE_COUNT_COLLAPSE_FAIL_CLOSED:%d'%source_count)
    return {'status':'PASS','certification':'CURRENT_COMPLETE_SOURCE' if require_current else 'CUMULATIVE_HISTORICAL_SOURCE',
            'candidate_bytes':len(new_bytes),'baseline_bytes':len(old_bytes),
            'size_ratio':round(ratio,6),'size_change_percent':round((ratio-1)*100,4),
            'max_source_files_in_nested_layer':source_count,
            'candidate_sha256':sha(new_bytes),'baseline_sha256':sha(old_bytes),
            'latest_source_checked':require_current}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('candidate',type=Path)
    p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--minimum-ratio',type=float,default=.8)
    p.add_argument('--minimum-sources',type=int,default=1000)
    p.add_argument('--require-current-source',action='store_true')
    p.add_argument('--receipt',type=Path)
    a=p.parse_args()
    try:
        report=verify(a.candidate,a.previous,minimum_ratio=a.minimum_ratio,
                      minimum_sources=a.minimum_sources,require_current=a.require_current_source)
    except Exception as exc:
        print('MIGRATION_COMPLETE_RELEASE_REJECTED: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
    if a.receipt:
        a.receipt.parent.mkdir(parents=True,exist_ok=True)
        a.receipt.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('MIGRATION_COMPLETE_RELEASE_GATE_PASS')
    print(json.dumps(report,sort_keys=True))

if __name__=='__main__':main()
