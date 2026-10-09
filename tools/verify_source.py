"""Verify every exported source against its recorded SHA256; no board access."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original-root', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    seen = set()
    counts = {}
    for entry in manifest['files']:
        relative = Path(entry['path'])
        source_relative = Path(entry['source'])
        if relative.is_absolute() or '..' in relative.parts or source_relative.is_absolute() or '..' in source_relative.parts:
            raise ValueError('Unsafe manifest path')
        if entry['path'] in seen:
            raise ValueError('Duplicate exported path: ' + entry['path'])
        seen.add(entry['path'])
        data = (root / relative).read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Source checksum mismatch: ' + entry['path'])
        if args.original_root is not None:
            original = (args.original_root / source_relative).read_bytes()
            if original != data:
                raise ValueError('Source differs from original: ' + entry['path'])
        side = relative.parts[0]
        counts[side] = counts.get(side, 0) + 1
    print(json.dumps({'status': 'PASS', 'files': len(seen), 'counts': counts,
                      'originals_compared': args.original_root is not None}, ensure_ascii=False))


if __name__ == '__main__':
    main()
