"""Independently compare downloaded DW output bytes and hardware job receipts."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(window, host, mode):
    actual = window / (mode + '-outputs')
    result = json.loads((actual / 'result.json').read_text())
    assert result['phase_pass'] and result['helper_closed_and_reaped']
    for name, item in result['files'].items():
        path = actual / name
        assert path.stat().st_size == item['bytes'] and digest(path) == item['sha256'], name
    rows = []
    if mode == 'smoke':
        reference = host / 'dw-jobs-001'
        manifest = json.loads((reference / 'manifest.json').read_text())
        assert len(result['results']) == len(manifest['jobs']) == 10
        for i, (job, receipt) in enumerate(zip(manifest['jobs'], result['results']), 1):
            output = actual / ('job-%02d-output.i32' % i)
            golden = reference / job['golden']
            assert digest(golden) == job['golden_sha256']
            assert output.read_bytes() == golden.read_bytes()
            assert receipt['job_id'] == receipt['request_id'] == i
            assert (receipt['weight_count'], receipt['pixel_count'], receipt['output_count']) == (49, 1024, 1024)
            assert receipt['cycles'] == 2493
            rows.append({'job_id': i, 'integer_values': 1024, 'sha256': digest(output)})
    else:
        reference = host / 'dw-ps-prefix-oracle-002'
        manifest = json.loads((reference / 'manifest.json').read_text())
        assert digest(reference / 'manifest.json') == 'dd75f3727699f60aa70e1ac84d6ef38f4416168b4ac4f8081c16ce21101e67c9'
        assert result['CPU_children_closed_and_reaped'] and len(result['cases']) == 3
        for i, case in enumerate(result['cases']):
            stem = 'image-%02d-' % i
            for output, golden in [('dw-output.i32', 'dw-oracle.i32'),
                                   ('quant.i8', 'ps-prefix-quant.i8'),
                                   ('dequant.f32', 'dw-dequant.f32')]:
                ref = reference / (stem + golden)
                assert digest(ref) == manifest['files'][ref.name]['sha256']
                assert (actual / (stem + output)).read_bytes() == ref.read_bytes(), (i, output)
            assert digest(actual / (stem + 'prefix.f32')) == manifest['cases'][i]['actual_ps_prefix_sha256']
            observed = struct.unpack('<512f', (actual / (stem + 'features.f32')).read_bytes())
            expected = struct.unpack('<512f', (reference / (stem + 'mixed-features.f32')).read_bytes())
            assert all(math.isfinite(x) for x in observed)
            error = max(abs(a-b) for a,b in zip(observed, expected))
            assert error < 1e-5
            receipts = case['job_receipts']
            assert [x['job_id'] for x in receipts] == list(range(11 + 128*i, 139 + 128*i))
            assert [x['request_id'] for x in receipts] == list(range(1 + 128*i, 129 + 128*i))
            assert all((x['weight_count'], x['pixel_count'], x['output_count'], x['cycles']) ==
                       (49, 1024, 1024, 2493) for x in receipts)
            rows.append({'image': i, 'integer_values': 131072, 'feature_max_abs': error,
                         'job_ids': [receipts[0]['job_id'], receipts[-1]['job_id']],
                         'cycles': sorted(set(x['cycles'] for x in receipts)),
                         'timing_ms': case['timing_ms']})
    return {'status': 'PASS_ACTUAL_PS_PL_' + mode.upper(), 'cases': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('window', type=Path)
    parser.add_argument('host', type=Path)
    parser.add_argument('mode', choices=['smoke', 'full'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.window, args.host, args.mode)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report))
