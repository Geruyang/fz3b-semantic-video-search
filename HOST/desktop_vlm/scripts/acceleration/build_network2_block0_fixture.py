"""Repack the board-verified block0 oracle for the new cascade datapath test."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from network2_stream_packet import build_packet, identity_header, pack_parameters


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output):
    if output.exists():
        raise ValueError('use a fresh output directory')
    root = Path(__file__).resolve().parents[3]
    base = root / 'artifacts/board-debug-20261004/acceleration/host'
    b = base / 'stage2-dw3-dw7-int16act-007'
    s = base / 'stage3-network20-int16-004'
    expected = {b: '68e2a29131ca0965783b00eea54049c313de669e1c758b738f4c530bb78cd282',
                s: '164fdff3ab1a09e0b6282f4281ed09e7846cb44ace36ddbdca86ab57237e94c7'}
    manifests = {}
    for directory, digest in expected.items():
        assert sha(directory / 'manifest.json') == digest
        manifests[directory] = json.loads((directory / 'manifest.json').read_text())
    def read(directory, name, dtype, shape):
        path = directory / name
        entry = manifests[directory]['files'][name]
        assert sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes']
        return np.fromfile(str(path), dtype=dtype).reshape(shape)
    pw = ['stage3-pw128-to-384', 'stage3-pw384-to-128']
    parameters = {
        'dw3_weights': read(b, 'dw3-weights-chw.i8', 'i1', (128, 9)),
        'dw7_weights': read(b, 'dw7-weights-chw.i8', 'i1', (128, 49)),
        'pw1_weights': read(s, pw[0] + '-weights-kn.i8', 'i1', (384, 128)),
        'pw2_weights': read(s, pw[1] + '-weights-kn.i8', 'i1', (128, 384)),
        'gelu': read(s, 'stage3-gelu-int16-lut.i16le', '<i2', (65536,)),
        'scale_multiplier': read(s, 'stage3-scale-add-multiplier.i32', '<i4', (128,)),
        'scale_shift': read(s, 'stage3-scale-add-shift.i32', '<i4', (128,)),
        'residual_multiplier': read(s, 'stage3-residual-multiplier.i32', '<i4', (1,)),
        'residual_shift': read(s, 'stage3-residual-shift.i32', '<i4', (1,)),
    }
    parameters['bias'] = np.concatenate([
        read(b, 'dw3-bias.i32', '<i4', (128,)), read(b, 'dw7-bias.i32', '<i4', (128,)),
        read(s, pw[0] + '-bias.i32', '<i4', (384,)), read(s, pw[1] + '-bias.i32', '<i4', (128,))])
    for field in ('multiplier', 'shift'):
        parameters[field] = np.concatenate([
            read(b, 'dw3-to-dw7-int16-requant-' + field + '.i32', '<i4', (128,)),
            read(b, 'dw7-to-stage3-int16-requant-' + field + '.i32', '<i4', (128,)),
            read(s, pw[0] + '-requant-' + field + '.i32', '<i4', (384,)),
            read(s, pw[1] + '-requant-' + field + '.i32', '<i4', (128,))])
    payload = pack_parameters(parameters)
    output.mkdir(parents=True)
    (output / 'block-00.params').write_bytes(payload)
    parameter_manifest = {
        'schema': 'network2-candidate-parameter-identity-v1',
        'scope': 'single block0 repacking regression; not twelve-block parameters or board test',
        'block_count': 1, 'mac_layout': [12, 16],
        'source_manifests': {directory.name: digest for directory, digest in expected.items()},
        'parameter_payload_sha256': hashlib.sha256(payload).hexdigest(),
        'parameter_payload_bytes': len(payload),
    }
    identity = output / 'parameter-manifest.json'
    identity.write_text(json.dumps(parameter_manifest, indent=2, sort_keys=True) + '\n')
    parameter_sha = sha(identity)
    (output / 'network2_parameter_identity.hpp').write_text(identity_header(1, parameter_sha))
    rows = []
    for index in range(3):
        name = 'image-%02d' % index
        activation = read(b, name + '-pre-dw3.i16', '<i2', (128, 32, 32)).tobytes()
        golden = read(s, name + '-stage3-single-output-packet.i16le', '<i2', (128, 32, 32)).tobytes()
        packet = output / (name + '.input.bin')
        answer = output / (name + '.output.bin')
        packet.write_bytes(build_packet([payload], activation, parameter_sha))
        answer.write_bytes(golden)
        rows.append({'image': name, 'input_sha256': sha(packet), 'input_bytes': packet.stat().st_size,
                     'output_sha256': sha(answer), 'output_bytes': answer.stat().st_size})
    manifest = {'status': 'OFFLINE_REPACKED_BOARD_VERIFIED_BLOCK0_FIXTURE',
                'parameter_manifest_sha256': parameter_sha, 'images': rows,
                'generator_sha256': sha(Path(__file__)),
                'serializer_sha256': sha(Path(__file__).with_name('network2_stream_packet.py'))}
    (output / 'fixture-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
