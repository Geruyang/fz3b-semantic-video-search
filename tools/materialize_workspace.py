"""Recreate original relative paths in a separate workspace; never overwrite changes."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError('Output must be a separate workspace, not the repository or its parent')
    manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    planned = {}
    for entry in manifest['files']:
        relative = Path(entry['source'])
        exported = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or exported.is_absolute() or '..' in exported.parts:
            raise ValueError('Unsafe manifest path')
        data = (root / exported).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Checksum mismatch: ' + entry['path'])
        target = output / relative
        if not target.resolve().is_relative_to(output):
            raise ValueError('Workspace path escaped through a symlink')
        if target in planned and planned[target] != data:
            raise ValueError('Conflicting shared source: ' + str(relative))
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Refuse to overwrite modified file: ' + str(relative))
        planned[target] = data
    for target, data in planned.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
    sample = output / 'vision_app/client-config.example.json'
    if not sample.exists():
        sample.write_bytes((root / 'HOST/vision_app/client-config.example.json').read_bytes())
    print(json.dumps({'status': 'PASS', 'workspace': str(output), 'files': len(planned)}))


if __name__ == '__main__':
    main()
