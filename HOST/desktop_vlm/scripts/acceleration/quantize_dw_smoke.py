"""Replace the validated DW7 node using all 128 channels, on the host only.

Reuses the frozen engineering-smoke scale; no new calibration or accuracy claim.
The FPGA contract is raw INT32. Dequantization and bias here remain float32.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference

from prepare_pointwise import error, quantize, sha, symmetric_scale


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--fixture-manifest-sha256', required=True)
    parser.add_argument('--input', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, choices=(1, 2, 4), default=2)
    args = parser.parse_args()
    manifest_path = args.fixture / 'manifest.json'
    if sha(manifest_path) != args.fixture_manifest_sha256:
        raise ValueError('fixture identity mismatch')
    fixture = json.loads(manifest_path.read_text(encoding='utf-8'))
    if sha(args.model) != fixture['model_sha256']:
        raise ValueError('model identity mismatch')
    if len(args.input) != 3 or len(fixture['results']) != 3:
        raise ValueError('requires the three frozen smoke inputs')
    for name, record in fixture['files'].items():
        path = args.fixture / name
        if path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
            raise ValueError('fixture file identity mismatch: ' + name)
    model = SymbolicShapeInference.infer_shapes(onnx.load(args.model), auto_merge=True)
    nodes = [n for n in model.graph.node if n.name == fixture['node']]
    if len(nodes) != 1 or nodes[0].op_type != 'Conv':
        raise ValueError('exact DW Conv missing')
    node = nodes[0]
    attrs = {a.name: onnx.helper.get_attribute_value(a) for a in node.attribute}
    if (attrs.get('group') != 128 or attrs.get('kernel_shape') != [7, 7]
            or attrs.get('pads') != [3, 3, 3, 3]
            or attrs.get('strides', [1, 1]) != [1, 1]
            or attrs.get('dilations', [1, 1]) != [1, 1]
            or attrs.get('auto_pad', b'NOTSET') != b'NOTSET'):
        raise ValueError('unsupported DW operator')
    initial = {x.name: numpy_helper.to_array(x) for x in model.graph.initializer}
    weights = initial[node.input[1]]
    bias = initial[node.input[2]] if len(node.input) == 3 else np.zeros(128, np.float32)
    if weights.shape != (128, 1, 7, 7) or bias.shape != (128,):
        raise ValueError('unsupported weights/bias shape')
    sx = fixture['contract']['activation_scale']
    sw = symmetric_scale(weights[:, 0], axis=(1, 2))
    qw = quantize(weights[:, 0], sw[:, None, None])
    if qw[:2].tobytes() != (args.fixture / 'weights-chw.i8').read_bytes():
        raise ValueError('weights differ from board-validated fixture')

    options = ort.SessionOptions()
    options.intra_op_num_threads = args.threads
    options.inter_op_num_threads = 1
    ort.disable_telemetry_events()
    def session(graph):
        return ort.InferenceSession(graph.SerializeToString(), options, providers=['CPUExecutionProvider'])
    original = session(model)
    suffix_graph = onnx.utils.Extractor(model).extract_model(['image', node.output[0]], ['features'])
    onnx.checker.check_model(suffix_graph)
    suffix = session(suffix_graph)
    info = {v.name: v for v in list(model.graph.value_info) + list(model.graph.output)}
    del model.graph.output[:]
    model.graph.output.extend([info[node.input[0]], info[node.output[0]]])
    probes = session(model)
    args.output.mkdir(parents=True, exist_ok=False)
    qw.tofile(args.output / 'weights-chw.i8')
    sw.astype('<f8').tofile(args.output / 'weight-scales.f64')
    bias.astype('<f4').tofile(args.output / 'bias.f32')
    results = []
    for index, path in enumerate(args.input):
        if sha(path) != fixture['results'][index]['input_sha256']:
            raise ValueError('input identity mismatch')
        image = np.fromfile(path, '<f4').reshape(1, 3, 256, 256)
        if not np.isfinite(image).all():
            raise ValueError('nonfinite image')
        activation, reference = probes.run(None, {'image': image})
        if activation.shape != (1, 128, 32, 32):
            raise ValueError('unsupported activation shape')
        qa = quantize(activation[0], sx)
        stem = 'sample-%02d' % index
        if qa[:2].tobytes() != (args.fixture / (stem + '-input-chw.i8')).read_bytes():
            raise ValueError('inputs differ from board-validated fixture')
        windows = np.lib.stride_tricks.sliding_window_view(
            np.pad(qa, ((0, 0), (3, 3), (3, 3))), (7, 7), axis=(1, 2))
        accum = np.einsum('chyij,cij->chy', windows.astype(np.int64), qw.astype(np.int64), optimize=True)
        board_golden = np.fromfile(args.fixture / (stem + '-output-chw.i32'), '<i4').reshape(2, 32, 32)
        if not np.array_equal(accum[:2], board_golden):
            raise ValueError('outputs differ from board-validated fixture')
        # Bounds-checked scalar cross-check across all channels and padded edges.
        scalar_checks = 0
        for ch in range(128):
            for y, x in ((0, 0), (0, 31), (31, 0), (31, 31), (16, 16)):
                total = sum(int(qa[ch, iy, ix]) * int(qw[ch, ky, kx])
                            for ky in range(7) for kx in range(7)
                            for iy, ix in [(y + ky - 3, x + kx - 3)]
                            if 0 <= iy < 32 and 0 <= ix < 32)
                if total != accum[ch, y, x]:
                    raise AssertionError('independent scalar mismatch')
                scalar_checks += 1
        if np.any(accum < -(1 << 31)) or np.any(accum > (1 << 31) - 1):
            raise OverflowError('INT32 overflow')
        qa.tofile(args.output / (stem + '-input-chw.i8'))
        accum.astype('<i4').tofile(args.output / (stem + '-output-chw.i32'))
        reconstructed = (accum * (sx * sw[:, None, None]) + bias[:, None, None])[None].astype(np.float32)
        baseline = original.run(['features'], {'image': image})[0]
        passthrough = suffix.run(['features'], {'image': image, node.output[0]: reference})[0]
        if not np.array_equal(baseline, passthrough):
            raise AssertionError('FP32 graph replacement baseline differs')
        mixed = suffix.run(['features'], {'image': image, node.output[0]: reconstructed})[0]
        mixed.astype('<f4').tofile(args.output / (stem + '-mixed-features.f32'))
        results.append({'input_sha256': sha(path), 'full_channels': 128,
                        'board_golden_overlap_values': 2048, 'scalar_checks': scalar_checks,
                        'fp32_passthrough_max_abs': 0, 'conv_error': error(reconstructed, reference),
                        'full_feature_error': error(mixed, baseline)})
    report = {'status': 'HOST_ENGINEERING_SMOKE_NOT_BOARD_MODEL_OR_ACCURACY',
              'model_sha256': fixture['model_sha256'], 'node': fixture['node'],
              'fixture_manifest_sha256': args.fixture_manifest_sha256,
              'execution': {'ort_threads': args.threads, 'ort_version': ort.__version__,
                            'onnx_version': onnx.__version__, 'script_sha256': sha(__file__)},
              'tensor_shape_chw': [128, 32, 32], 'weight_shape_ckk': [128, 7, 7],
              'activation_scale': sx,
              'contract': 'raw INT32 DW; per-channel dequantization plus FP32 bias on host',
              'scale_source': 'frozen same-three-image engineering fixture; no held-out samples',
              'results': results, 'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                                           for p in args.output.iterdir() if p.is_file()}}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
