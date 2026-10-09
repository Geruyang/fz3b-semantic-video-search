"""Repack a pinned 12-block integer oracle for offline HLS validation.

This is a file-integrity and serialization step, not an independent numerical
checker or permission to deploy the resulting identity on a board.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from network2_stream_packet import build_packet, identity_header, pack_parameters


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_file(root, entry):
    path = (root / entry['path']).resolve()
    path.relative_to(root.resolve())
    if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
        raise ValueError('oracle file differs: ' + str(path))
    return path


def run(oracle, expected_sha, output):
    oracle = oracle.resolve()
    path = oracle / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('pinned oracle manifest differs')
    source = json.loads(path.read_text(encoding='utf-8'))
    if (source.get('artifact_completeness') != 'FULL_CASCADE' or
            source.get('block_count') != 12 or source.get('provenance', {}).get('mode') != 'BOARD_PS'):
        raise ValueError('complete board-PS-calibrated 12-block oracle required')
    blocks = source['blocks']
    results = source['results']
    if [block['index'] for block in blocks] != list(range(12)):
        raise ValueError('ordered blocks 0..11 required')
    if [item['sample_id'] for item in results] != ['image-00', 'image-01', 'image-02']:
        raise ValueError('ordered three-image fixture required')
    names = {'dw3_weights': 'dw3_weights', 'dw7_weights': 'dw7_weights',
             'pw1_weights': 'pw1_weights', 'pw2_weights': 'pw2_weights',
             'bias': 'bias_i32', 'multiplier': 'multiplier_i32', 'shift': 'shift_i32',
             'gelu': 'gelu_lut', 'scale_multiplier': 'scale_multiplier_i32',
             'scale_shift': 'scale_shift_i32', 'residual_multiplier': 'residual_multiplier_i32',
             'residual_shift': 'residual_shift_i32'}
    payloads = []
    for block in blocks:
        subpath = verified_file(oracle, block['parameter_manifest'])
        submanifest = json.loads(subpath.read_text(encoding='utf-8'))
        if submanifest['block_index'] != block['index']:
            raise ValueError('submanifest index differs')
        arrays = {}
        for wire_name, stored_name in names.items():
            entry = submanifest['parameters'][stored_name]
            arrays[wire_name] = np.fromfile(str(verified_file(oracle, entry)),
                                             dtype=entry['dtype']).reshape(entry['shape'])
        payloads.append(pack_parameters(arrays))
    images = []
    for result in results:
        activation = verified_file(oracle, result['qinput_file']).read_bytes()
        expected = verified_file(oracle, result['final_add_file']).read_bytes()
        if len(activation) != 262144 or len(expected) != 262144:
            raise ValueError('activation/output contract length differs')
        images.append((result['sample_id'], activation, expected))
    output.mkdir(parents=True, exist_ok=False)
    parameter_manifest = {
        'schema': 'network2-candidate-parameter-identity-v1',
        'scope': '12-block offline HLS candidate; numerical review and board deployment gates are separate',
        'block_count': 12, 'mac_layout': [12, 16],
        'oracle_manifest_sha256': expected_sha,
        'blocks': [{'index': index, 'bytes': len(payload),
                    'sha256': hashlib.sha256(payload).hexdigest()}
                   for index, payload in enumerate(payloads)]}
    for index, payload in enumerate(payloads):
        (output / ('block-%02d.params' % index)).write_bytes(payload)
    identity = output / 'parameter-manifest.json'
    identity.write_text(json.dumps(parameter_manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    parameter_sha = sha(identity)
    (output / 'network2_parameter_identity.hpp').write_text(identity_header(12, parameter_sha), encoding='utf-8')
    rows = []
    for name, activation, expected in images:
        packet = output / (name + '.input.bin')
        answer = output / (name + '.output.bin')
        packet.write_bytes(build_packet(payloads, activation, parameter_sha))
        answer.write_bytes(expected)
        rows.append({'image': name, 'input_bytes': packet.stat().st_size, 'input_sha256': sha(packet),
                     'output_bytes': answer.stat().st_size, 'output_sha256': sha(answer)})
    report = {'status': 'OFFLINE_REPACKED_TWELVE_BLOCK_ORACLE_NOT_BOARD_VALIDATED',
              'parameter_manifest_sha256': parameter_sha, 'oracle_manifest_sha256': expected_sha,
              'images': rows, 'generator_sha256': sha(Path(__file__)),
              'serializer_sha256': sha(Path(__file__).with_name('network2_stream_packet.py'))}
    (output / 'fixture-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle', type=Path, required=True)
    parser.add_argument('--oracle-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.oracle, args.oracle_sha256, args.output), indent=2))
