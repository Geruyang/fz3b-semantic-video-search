"""Freeze small dynamic-DW jobs from verified model data and scalar edge cases.

This prepares data only; it neither accesses hardware nor certifies a board run.
Each request is exactly 49 weight bytes followed by 1024 pixel bytes.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


TRUSTED_MANIFEST = '68f6df810f1e39892adfba2a20768651e6a1cec6b8e8d4e09ac1ee3930371576'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def signed(data):
    return [x if x < 128 else x - 256 for x in data]


def scalar_dw(weights, pixels):
    if len(weights) != 49 or len(pixels) != 1024:
        raise ValueError('fixed 7x7 weights and 32x32 pixels required')
    return [sum(weights[ky * 7 + kx] * pixels[iy * 32 + ix]
                for ky in range(7) for kx in range(7)
                for iy, ix in [(y + ky - 3, x + kx - 3)]
                if 0 <= iy < 32 and 0 <= ix < 32)
            for y in range(32) for x in range(32)]


def prepare(source, output):
    source, output = Path(source), Path(output)
    raw_manifest = (source / 'manifest.json').read_bytes()
    if digest(raw_manifest) != TRUSTED_MANIFEST:
        raise ValueError('source manifest differs from independently reviewed reference')
    manifest = json.loads(raw_manifest)
    files = {}
    names = ['weights-chw.i8']
    for image in range(3):
        names.extend(['sample-%02d-input-chw.i8' % image,
                      'sample-%02d-output-chw.i32' % image])
    for name in names:
        data = (source / name).read_bytes()
        entry = manifest['files'][name]
        if len(data) != entry['bytes'] or digest(data) != entry['sha256']:
            raise ValueError('source data identity mismatch: ' + name)
        files[name] = data
    if len(files['weights-chw.i8']) != 128 * 49:
        raise ValueError('unexpected channel count')
    jobs = []
    for image in range(3):
        for channel in range(2):
            weights = files['weights-chw.i8'][channel * 49:(channel + 1) * 49]
            pixels = files['sample-%02d-input-chw.i8' % image][channel * 1024:(channel + 1) * 1024]
            expected = files['sample-%02d-output-chw.i32' % image][channel * 4096:(channel + 1) * 4096]
            calculated = scalar_dw(signed(weights), signed(pixels))
            if expected != struct.pack('<1024i', *calculated):
                raise ValueError('independent scalar mismatch')
            jobs.append(('sample-%02d-channel-%03d' % (image, channel), weights, pixels, expected))
    for name, w, p in [('negative-times-negative', -128, -128),
                       ('negative-times-positive', -128, 127),
                       ('positive-times-positive', 127, 127), ('zero', 0, -128)]:
        weights, pixels = bytes([w & 255]) * 49, bytes([p & 255]) * 1024
        expected = struct.pack('<1024i', *scalar_dw([w] * 49, [p] * 1024))
        jobs.append((name, weights, pixels, expected))
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for number, (name, weights, pixels, expected) in enumerate(jobs, 1):
        reqname, outname = '%02d-%s.request' % (number, name), '%02d-%s.i32' % (number, name)
        request = weights + pixels
        (output / reqname).write_bytes(request)
        (output / outname).write_bytes(expected)
        records.append({'name': name, 'job_id_if_fresh': number,
                        'request': reqname, 'request_bytes': len(request), 'request_sha256': digest(request),
                        'golden': outname, 'golden_bytes': len(expected), 'golden_sha256': digest(expected)})
    result = {'status': 'PREPARED_NOT_BOARD_RESULT', 'schema': 'fz3b-dw-c2-jobs-v1',
              'source_manifest_sha256': TRUSTED_MANIFEST,
              'model_sha256': manifest['model_sha256'], 'node': manifest['node'],
              'request_layout': '49 signed INT8 weights followed by 1024 signed INT8 pixels, row-major',
              'response_layout': '1024 little-endian signed INT32 outputs, row-major',
              'reference': 'all 10240 outputs independently recomputed by bounds-checked scalar loops',
              'jobs': records}
    (output / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(json.dumps({'jobs': len(result['jobs']), 'source_sha256': TRUSTED_MANIFEST,
                      'manifest_sha256': digest((args.output / 'manifest.json').read_bytes())}))
