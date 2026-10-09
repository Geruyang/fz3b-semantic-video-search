"""Generate an independent DW oracle from actual PS prefix outputs.

Small host CPU calculation only. This does not access the board or certify PL.
The numerical source manifest and CPU split are independently pinned.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort

QUANT_SHA = '68f6df810f1e39892adfba2a20768651e6a1cec6b8e8d4e09ac1ee3930371576'
SPLIT_SHA = 'ab19a87c8fac6661611f6e35bd2b31fc59e2be4b133df7a663611c238b2bd8c4'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_manifest(directory, expected):
    path = directory / 'manifest.json'
    if sha(path) != expected:
        raise ValueError('manifest identity mismatch: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'))


def verify_file(path, entry):
    if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
        raise ValueError('data identity mismatch: ' + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--split', type=Path, required=True)
    parser.add_argument('--prefix', type=Path, action='append', required=True)
    parser.add_argument('--collection-receipt', type=Path, required=True)
    parser.add_argument('--ps-prefix-threads', type=int, choices=(1, 2, 4), required=True,
                        help='collector setting established by the linked collection evidence')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if len(args.prefix) != 3:
        raise ValueError('three actual PS prefix outputs required, image order 00/01/02')
    quant = load_manifest(args.reference, QUANT_SHA)
    split = load_manifest(args.split, SPLIT_SHA)
    for name, entry in quant['files'].items():
        if Path(name).name != name:
            raise ValueError('unexpected reference filename')
        verify_file(args.reference / name, entry)
    stages = {x['stage']: x for x in split['stages']}
    verify_file(args.split / 'suffix.onnx', stages['suffix'])
    sx = quant['activation_scale']
    if not np.isfinite(sx) or sx <= 0:
        raise ValueError('invalid activation scale')
    weights = np.fromfile(args.reference / 'weights-chw.i8', np.int8).reshape(128, 7, 7).astype(np.int64)
    scales = np.fromfile(args.reference / 'weight-scales.f64', '<f8').reshape(128, 1, 1)
    bias = np.fromfile(args.reference / 'bias.f32', '<f4').reshape(128, 1, 1)
    if not np.isfinite(scales).all() or np.any(scales <= 0) or not np.isfinite(bias).all():
        raise ValueError('invalid dequantization constants')
    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
    session = ort.InferenceSession(str(args.split / 'suffix.onnx'), options,
                                  providers=['CPUExecutionProvider'])
    suffix_inputs = [x['name'] for x in stages['suffix']['inputs']]
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for image, path in enumerate(args.prefix):
        if path.stat().st_size != 128 * 32 * 32 * 4:
            raise ValueError('unexpected PS prefix size')
        actual = np.fromfile(path, '<f4').reshape(1, 128, 32, 32)
        if not np.isfinite(actual).all():
            raise ValueError('nonfinite PS prefix')
        pixels = np.clip(np.rint(actual[0].astype(np.float64) / sx), -127, 127).astype(np.int8)
        frozen = np.fromfile(args.reference / ('sample-%02d-input-chw.i8' % image), np.int8).reshape(pixels.shape)
        padded = np.pad(pixels.astype(np.int64), ((0, 0), (3, 3), (3, 3)))
        # Independent shifted-image accumulation (no sliding-window/einsum).
        accum = np.zeros((128, 32, 32), dtype=np.int64)
        for ky in range(7):
            for kx in range(7):
                accum += padded[:, ky:ky + 32, kx:kx + 32] * weights[:, ky, kx, None, None]
        if np.any(accum < -(1 << 31)) or np.any(accum > (1 << 31) - 1):
            raise OverflowError('DW accumulation out of signed32 range')
        changed = int(np.count_nonzero(pixels != frozen))
        original = np.fromfile(args.reference / ('sample-%02d-output-chw.i32' % image), '<i4').reshape(accum.shape)
        if changed == 0 and not np.array_equal(accum, original):
            raise AssertionError('independent integer oracle differs for identical input')
        dequant = (accum * (sx * scales) + bias)[None].astype(np.float32)
        feature = session.run(['features'], {suffix_inputs[0]: dequant, suffix_inputs[1]: actual})[0]
        if feature.shape != (1, 512) or not np.isfinite(feature).all():
            raise ValueError('invalid suffix reference feature')
        stem = 'image-%02d' % image
        pixels.tofile(args.output / (stem + '-ps-prefix-quant.i8'))
        accum.astype('<i4').tofile(args.output / (stem + '-dw-oracle.i32'))
        dequant.astype('<f4').tofile(args.output / (stem + '-dw-dequant.f32'))
        feature.astype('<f4').tofile(args.output / (stem + '-mixed-features.f32'))
        rows.append({'image': image, 'actual_ps_prefix_sha256': sha(path),
                     'quantized_pixels_different_from_host': changed,
                     'integer_outputs_different_from_host': int(np.count_nonzero(accum != original)),
                     'integer_values': int(accum.size)})
    report = {'status': 'INDEPENDENT_HOST_REFERENCE_FOR_ACTUAL_PS_INPUT_NOT_PL_RESULT',
              'quant_manifest_sha256': QUANT_SHA, 'split_manifest_sha256': SPLIT_SHA,
              'host_suffix_ort_version': ort.__version__, 'host_suffix_threads': 2,
              'ps_prefix_threads_from_collector': args.ps_prefix_threads,
              'ps_prefix_collection_receipt_sha256': sha(args.collection_receipt),
              'cases': rows,
              'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                        for p in args.output.iterdir() if p.is_file()}}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
