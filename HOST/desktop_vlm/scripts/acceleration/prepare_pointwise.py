"""Build real-model INT8 MAC fixtures and a single-convolution smoke experiment.

Existing images are engineering fixtures, NOT a representative calibration or
independent accuracy set. No board access; model and input sources are immutable.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def symmetric_scale(array, axis=None):
    peak = np.max(np.abs(array.astype(np.float64)), axis=axis)
    return np.where(peak > 0, peak / 127.0, 1.0)


def quantize(array, scale):
    if not np.all(np.isfinite(array)) or not np.all(np.isfinite(scale)):
        raise ValueError('non-finite quantization input')
    if np.any(np.asarray(scale) <= 0):
        raise ValueError('scale must be positive')
    return np.clip(np.rint(array.astype(np.float64) / scale), -127, 127).astype(np.int8)


def error(actual, expected):
    a, b = actual.astype(np.float64).ravel(), expected.astype(np.float64).ravel()
    mse = float(np.mean((a - b) ** 2))
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return {'max_abs': float(np.max(np.abs(a-b))), 'rmse': math.sqrt(mse),
            'relative_l2': float(np.linalg.norm(a-b) / max(np.linalg.norm(b), 1e-30)),
            'cosine': float(np.dot(a, b) / norm) if norm else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', required=True)
    ap.add_argument('--expected-model-sha256', required=True)
    ap.add_argument('--node', required=True)
    ap.add_argument('--input', action='append', required=True,
                    help='Existing little-endian float32 NCHW [1,3,256,256]')
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    if sha(args.model) != args.expected_model_sha256:
        raise ValueError('model SHA mismatch')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    model = SymbolicShapeInference.infer_shapes(onnx.load(args.model), auto_merge=True)
    nodes = [n for n in model.graph.node if n.name == args.node]
    if len(nodes) != 1 or nodes[0].op_type != 'Conv':
        raise ValueError('requires one exact Conv node name')
    node = nodes[0]
    attrs = {a.name: onnx.helper.get_attribute_value(a) for a in node.attribute}
    init = {v.name: numpy_helper.to_array(v) for v in model.graph.initializer}
    w = init[node.input[1]]
    if (w.ndim != 4 or list(w.shape[2:]) != [1, 1] or attrs.get('group', 1) != 1
            or attrs.get('strides', [1, 1]) != [1, 1]
            or any(attrs.get('pads', [0, 0, 0, 0]))
            or attrs.get('auto_pad', b'NOTSET') not in (b'NOTSET', b'VALID')):
        raise ValueError('only unpadded stride-1 group-1 pointwise Conv supported')
    b = init[node.input[2]] if len(node.input) == 3 else np.zeros(w.shape[0], np.float32)
    shape = {v.name: v for v in list(model.graph.value_info) + list(model.graph.output)}
    del model.graph.output[:]
    model.graph.output.extend([shape[node.input[0]], shape[node.output[0]], shape['features']])
    onnx.checker.check_model(model)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    ort.disable_telemetry_events()
    session = ort.InferenceSession(model.SerializeToString(), options, providers=['CPUExecutionProvider'])
    records = []
    for path in args.input:
        x = np.fromfile(path, '<f4')
        if x.size != 3*256*256 or not np.all(np.isfinite(x)):
            raise ValueError('invalid input tensor: ' + path)
        x = x.reshape(1, 3, 256, 256)
        activation, expected, features = session.run(None, {'image': x})
        records.append((path, x, activation, expected, features))
    # Engineering-only range estimate. These same inputs are reused below, so
    # results explicitly cannot be interpreted as held-out accuracy validation.
    act_scale = float(symmetric_scale(np.array([np.max(np.abs(r[2])) for r in records])))
    matrix_b = w[:, :, 0, 0].T.copy()  # [K,N]
    weight_scale = symmetric_scale(matrix_b, axis=0)  # per output channel
    qb = quantize(matrix_b, weight_scale)
    qb.tofile(out/'weights-kn.i8')
    np.asarray(weight_scale, '<f8').tofile(out/'weight-scales.f64')
    np.asarray(b, '<f4').tofile(out/'bias.f32')
    # Inject only this Conv output; other branches still compute from image.
    # This is a diagnostic replacement, not an efficient partitioned runner.
    source = onnx.load(args.model)
    source = SymbolicShapeInference.infer_shapes(source, auto_merge=True)
    patched = onnx.utils.Extractor(source).extract_model(['image', node.output[0]], ['features'])
    onnx.checker.check_model(patched)
    suffix = ort.InferenceSession(patched.SerializeToString(), options, providers=['CPUExecutionProvider'])
    results = []
    for idx, (path, x, activation, expected, features) in enumerate(records):
        _, k, h, width = activation.shape
        n = qb.shape[1]
        a = activation[0].transpose(1, 2, 0).reshape(-1, k).copy()
        qa = quantize(a, act_scale)
        accum64 = qa.astype(np.int64) @ qb.astype(np.int64)
        if np.any(accum64 > np.iinfo(np.int32).max) or np.any(accum64 < np.iinfo(np.int32).min):
            raise OverflowError('INT32 accumulator overflow')
        actual = ((accum64.astype(np.float64) * (act_scale*weight_scale)) + b)
        actual = actual.reshape(h, width, n).transpose(2, 0, 1)[None].astype(np.float32)
        mixed_features = suffix.run(['features'], {'image': x, node.output[0]: actual})[0]
        np.asarray(mixed_features, '<f4').tofile(out/('sample-%02d-mixed-features.f32'%idx))
        # Full K, first 16 spatial positions, first 32 output channels.
        ta, tb = qa[:16].copy(), qb[:, :32].copy()
        tc = (ta.astype(np.int64) @ tb.astype(np.int64)).astype('<i4')
        for mi in range(ta.shape[0]):
            for ni in range(tb.shape[1]):
                scalar = sum(int(ta[mi, ki])*int(tb[ki, ni]) for ki in range(k))
                if scalar != int(tc[mi, ni]):
                    raise AssertionError('independent integer reference mismatch')
        stem = 'sample-%02d'%idx
        ta.tofile(out/(stem+'-a-mk.i8'))
        tb.tofile(out/(stem+'-b-kn.i8'))
        tc.tofile(out/(stem+'-c-mn.i32'))
        # Decimal text is directly usable in a C/C++ HLS testbench.
        np.savetxt(out/(stem+'-a.txt'), ta.reshape(-1), fmt='%d')
        np.savetxt(out/(stem+'-b.txt'), tb.reshape(-1), fmt='%d')
        np.savetxt(out/(stem+'-c.txt'), tc.reshape(-1), fmt='%d')
        results.append({'input':str(Path(path).resolve()), 'input_sha256':sha(path),
                        'activation_shape':list(activation.shape),
                        'weight_shape':list(w.shape), 'tile_mnk':[ta.shape[0],tb.shape[1],k],
                        'conv_error':error(actual,expected),
                        'full_feature_error':error(mixed_features,features),
                        'scalar_integer_checks':int(tc.size),
                        'activation_clipped':int(np.count_nonzero(np.abs(a)>127*act_scale))})
    report = {'status':'ENGINEERING_SMOKE_ONLY', 'model_sha256':sha(args.model),
              'node':args.node, 'calibration':'range estimated from same smoke inputs; NOT held-out accuracy',
              'contract':{'a':'signed int8 row-major M,K','b':'signed int8 row-major K,N',
                          'c':'signed little-endian int32 row-major M,N; sum(A*B); no bias or requant',
                          'zero_points':0,'quant_range':[-127,127], 'rounding':'nearest ties to even',
                          'activation_scale':act_scale,'weight_scale':'per output channel float64',
                          'bias':'float32 applied after dequantization in smoke experiment'},
              'results':results, 'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)}
                                         for p in out.iterdir() if p.is_file()}}
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['results'],ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
