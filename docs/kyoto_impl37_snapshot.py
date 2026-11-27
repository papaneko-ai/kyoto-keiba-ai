import json,os,subprocess,pathlib,hashlib,zipfile
P=pathlib.Path
m=json.loads(P('docs/KYOTO_IMPL37_SNAPSHOT_REQUEST.json').read_text())
repo=os.environ['GITHUB_REPOSITORY']
assert repo=='papaneko-ai/kyoto-keiba-ai'
def call(*a):return subprocess.check_output(a,timeout=60)
def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
def api(path):return call('gh','api',f'repos/{repo}/'+path)
def pack(root,out):
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for f in sorted(root.rglob('*')):
            if f.is_file():z.write(f,str(f.relative_to(root)))
source=P('snapshot_source');source.mkdir()
for label,sha in m['refs'].items():
    try:call('git','cat-file','-e',sha+'^{commit}')
    except subprocess.CalledProcessError:call('git','fetch','--no-tags','origin',sha)
    assert call('git','rev-parse',sha).decode().strip()==sha
    call('git','update-ref','refs/heads/impl37-snapshot/'+label,sha)
    write(source/'trees'/f'{label}.txt',call('git','ls-tree','-r',sha))
    write(source/'commits'/f'{label}.txt',call('git','show','--no-patch','--format=raw',sha))
call('git','bundle','create',str(source/'SOURCE_HISTORY.bundle'),*['refs/heads/impl37-snapshot/'+x for x in m['refs']])
write(source/'bundle_heads.txt',call('git','bundle','list-heads',str(source/'SOURCE_HISTORY.bundle')))
write(source/'bundle_verify.txt',call('git','bundle','verify',str(source/'SOURCE_HISTORY.bundle')))
write(source/'snapshot_request.json',json.dumps(m,indent=2).encode())
pack(source,'IMPL37_GITHUB_SOURCE.zip')
print('SOURCE_SNAPSHOT_COMPLETE',flush=True)
e=P('snapshot_evidence');e.mkdir()
errors=[]
for i in m['issues']:
    for path,name in [(f'issues/{i}',f'issue-{i}.json'),(f'issues/{i}/comments?per_page=100',f'issue-{i}-comments.json')]:
        try:write(e/name,api(path))
        except Exception as exc:errors.append([name,type(exc).__name__])
for i in m['prs']:
    try:write(e/f'pr-{i}.json',api(f'pulls/{i}'))
    except Exception as exc:errors.append([f'pr-{i}',type(exc).__name__])
for i in m['runs']:
    for suffix in ('','/jobs','/artifacts'):
        name=f'run-{i}'+suffix.replace('/','-')+'.json'
        try:write(e/name,api(f'actions/runs/{i}'+suffix))
        except Exception as exc:errors.append([name,type(exc).__name__])
write(e/'metadata_errors.json',json.dumps(errors,indent=2).encode())
write(e/'snapshot_request.json',json.dumps(m,indent=2).encode())
pack(e,'IMPL37_GITHUB_EVIDENCE.zip')
print('EVIDENCE_METADATA_COMPLETE',len(errors),flush=True)
