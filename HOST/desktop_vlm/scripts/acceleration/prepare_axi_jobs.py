"""Prepare bounded real-model dot jobs from the frozen pointwise fixture.

This is register-path correctness data, not model accuracy or acceleration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(directory, expected_manifest_sha):
    directory = Path(directory)
    raw = (directory / 'manifest.json').read_bytes()
    if digest(raw) != expected_manifest_sha:
        raise ValueError('fixture manifest identity mismatch')
    manifest = json.loads(raw)
    if len(manifest['results']) != 3:
        raise ValueError('expected three frozen model samples')
    jobs, sources = [], {}

    def read(name, size):
        data = (directory / name).read_bytes()
        record = manifest['files'][name]
        if len(data) != size or record['bytes'] != size or digest(data) != record['sha256']:
            raise ValueError('fixture file identity mismatch: ' + name)
        sources[name] = record
        return data

    for sample, result in enumerate(manifest['results']):
        if result['tile_mnk'] != [16, 32, 64]:
            raise ValueError('unexpected matrix shape')
        stem = 'sample-%02d' % sample
        a = struct.unpack('<1024b', read(stem + '-a-mk.i8', 1024))
        b = struct.unpack('<2048b', read(stem + '-b-kn.i8', 2048))
        c = struct.unpack('<512i', read(stem + '-c-mn.i32', 2048))
        for row, col in ((0, 0), (0, 31), (15, 0), (15, 31)):
            pairs = [[a[row * 64 + k], b[k * 32 + col]] for k in range(64)]
            expected = sum(x * y for x, y in pairs)
            if expected != c[row * 32 + col]:
                raise ValueError('scalar/matrix reference mismatch')
            jobs.append({'name': '%s-m%d-n%d' % (stem, row, col),
                         'source': 'real-model-pointwise', 'pairs': pairs,
                         'expected': expected})

    for name, pairs in (
        ('length-one-negative', [[-128, 127]]),
        ('length-one-zero', [[0, -128]]),
        ('length-512-positive-max', [[-128, -128]] * 512),
        ('length-512-negative-min', [[-128, 127]] * 512),
        ('length-511-alternating', [[127, (-128 if i % 2 else 127)] for i in range(511)]),
        ('length-512-zero', [[0, 127]] * 512),
    ):
        jobs.append({'name': name, 'source': 'synthetic-boundary',
                     'pairs': pairs, 'expected': sum(x * y for x, y in pairs)})
    return {'schema': 'fz3b-axi-dot-jobs-v1', 'status': 'PREPARED_NOT_BOARD_RESULT',
            'purpose': 'bounded register transport and signed INT8/INT32 correctness',
            'fixture_manifest_sha256': expected_manifest_sha,
            'model_sha256': manifest['model_sha256'], 'node': manifest['node'],
            'source_files': sources, 'job_count': len(jobs), 'jobs': jobs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture', type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.fixture, args.manifest_sha256)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'jobs': result['job_count'], 'sha256': digest(args.output.read_bytes())}))
