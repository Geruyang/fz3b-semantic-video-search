"""Experimental integer oracle for the frozen V10 PS N1 bridge.

This module is deliberately separate from the production FP32 ORT runner. It
implements symmetric per-output-channel W8, per-tensor A16, and checked Acc32
Conv math, with float GELU between the two convolutions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import time

import numpy as np
import onnx
from onnx import numpy_helper


EXPECTED_MODEL_SHA256 = "768410c97149468880dc1fd3d1d2c79b4e7460b31ce861020e7216da81968529"
INT32_MAX = (1 << 31) - 1
A16_MAX = (1 << 15) - 1
W8_MAX = (1 << 7) - 1


@dataclass(frozen=True)
class Conv:
    name: str
    x_name: str
    y_name: str
    weight: np.ndarray
    bias: np.ndarray
    stride: tuple[int, int]
    pads: tuple[int, int, int, int]
    group: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _attributes(node):
    return {a.name: onnx.helper.get_attribute_value(a) for a in node.attribute}


def load_n1_contract(model_path: str | Path, *, require_frozen_hash: bool = True) -> tuple[Conv, Conv, dict]:
    """Read and validate the concrete two-Conv N1 graph and its tensor shapes."""
    path = Path(model_path)
    digest = sha256_file(path)
    if require_frozen_hash and digest != EXPECTED_MODEL_SHA256:
        raise ValueError(f"unexpected N1 model SHA256: {digest}")
    model = onnx.load(str(path), load_external_data=True)
    onnx.checker.check_model(model)
    initializers = {t.name: numpy_helper.to_array(t).copy() for t in model.graph.initializer}
    nodes = [n for n in model.graph.node if n.op_type == "Conv"]
    if len(nodes) != 2:
        raise ValueError(f"N1 contract requires exactly two Conv nodes, got {len(nodes)}")
    convs = []
    for node in nodes:
        if len(node.input) != 3 or node.input[1] not in initializers or node.input[2] not in initializers:
            raise ValueError(f"Conv parameters must be initializers: {node.name}")
        attr = _attributes(node)
        stride = tuple(int(v) for v in attr.get("strides", [1, 1]))
        pads = tuple(int(v) for v in attr.get("pads", [0, 0, 0, 0]))
        weight, bias = initializers[node.input[1]], initializers[node.input[2]]
        if weight.ndim != 4 or bias.shape != (weight.shape[0],):
            raise ValueError(f"unsupported Conv parameter shape at {node.name}")
        convs.append(Conv(node.name, node.input[0], node.output[0], weight, bias,
                          stride, pads, int(attr.get("group", 1))))
    value_shapes = {}
    for value in list(model.graph.input) + list(model.graph.output) + list(model.graph.value_info):
        tensor = value.type.tensor_type
        if tensor.HasField("shape"):
            value_shapes[value.name] = tuple(int(d.dim_value) for d in tensor.shape.dim)
    input_shape = value_shapes.get(model.graph.input[0].name)
    output_shape = value_shapes.get(model.graph.output[0].name)
    if input_shape != (1, 64, 64, 64) or output_shape != (1, 128, 32, 32):
        raise ValueError(f"frozen N1 boundary mismatch: {input_shape} -> {output_shape}")
    c0, c1 = convs
    if c0.weight.shape != (128, 1, 7, 7) or c0.group != 64 or c0.stride != (2, 2) or c0.pads != (3, 3, 3, 3):
        raise ValueError("first N1 Conv is not frozen DW7 stride2 multiplier2 contract")
    if c1.weight.shape != (128, 128, 1, 1) or c1.group != 1 or c1.stride != (1, 1):
        raise ValueError("second N1 Conv is not frozen PW1 contract")
    constants = {}
    for node in model.graph.node:
        if node.op_type == "Constant":
            for attr in node.attribute:
                if attr.name == "value":
                    constants[node.output[0]] = numpy_helper.to_array(attr.t).item()
    gelu_divisors = [float(v) for k, v in constants.items() if "/activation/Constant_output_0" in k]
    gelu_scales = [float(v) for k, v in constants.items() if "/activation/Constant_2_output_0" in k]
    if len(gelu_divisors) != 2 or any(abs(v - math.sqrt(2)) > 2e-6 for v in gelu_divisors):
        raise ValueError("N1 GELU Div constants differ from sqrt(2) contract")
    if len(gelu_scales) != 2 or any(abs(v - 0.5) > 1e-7 for v in gelu_scales):
        raise ValueError("N1 GELU multiplier differs from 0.5 contract")
    contract = {
        "model_sha256": digest,
        "nodes": [{"name": c.name, "input": c.x_name, "output": c.y_name,
                   "weight_shape": list(c.weight.shape), "stride": list(c.stride),
                   "pads": list(c.pads), "group": c.group} for c in convs],
        "input_shape": list(input_shape), "output_shape": list(output_shape),
        "integer": {"activation": "signed A16 symmetric per tensor", "weight": "signed W8 symmetric per output channel",
                    "accumulator": "signed Acc32, host oracle accumulated in int64 then range-checked",
                    "overflow_proof": "full storage domains A16[-32768,32767] x W8[-128,127]",
                    "rounding": "IEEE ties-to-even via numpy.rint", "gelu": "FP32 between Conv nodes"},
    }
    return convs[0], convs[1], contract


def activation_scale(samples) -> float:
    peak = max(float(np.max(np.abs(x))) for x in samples)
    if not math.isfinite(peak) or peak <= 0:
        raise ValueError("calibration activation must be finite and nonzero")
    return peak / A16_MAX


def quantize_a16(array: np.ndarray, scale: float) -> np.ndarray:
    if not math.isfinite(scale) or scale <= 0 or not np.isfinite(array).all():
        raise ValueError("invalid A16 input or scale")
    return np.clip(np.rint(array / scale), -A16_MAX, A16_MAX).astype(np.int16)


def quantize_w8_per_output(weight: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows = weight.reshape(weight.shape[0], -1).astype(np.float64)
    scales = np.max(np.abs(rows), axis=1) / W8_MAX
    scales[scales == 0] = 1.0
    quantized = np.clip(np.rint(rows / scales[:, None]), -W8_MAX, W8_MAX).astype(np.int8)
    return quantized.reshape(weight.shape), scales.astype(np.float32)


def accumulator_bound(reduction_terms: int, *, activation_abs: int = (1 << 15),
                      weight_abs: int = (1 << 7)) -> dict:
    if type(reduction_terms) is not int or reduction_terms <= 0:
        raise ValueError("reduction_terms must be a positive integer")
    bound = reduction_terms * activation_abs * weight_abs
    return {"reduction_terms": reduction_terms, "activation_abs_max": activation_abs,
            "weight_abs_max": weight_abs, "worst_case_abs": bound,
            "signed32_max": INT32_MAX, "fits_signed32": bound <= INT32_MAX}


def _conv_accumulate(x_q: np.ndarray, conv: Conv, w_q: np.ndarray) -> np.ndarray:
    if x_q.dtype != np.int16 or x_q.ndim != 4 or w_q.dtype != np.int8:
        raise ValueError("Conv oracle expects NCHW int16 activations and int8 weights")
    n, cin, height, width = x_q.shape
    cout, channels_per_group, kh, kw = w_q.shape
    if cin % conv.group or cout % conv.group or channels_per_group != cin // conv.group:
        raise ValueError("Conv group/input channel contract mismatch")
    sh, sw = conv.stride
    pt, pl, pb, pr = conv.pads
    padded = np.pad(x_q.astype(np.int64), ((0, 0), (0, 0), (pt, pb), (pl, pr)))
    oh = (padded.shape[2] - kh) // sh + 1
    ow = (padded.shape[3] - kw) // sw + 1
    out = np.zeros((n, cout, oh, ow), dtype=np.int64)
    outputs_per_group = cout // conv.group
    for oc in range(cout):
        group_index = oc // outputs_per_group
        input_start = group_index * channels_per_group
        for ky in range(kh):
            ys = slice(ky, ky + oh * sh, sh)
            for kx in range(kw):
                xs = slice(kx, kx + ow * sw, sw)
                # The innermost axis is the reduction channel for grouped PW Conv;
                # DW7 has a single reduction channel per output channel.
                products = padded[:, input_start:input_start + channels_per_group, ys, xs] * w_q[oc, :, ky, kx].astype(np.int64)[None, :, None, None]
                out[:, oc] += products.sum(axis=1, dtype=np.int64)
    actual_min, actual_max = int(out.min()), int(out.max())
    if actual_min < -(1 << 31) or actual_max > INT32_MAX:
        raise OverflowError(f"actual Acc32 overflow: [{actual_min}, {actual_max}]")
    return out


def _gelu_fp32(x: np.ndarray) -> np.ndarray:
    x32 = np.asarray(x, dtype=np.float32)
    erf = np.frompyfunc(math.erf, 1, 1)(x32.astype(np.float64) / np.float64(math.sqrt(2))).astype(np.float32)
    return (np.float32(0.5) * x32 * (np.float32(1.0) + erf)).astype(np.float32)


def _conv_float_channels(x: np.ndarray, conv: Conv, output_channels) -> np.ndarray:
    """Compute selected output channels with float32 input and float32 weights."""
    x = np.asarray(x, dtype=np.float32)
    n, cin, height, width = x.shape
    cout, channels_per_group, kh, kw = conv.weight.shape
    if cin % conv.group or cout % conv.group or channels_per_group != cin // conv.group:
        raise ValueError("float fallback Conv group/input channel contract mismatch")
    sh, sw = conv.stride
    pt, pl, pb, pr = conv.pads
    padded = np.pad(x, ((0, 0), (0, 0), (pt, pb), (pl, pr)))
    oh = (padded.shape[2] - kh) // sh + 1
    ow = (padded.shape[3] - kw) // sw + 1
    result = np.empty((n, cout, oh, ow), dtype=np.float32)
    outputs_per_group = cout // conv.group
    for oc in output_channels:
        group_index = int(oc) // outputs_per_group
        input_start = group_index * channels_per_group
        acc = np.zeros((n, oh, ow), dtype=np.float32)
        for ic in range(channels_per_group):
            channel = input_start + ic
            for ky in range(kh):
                ys = slice(ky, ky + oh * sh, sh)
                for kx in range(kw):
                    xs = slice(kx, kx + ow * sw, sw)
                    acc += padded[:, channel, ys, xs] * np.float32(conv.weight[oc, ic, ky, kx])
        result[:, oc] = acc + np.float32(conv.bias[oc])
    return result


def _run_conv(x_q: np.ndarray, a_scale: float, conv: Conv, *,
              fp32_channels=()) -> tuple[np.ndarray, dict]:
    w_q, w_scales = quantize_w8_per_output(conv.weight)
    reduction = int(w_q.shape[1] * w_q.shape[2] * w_q.shape[3])
    proof = accumulator_bound(reduction)
    if not proof["fits_signed32"]:
        raise OverflowError(f"signed32 cannot cover the legal input range for {conv.name}")
    start = time.perf_counter()
    accum = _conv_accumulate(x_q, conv, w_q)
    mac_ms = (time.perf_counter() - start) * 1000
    # Conv bias is applied after the integer dot product, in real units.
    scale = (np.float32(a_scale) * w_scales).reshape(1, -1, 1, 1)
    y = accum.astype(np.float32) * scale + conv.bias.astype(np.float32).reshape(1, -1, 1, 1)
    selected = sorted({int(c) for c in fp32_channels})
    if any(c < 0 or c >= conv.weight.shape[0] for c in selected):
        raise ValueError(f"FP32 fallback channel out of range for {conv.name}")
    if selected:
        # Native PS fallback only has the A16 tensor contract. Reconstruct the
        # real-valued input from the exact same qA16 bytes and scale used by PL.
        source = x_q.astype(np.float32) * np.float32(a_scale)
        precise = _conv_float_channels(source, conv, selected)
        y[:, selected] = precise[:, selected]
    return y, {"name": conv.name, "reduction_terms": reduction, "bound": proof,
               "observed_accumulator_min": int(accum.min()), "observed_accumulator_max": int(accum.max()),
               "weight_scale_min": float(w_scales.min()), "weight_scale_max": float(w_scales.max()),
               "fp32_weight_output_channels": selected,
               "integer_conv_ms": mac_ms}


def calibrate_n1(convs: tuple[Conv, Conv], inputs: list[np.ndarray],
                 fp32_first_outputs: list[np.ndarray] | None = None) -> dict:
    if not inputs or any(x.shape != (1, 64, 64, 64) or not np.isfinite(x).all() for x in inputs):
        raise ValueError("calibration needs finite N1 inputs shaped [1,64,64,64]")
    in_scale = activation_scale(inputs)
    if fp32_first_outputs is not None:
        if len(fp32_first_outputs) != len(inputs) or any(y.shape != (1, 128, 32, 32) for y in fp32_first_outputs):
            raise ValueError("FP32 first-layer calibration outputs have a bad count or shape")
        after_first = fp32_first_outputs
    else:
        after_first = []
        for x in inputs:
            conv_y, _ = _run_conv(quantize_a16(x, in_scale), in_scale, convs[0])
            after_first.append(_gelu_fp32(conv_y))
    return {"input_a16_scale": in_scale, "pw_input_a16_scale": activation_scale(after_first),
            "calibration_count": len(inputs), "scale_method": "global max-absolute calibration, symmetric ties-even"}


def run_n1_w8a16(convs: tuple[Conv, Conv], x: np.ndarray, scales: dict, *,
                 dw_fp32_channels=(), pw_fp32_channels=()) -> tuple[np.ndarray, list[dict], np.ndarray]:
    if x.shape != (1, 64, 64, 64):
        raise ValueError(f"unexpected N1 input shape {x.shape}")
    a0 = quantize_a16(x, float(scales["input_a16_scale"]))
    y0, proof0 = _run_conv(a0, float(scales["input_a16_scale"]), convs[0],
                           fp32_channels=dw_fp32_channels)
    z0 = _gelu_fp32(y0)
    a1 = quantize_a16(z0, float(scales["pw_input_a16_scale"]))
    y1, proof1 = _run_conv(a1, float(scales["pw_input_a16_scale"]), convs[1],
                           fp32_channels=pw_fp32_channels)
    return _gelu_fp32(y1), [proof0, proof1], z0


def error_metrics(expected: np.ndarray, actual: np.ndarray) -> dict:
    a, b = np.asarray(expected, dtype=np.float64).ravel(), np.asarray(actual, dtype=np.float64).ravel()
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("error metric operands must be same-shape finite arrays")
    delta = b - a
    denom = float(np.linalg.norm(a))
    cosine_denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return {"max_abs": float(np.max(np.abs(delta))),
            "relative_l2": float(np.linalg.norm(delta) / max(denom, np.finfo(np.float64).tiny)),
            "cosine": float(np.dot(a, b) / cosine_denom) if cosine_denom else (1.0 if not np.any(b) else 0.0),
            "reference_rms": float(np.sqrt(np.mean(a * a))), "actual_rms": float(np.sqrt(np.mean(b * b)))}
