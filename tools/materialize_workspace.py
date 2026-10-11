"""Restore source paths into an isolated workspace without overwriting changed files."""
from pathlib import Path
import argparse
import hashlib
import json

parser=argparse.ArgumentParser()
parser.add_argument('--output',required=True,type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1];out=args.output.resolve()
if out==root or root.is_relative_to(out):raise ValueError('Use a separate output workspace')
manifest=json.loads((root/'UPLOAD_MANIFEST.json').read_text(encoding='utf-8'));planned={}
for entry in manifest['files']:
    exported=Path(entry['path']);original=Path(entry['source'])
    if exported.is_absolute() or original.is_absolute() or '..' in exported.parts or '..' in original.parts:
        raise ValueError('Unsafe manifest path')
    data=(root/exported).read_bytes()
    if hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Source checksum mismatch')
    target=out/original
    if not target.resolve().is_relative_to(out):raise ValueError('Workspace path escaped')
    if target.exists() and target.read_bytes()!=data:raise ValueError('Refuse to overwrite modified file: '+str(original))
    planned[target]=data
for target,data in planned.items():
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():target.write_bytes(data)
print(json.dumps({'status':'PASS','files':len(planned),'workspace':str(out)}))
