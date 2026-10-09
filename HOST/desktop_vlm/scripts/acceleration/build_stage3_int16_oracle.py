"""Full network.2.0 INT16-activation/INT8-weight CPU oracle from B data."""
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

import build_stage2_int8_reference as base
from integer_postops import multiplier_shift, round_shift_even


STAGE2_B_MANIFEST_SHA256 = "68e2a29131ca0965783b00eea54049c313de669e1c758b738f4c530bb78cd282"
FC1_NODE = "/image_encoder/model/network.2/network.2.0/convffn/fc1/Conv"
GELU_NODE = "/image_encoder/model/network.2/network.2.0/convffn/act/Mul_1"
FC2_NODE = "/image_encoder/model/network.2/network.2.0/convffn/fc2/Conv"
SCALE_NODE = "/image_encoder/model/network.2/network.2.0/Mul"
ADD_NODE = "/image_encoder/model/network.2/network.2.0/Add"
STAGE3_NODES = [FC1_NODE, GELU_NODE, FC2_NODE, SCALE_NODE, ADD_NODE]
TEXT_SHA256 = base.TEXT_SHA256


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write(out, filename, array, dtype):
    path = out / filename
    packed = np.ascontiguousarray(array, dtype=dtype)
    packed.tofile(str(path))
    return {"path": filename, "shape": list(packed.shape), "dtype": dtype,
            "bytes": path.stat().st_size, "sha256": _sha(path)}


def _metric(actual, expected):
    a, b = actual.astype(np.float64), expected.astype(np.float64)
    delta = a - b
    aa, bb = a.reshape(-1), b.reshape(-1)
    return {"max_abs": float(np.max(np.abs(delta))),
            "rms_abs": float(np.sqrt(np.mean(delta * delta))),
            "relative_l2": float(np.linalg.norm(delta) / max(float(np.linalg.norm(b)), 1e-30)),
            "cosine": float(np.dot(aa, bb) / max(float(np.linalg.norm(aa) * np.linalg.norm(bb)), 1e-30)),
            "allclose_rtol_1e-4_atol_1e-5": bool(np.allclose(
                actual, expected, rtol=1e-4, atol=1e-5))}


def _coefficients(ratios):
    multipliers, shifts = [], []
    for ratio in ratios:
        if ratio == 0:
            multipliers.append(0)
            shifts.append(0)
        else:
            magnitude, shift = multiplier_shift(abs(float(ratio)))
            multipliers.append(int(magnitude if ratio > 0 else -magnitude))
            shifts.append(int(shift))
    return np.asarray(multipliers, dtype=np.int32), np.asarray(shifts, dtype=np.int32)


def _q31_i16(values, multipliers, shifts, clip_output=True):
    data = np.asarray(values)
    if data.dtype.kind not in "iu":
        raise ValueError("Q31 input must be integer")
    if data.ndim != 3 or multipliers.size not in (1, data.shape[0]) or multipliers.shape != shifts.shape:
        raise ValueError("Q31 channel layout mismatch; expected CHW and per-channel parameters")
    output = np.empty(data.shape, dtype=np.int16 if clip_output else np.int64)
    max_product = 0
    for channel in range(data.shape[0]):
        coefficient_index = 0 if multipliers.size == 1 else channel
        product = data[channel].astype(np.int64) * np.int64(multipliers[coefficient_index])
        if product.size:
            max_product = max(max_product, int(np.max(np.abs(product))))
        rounded = round_shift_even(product, int(shifts[coefficient_index]))
        if clip_output:
            output[channel] = np.clip(rounded, -32767, 32767).astype(np.int16)
        else:
            output[channel] = rounded.astype(np.int64)
    return output, max_product


def _accumulate_pw(qinput_chw, qweight_kn, bias_q):
    channels, height, width = qinput_chw.shape
    rows = qinput_chw.transpose(1, 2, 0).reshape((height * width, channels)).astype(np.int64)
    raw = rows @ qweight_kn.astype(np.int64).T
    i32 = np.iinfo(np.int32)
    if np.any(raw < i32.min) or np.any(raw > i32.max):
        raise OverflowError("raw INT64 PW accumulator exceeds INT32")
    total = raw + bias_q.astype(np.int64)[None, :]
    if np.any(total < i32.min) or np.any(total > i32.max):
        raise OverflowError("PW accumulator plus bias exceeds INT32")
    output_channels = qweight_kn.shape[0]
    return raw, total.T.reshape((output_channels, height, width)).astype(np.int32)


def _weight_q(model, node_name):
    nodes = {node.name: node for node in model.graph.node}
    initializers = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    node = nodes[node_name]
    weight = np.asarray(initializers[node.input[1]], dtype=np.float32)[:, :, 0, 0]
    bias = np.asarray(initializers[node.input[2]], dtype=np.float32)
    scales = np.max(np.abs(weight.astype(np.float64)), axis=1) / 127.0
    scales = np.where(scales > 0, scales, 1.0)
    quantized = np.clip(np.rint(weight.astype(np.float64) / scales[:, None]),
                         -127, 127).astype(np.int8)
    return node, weight, bias, quantized, scales


def _bias_q(bias, accumulator_scales):
    result = np.rint(np.asarray(bias, dtype=np.float64) / accumulator_scales)
    limits = np.iinfo(np.int32)
    if np.any(result < limits.min) or np.any(result > limits.max):
        raise OverflowError("quantized stage3 bias exceeds int32")
    return result.astype(np.int32)


def _budget(qweight_kn, bias_q):
    l1 = np.sum(np.abs(qweight_kn.astype(np.int64)), axis=1)
    bound = l1 * np.int64(32767) + np.abs(bias_q.astype(np.int64))
    return {"reduction_length": int(qweight_kn.shape[1]),
            "all_int8_max_code_absolute_bound_before_bias": int(
                qweight_kn.shape[1] * 32767 * 127),
            "weight_l1_sum_max": int(np.max(l1)),
            "worst_case_abs_accumulator_including_bias": int(np.max(bound)),
            "worst_case_fits_int32": bool(np.all(bound <= np.iinfo(np.int32).max)),
            "int32_headroom": int(np.iinfo(np.int32).max - np.max(bound)),
            "formula": "32767*sum(abs(qweight), reduction axis)+abs(quantized_bias)"}


def _make_sessions(model_path, threads):
    model = SymbolicShapeInference.infer_shapes(onnx.load(str(model_path)), auto_merge=True)
    nodes = {node.name: node for node in model.graph.node}
    tensor_names = [nodes[name].output[0] for name in STAGE3_NODES]
    infos = {item.name: item for item in list(model.graph.value_info) + list(model.graph.output)}
    trace_suffix = onnx.utils.Extractor(model).extract_model(
        [base.DW3_OUT, base.DW7_OUT], ["features"])
    del trace_suffix.graph.output[:]
    trace_suffix.graph.output.extend([infos["features"]] + [infos[name] for name in tensor_names])
    onnx.checker.check_model(trace_suffix)
    post_suffix = onnx.utils.Extractor(model).extract_model([nodes[ADD_NODE].output[0]], ["features"])
    onnx.checker.check_model(post_suffix)
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    ort.disable_telemetry_events()
    trace_session = ort.InferenceSession(trace_suffix.SerializeToString(), options,
                                         providers=["CPUExecutionProvider"])
    post_session = ort.InferenceSession(post_suffix.SerializeToString(), options,
                                        providers=["CPUExecutionProvider"])
    initializers = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    scale_input = next(name for name in nodes[SCALE_NODE].input if name in initializers)
    layer_scale = np.asarray(initializers[scale_input], dtype=np.float32).reshape(-1)
    return model, trace_session, post_session, nodes, tensor_names, layer_scale


def _gelu_lut(scale_in, scale_out):
    lut = np.empty((65536,), dtype=np.int16)
    for encoded in range(65536):
        signed = encoded - 32768
        x = signed * scale_in
        y = 0.5 * x * (1.0 + math.erf(x / math.sqrt(2.0)))
        lut[encoded] = np.int16(max(-32767, min(32767, int(np.rint(y / scale_out)))))
    return lut


def _rank(feature, text_unit, ids):
    image = feature.astype(np.float64).reshape(-1)
    image /= max(float(np.linalg.norm(image)), 1e-30)
    scores = image @ text_unit.T
    return scores.tolist(), [ids[int(i)] for i in np.argsort(-scores, kind="stable")]


def run(args):
    b_dir = Path(args.stage2_b)
    b_manifest_path = b_dir / "manifest.json"
    if _sha(b_manifest_path) != STAGE2_B_MANIFEST_SHA256:
        raise ValueError("stage2 B manifest SHA mismatch")
    b_manifest = json.loads(b_manifest_path.read_text(encoding="utf-8"))
    if b_manifest["status"] != "STAGE2_B_INT16_ACTIVATION_INT8_WEIGHT_CPU_ABLATION_NOT_PL":
        raise ValueError("stage2 B artifact is not the accepted CPU candidate")
    model_path = Path(args.model)
    if _sha(model_path) != base.MODEL_SHA256:
        raise ValueError("source model SHA mismatch")
    text_path = Path(args.text_features)
    if _sha(text_path) != TEXT_SHA256:
        raise ValueError("text feature SHA mismatch")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    model, trace_session, post_session, nodes, trace_tensor_names, gamma = _make_sessions(
        model_path, args.threads)
    if gamma.shape != (128,):
        raise ValueError("stage3 layer-scale must contain 128 channels")
    dw3_acc_scale = np.fromfile(str(b_dir / "dw3-int16-accumulator-scales.f64"), dtype="<f8")
    dw7_acc_scale = np.fromfile(str(b_dir / "dw7-int16-accumulator-scales.f64"), dtype="<f8")
    if dw3_acc_scale.shape != (128,) or dw7_acc_scale.shape != (128,):
        raise ValueError("stage2 per-channel accumulator scales must be 128 elements")
    b_scales = b_manifest["activation_quantization"]["scales"]
    q3_scale = float(b_scales["dw3_residual_to_stage3_add"])
    q7_scale = float(b_scales["dw7_to_stage3_pw128"])
    text = np.fromfile(str(text_path), dtype="<f4").reshape((8, 512))
    text_unit = text.astype(np.float64)
    text_unit /= np.maximum(np.linalg.norm(text_unit, axis=1, keepdims=True), 1e-30)
    text_manifest = json.loads(Path(args.text_manifest).read_text(encoding="utf-8"))
    ids = [item["id"] for item in text_manifest["prompts"]]

    # Build full float traces on the exact B stage2 inputs to calibrate the
    # subsequent signed INT16 activation boundaries.
    stage2_values = []
    float_traces = []
    for record in b_manifest["results"]:
        sample_id = record["sample_id"]
        i32_3 = np.fromfile(str(b_dir / record["files"]["dw3_with_bias_i32"]["path"]),
                            dtype="<i4").reshape((128, 32, 32))
        i32_7 = np.fromfile(str(b_dir / record["files"]["dw7_with_bias_i32"]["path"]),
                            dtype="<i4").reshape((128, 32, 32))
        f3 = (i32_3.astype(np.float64) * dw3_acc_scale[:, None, None]).astype("<f4")
        f7 = (i32_7.astype(np.float64) * dw7_acc_scale[:, None, None]).astype("<f4")
        stage2_values.append((sample_id, f3, f7))
        traced = trace_session.run(None, {base.DW3_OUT: f3[None, ...], base.DW7_OUT: f7[None, ...]})
        float_traces.append(dict(zip(["features"] + STAGE3_NODES, traced)))

    scale_fc1_out = max(float(np.max(np.abs(item[FC1_NODE]))) for item in float_traces) / 32767.0
    scale_gelu_out = max(float(np.max(np.abs(item[GELU_NODE]))) for item in float_traces) / 32767.0
    scale_fc2_out = max(float(np.max(np.abs(item[FC2_NODE]))) for item in float_traces) / 32767.0
    scale_block_out = max(float(np.max(np.abs(item[ADD_NODE]))) for item in float_traces) / 32767.0
    scale_fc1_out = scale_fc1_out if scale_fc1_out else 1.0
    scale_gelu_out = scale_gelu_out if scale_gelu_out else 1.0
    scale_fc2_out = scale_fc2_out if scale_fc2_out else 1.0
    scale_block_out = scale_block_out if scale_block_out else 1.0

    n1, w1, b1, qw1, sw1 = _weight_q(model, FC1_NODE)
    n2, w2, b2, qw2, sw2 = _weight_q(model, FC2_NODE)
    if qw1.shape != (384, 128) or qw2.shape != (128, 384):
        raise ValueError("PW matrix dimensions must be real 128x384 and 384x128")
    acc_scale1, acc_scale2 = q7_scale * sw1, scale_gelu_out * sw2
    bias1_q, bias2_q = _bias_q(b1, acc_scale1), _bias_q(b2, acc_scale2)
    mul1, shift1 = _coefficients(acc_scale1 / scale_fc1_out)
    mul2, shift2 = _coefficients(acc_scale2 / scale_fc2_out)
    scale_mul, scale_shift = _coefficients((scale_fc2_out * gamma) / scale_block_out)
    residual_mul, residual_shift = _coefficients(np.asarray([q3_scale / scale_block_out]))
    gelu_table = _gelu_lut(scale_fc1_out, scale_gelu_out)
    gelu_path = out / "stage3-gelu-int16-lut.i16le"
    gelu_table.astype("<i2").tofile(str(gelu_path))
    gamma_path = out / "stage3-layer-scale.f32"
    gamma.astype("<f4").tofile(str(gamma_path))
    quant_params = {"scale_add_gelu": {}}
    for label, qweights, weight_scales, bias_q, multipliers, shifts, acc_scales in (
            ("pw128-to-384", qw1, sw1, bias1_q, mul1, shift1, acc_scale1),
            ("pw384-to-128", qw2, sw2, bias2_q, mul2, shift2, acc_scale2)):
        quant_params[label] = {}
        for suffix, array, dtype in (("weights-kn.i8", qweights, "|i1"),
                                     ("weight-scales.f64", weight_scales, "<f8"),
                                     ("bias.i32", bias_q, "<i4"),
                                     ("requant-multiplier.i32", multipliers, "<i4"),
                                     ("requant-shift.i32", shifts, "<i4"),
                                     ("accumulator-scales.f64", acc_scales, "<f8")):
            quant_params[label][suffix] = _write(out, "stage3-" + label + "-" + suffix,
                                                  array, dtype)
    for suffix, array, dtype in (("layer-scale.f32", gamma, "<f4"),
                                 ("gelu-int16-lut.i16le", gelu_table, "<i2"),
                                 ("scale-add-multiplier.i32", scale_mul, "<i4"),
                                 ("scale-add-shift.i32", scale_shift, "<i4"),
                                 ("residual-multiplier.i32", residual_mul, "<i4"),
                                 ("residual-shift.i32", residual_shift, "<i4")):
        quant_params["scale_add_gelu"][suffix] = _write(out, "stage3-" + suffix, array, dtype)
    scale_params = {"stage3-fc1-output-scale.f64": scale_fc1_out,
                    "stage3-gelu-output-scale.f64": scale_gelu_out,
                    "stage3-fc2-output-scale.f64": scale_fc2_out,
                    "stage3-block-output-scale.f64": scale_block_out,
                    "stage3-dw7-input-scale.f64": q7_scale,
                    "stage3-dw3-residual-input-scale.f64": q3_scale}
    quant_params["scale_add_gelu"]["scalar_scales"] = {}
    for filename, value in scale_params.items():
        quant_params["scale_add_gelu"]["scalar_scales"][filename] = _write(
            out, filename, np.asarray([value], dtype="<f8"), "<f8")

    records = []
    stage3_actual_budgets = {"fc1": [], "fc2": []}
    for index, b_record in enumerate(b_manifest["results"]):
        sample_id = b_record["sample_id"]
        q7_meta = b_record["files"]["dw7_stage3_i16"]
        q3_meta = b_record["files"]["dw3_residual_i16"]
        q7_path, q3_path = b_dir / q7_meta["path"], b_dir / q3_meta["path"]
        if _sha(q7_path) != q7_meta["sha256"] or _sha(q3_path) != q3_meta["sha256"]:
            raise ValueError("B-stage2 INT16 input tensor SHA mismatch")
        q7 = np.fromfile(str(q7_path), dtype="<i2").reshape((128, 32, 32))
        q3 = np.fromfile(str(q3_path), dtype="<i2").reshape((128, 32, 32))
        raw1, total1 = _accumulate_pw(q7, qw1, bias1_q)
        qfc1, q31prod1 = _q31_i16(total1, mul1, shift1)
        qgelu = gelu_table[qfc1.astype(np.int32) + 32768]
        raw2, total2 = _accumulate_pw(qgelu, qw2, bias2_q)
        qfc2, q31prod2 = _q31_i16(total2, mul2, shift2)
        scaled_branch, q31prod_scale = _q31_i16(qfc2, scale_mul, scale_shift, False)
        residual_branch, q31prod_res = _q31_i16(q3, residual_mul, residual_shift, False)
        # Branch terms remain unsaturated INT64 values until addition; only the
        # fused block output saturates to INT16.
        summed = scaled_branch.astype(np.int64) + residual_branch.astype(np.int64)
        i32 = np.iinfo(np.int32)
        scale_branch_fits_i32 = bool(np.all(scaled_branch >= i32.min) and
                                     np.all(scaled_branch <= i32.max))
        residual_branch_fits_i32 = bool(np.all(residual_branch >= i32.min) and
                                        np.all(residual_branch <= i32.max))
        add_i32_fits = bool(np.all(summed >= i32.min) and np.all(summed <= i32.max))
        if not scale_branch_fits_i32 or not residual_branch_fits_i32:
            raise OverflowError("scale/residual Q31 branch exceeds INT32 serialization range")
        qblock = np.clip(summed, -32767, 32767).astype(np.int16)
        block_float = (qblock.astype(np.float64) * scale_block_out).astype("<f4")[None, ...]
        traces = float_traces[index]
        qfc1_dequant = (qfc1.astype(np.float64) * scale_fc1_out).astype("<f4")[None, ...]
        qgelu_dequant = (qgelu.astype(np.float64) * scale_gelu_out).astype("<f4")[None, ...]
        qfc2_dequant = (qfc2.astype(np.float64) * scale_fc2_out).astype("<f4")[None, ...]
        float_features = traces["features"]
        quant_features = post_session.run(["features"], {nodes[ADD_NODE].output[0]: block_float})[0]
        board_name, board_sha = base.BOARD_FEATURES[index]
        board_path = Path(args.board_feature_dir) / board_name
        if _sha(board_path) != board_sha:
            raise ValueError("pure PS 512 feature reference SHA mismatch")
        board_features = np.fromfile(str(board_path), dtype="<f4").reshape((1, 512))
        float_scores, float_rank = _rank(float_features, text_unit, ids)
        quant_scores, quant_rank = _rank(quant_features, text_unit, ids)
        board_scores, board_rank = _rank(board_features, text_unit, ids)

        raw1_min, raw1_max = int(raw1.min()), int(raw1.max())
        raw2_min, raw2_max = int(raw2.min()), int(raw2.max())
        stage3_actual_budgets["fc1"].append({
            "sample_id": sample_id, "spatial_positions": 1024,
            "raw_accum_int64_minmax": [raw1_min, raw1_max],
            "raw_accum_fits_int32": bool(raw1_min >= i32.min and raw1_max <= i32.max),
            "accum_plus_bias_fits_int32": True,
        })
        stage3_actual_budgets["fc2"].append({
            "sample_id": sample_id, "spatial_positions": 1024,
            "raw_accum_int64_minmax": [raw2_min, raw2_max],
            "raw_accum_fits_int32": bool(raw2_min >= i32.min and raw2_max <= i32.max),
            "accum_plus_bias_fits_int32": True,
        })
        prefix = sample_id + "-stage3-"
        sample_files = {
            "pw128_input_q7_i16": q7_meta,
            "residual_q3_i16": q3_meta,
            "fc1_with_bias_i32": _write(out, prefix + "fc1-with-bias.i32", total1[None, ...], "<i4"),
            "fc1_output_i16": _write(out, prefix + "fc1-output.i16", qfc1[None, ...], "<i2"),
            "gelu_output_i16": _write(out, prefix + "gelu-output.i16", qgelu[None, ...], "<i2"),
            "fc2_with_bias_i32": _write(out, prefix + "fc2-with-bias.i32", total2[None, ...], "<i4"),
            "fc2_output_i16": _write(out, prefix + "fc2-output.i16", qfc2[None, ...], "<i2"),
            "scale_branch_i32": _write(out, prefix + "scale-branch.i32", scaled_branch[None, ...], "<i4"),
            "residual_branch_i32": _write(out, prefix + "residual-branch.i32", residual_branch[None, ...], "<i4"),
            "block_add_output_i16": _write(out, prefix + "block-add-output.i16", qblock[None, ...], "<i2"),
        }
        qblock_path = out / (prefix + "single-output-packet.i16le")
        qblock_path.write_bytes(np.ascontiguousarray(qblock, dtype="<i2").tobytes(order="C"))
        sample_files["stage3_output_packet"] = {
            "path": qblock_path.name, "sha256": _sha(qblock_path),
            "dtype": "signed int16 little-endian", "shape": [1, 128, 32, 32],
            "offset_bytes": 0, "bytes": 262144, "alignment_bytes": 2,
            "physical_packets": 1, "shared_frame_id": sample_id,
            "TLAST": "only after final byte at offset 262143",
        }
        stage_metrics = {
            "fc1_output_vs_float_trace": _metric(qfc1_dequant, traces[FC1_NODE]),
            "gelu_output_vs_float_trace": _metric(qgelu_dequant, traces[GELU_NODE]),
            "fc2_output_vs_float_trace": _metric(qfc2_dequant, traces[FC2_NODE]),
            "fused_scale_add_output_vs_float_trace": _metric(block_float, traces[ADD_NODE]),
            "unquantized_b_stage2_suffix_vs_pure_ps_feature": _metric(float_features, board_features),
            "quantized_stage3_final512_vs_pure_ps_feature": _metric(quant_features, board_features),
        }
        records.append({
            "sample_id": sample_id,
            "input_sha256": b_record["input_sha256"],
            "stage2_b_manifest_sha256": STAGE2_B_MANIFEST_SHA256,
            "stage2_boundary_packet": b_record["files"]["dual_accumulator_packet"],
            "board_ps_feature_sha256": board_sha,
            "files": sample_files,
            "accumulator_semantics": {
                "fc1_raw": "signed INT64 sum of q7_i16*qw1_i8; bias excluded until checked quantized i32 bias add",
                "fc1_output": "post-bias signed INT32 accumulator; bias included",
                "fc2_raw": "signed INT64 sum of gelu_i16*qw2_i8; bias excluded until checked quantized i32 bias add",
                "fc2_output": "post-bias signed INT32 accumulator; bias included",
                "stage3_add": "signed Q31 branch values remain unsaturated INT64; signed round-shift-even; sum in INT64, check INT32 candidate range; saturate to [-32767,32767] only at block output",
            },
            "int64_and_int32_checks": {
                "fc1_raw_int64_minmax": [raw1_min, raw1_max],
                "fc1_raw_fits_i32": stage3_actual_budgets["fc1"][-1]["raw_accum_fits_int32"],
                "fc1_bias_add_fits_i32": True,
                "fc2_raw_int64_minmax": [raw2_min, raw2_max],
                "fc2_raw_fits_i32": stage3_actual_budgets["fc2"][-1]["raw_accum_fits_int32"],
                "fc2_bias_add_fits_i32": True,
                "scale_branch_q31_max_product_abs": q31prod_scale,
                "residual_branch_q31_max_product_abs": q31prod_res,
                "fc1_q31_max_product_abs": q31prod1,
                "fc2_q31_max_product_abs": q31prod2,
                "scale_branch_int32_fits": scale_branch_fits_i32,
                "residual_branch_int32_fits": residual_branch_fits_i32,
                "add_int32_fits": add_i32_fits,
                "pre_saturation_add_int64_minmax": [int(summed.min()), int(summed.max())],
            },
            "feature_metrics": stage_metrics,
            "text_similarity": {
                "candidate_ids": ids,
                "pure_ps_scores": board_scores, "pure_ps_ranking": board_rank,
                "float_b_suffix_scores": float_scores, "float_b_suffix_ranking": float_rank,
                "int16_int8_stage3_scores": quant_scores,
                "int16_int8_stage3_ranking": quant_rank,
                "pure_ps_top1": board_rank[0], "quantized_stage3_top1": quant_rank[0],
                "top1_changed": board_rank[0] != quant_rank[0],
                "full_rank_matches_pure_ps": board_rank == quant_rank,
            },
        })

    budgets = {
        "stage3_fc1_pw128_to_384": _budget(qw1, bias1_q),
        "stage3_fc2_pw384_to_128": _budget(qw2, bias2_q),
        "actual_all_1024_pixels": stage3_actual_budgets,
        "accumulator_width": "signed INT32 candidate, independent signed INT64 reference; actual and conservative bounds both recorded",
    }
    report = {
        "schema_version": 1,
        "status": "STAGE3_FULL_BLOCK_INT16_ACTIVATION_INT8_WEIGHT_CPU_ORACLE_NOT_PL",
        "source_model_sha256": base.MODEL_SHA256,
        "stage2_b_manifest_sha256": STAGE2_B_MANIFEST_SHA256,
        "stage2_b_status": b_manifest["status"],
        "board_collection_manifest_sha256": base.COLLECTION_MANIFEST_SHA256,
        "text_features_sha256": TEXT_SHA256,
        "text_manifest_sha256": _sha(Path(args.text_manifest)),
        "board_ps_features_are_authoritative": True,
        "host_ort_traces_are_calibration_and_comparison_only": True,
        "host_dw7_allclose_failures_preserved_from_stage2_b": b_manifest[
            "host_dw7_allclose_failures_preserved"],
        "pl_execution": False,
        "shape_and_layout": {
            "input_main": {"tensor": base.DW7_OUT, "shape": [1, 128, 32, 32],
                           "dtype": "signed INT16 little-endian NCHW", "scale": q7_scale, "zero_point": 0},
            "input_residual": {"tensor": base.DW3_OUT, "shape": [1, 128, 32, 32],
                               "dtype": "signed INT16 little-endian NCHW", "scale": q3_scale, "zero_point": 0},
            "fc1_output": {"shape": [1, 384, 32, 32], "dtype": "signed INT16 little-endian NCHW",
                           "scale": scale_fc1_out, "zero_point": 0},
            "gelu_output": {"shape": [1, 384, 32, 32], "dtype": "signed INT16 little-endian NCHW",
                            "scale": scale_gelu_out, "zero_point": 0},
            "fc2_output": {"shape": [1, 128, 32, 32], "dtype": "signed INT16 little-endian NCHW",
                           "scale": scale_fc2_out, "zero_point": 0},
            "block_scale_add_output": {"tensor": nodes[ADD_NODE].output[0],
                                       "shape": [1, 128, 32, 32],
                                       "dtype": "signed INT16 little-endian NCHW",
                                       "scale": scale_block_out, "zero_point": 0},
            "weight_quantization": "symmetric per output channel, signed INT8, zero point 0, round ties-even, clip [-127,127]",
            "activation_quantization": "symmetric signed INT16, zero point 0, round ties-even, clip [-32767,32767]",
        },
        "stage2_to_stage3_physical_packet": {
            "packet_count": 1, "dtype": "signed INT32 little-endian", "total_bytes": 1048576,
            "segment_0": {"meaning": "DW3 bias-included raw accumulator", "offset_bytes": 0,
                           "bytes": 524288, "shape": [1, 128, 32, 32]},
            "segment_1": {"meaning": "DW7 bias-included raw accumulator", "offset_bytes": 524288,
                           "bytes": 524288, "shape": [1, 128, 32, 32]},
            "TLAST": "one TLAST only at packet byte offset 1048575",
            "frame_id": "one packet per input frame; host records use image-00/image-01/image-02",
            "PL_buffer_policy": "DW3 raw INT32 is streamed to PS; one DW3 q3 INT16 tensor (256 KiB) is retained on-chip and used for DW7; do not retain both DW3 and DW7 raw accumulator tensors in PL. DW7 raw INT32 follows in the same S2MM packet.",
            "fused_stage3_policy": "when stage3 scale/add is fused, q3 remains the residual input on chip and the DW3 raw32 return segment may be removed from that fused implementation packet.",
        },
        "stage3_internal_boundaries": {
            "fc1_accumulator": {"dtype": "signed INT32", "bias_included_in_output": True,
                                 "raw_reference": "signed INT64", "requant": "per-channel Q31, signed ties-even, clip [-32767,32767]"},
            "gelu": {"dtype": "signed INT16", "lut_entries": 65536,
                     "index": "signed INT16 code + 32768", "table_dtype": "little-endian signed INT16",
                     "rounding": "ties-to-even", "clip": [-32767, 32767]},
            "fc2_accumulator": {"dtype": "signed INT32", "bias_included_in_output": True,
                                 "raw_reference": "signed INT64", "requant": "per-channel Q31, signed ties-even, clip [-32767,32767]"},
            "scale_add": {"fc2_scale_multiplier": "signed per-channel Q31 approximating S_fc2*gamma[channel]/S_block",
                          "residual_multiplier": "Q31 approximating S_q3/S_block",
                          "branch_rounding": "signed round-shift-even; branch values then INT64-add; final output clips [-32767,32767]",
                          "output_packet": "single NCHW INT16 tensor, 262144 bytes, one TLAST after byte 262143 if DMA-exported"},
        },
        "activation_scales": {
            "dw7_input": q7_scale, "dw3_residual": q3_scale,
            "fc1_output": scale_fc1_out, "gelu_output": scale_gelu_out,
            "fc2_output": scale_fc2_out, "block_output": scale_block_out,
            "zero_point_all": 0,
        },
        "parameter_files": quant_params,
        "gelu_lut": {"path": gelu_path.name, "entries": 65536, "bytes": gelu_path.stat().st_size,
                     "sha256": _sha(gelu_path), "input_scale": scale_fc1_out,
                     "output_scale": scale_gelu_out},
        "int32_budget": budgets,
        "results": records,
        "suffix_runtime": {"runtime": ort.__version__, "threads": args.threads,
                           "execution": "host CPU ORT; full suffix after Stage3 Add"},
        "checks": {"three_real_32x32_inputs": True,
                   "full_spatial_position_count_per_input": 1024,
                   "stage3_pw_accumulations_computed_in_int64": True,
                   "bias_adds_checked_against_int32": True,
                   "layer_scale_and_residual_add_quantized_and_executed": True,
                   "allclose_values_preserved_without_threshold_relaxation": True,
                   "pl_execution": False},
    }
    report["files"] = {path.name: {"bytes": path.stat().st_size, "sha256": _sha(path)}
                       for path in sorted(out.iterdir()) if path.is_file()}
    manifest = out / "manifest.json"
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps({"output": str(out.resolve()), "manifest_sha256": _sha(manifest),
                      "results": [{"sample_id": item["sample_id"],
                                   "top1_changed": item["text_similarity"]["top1_changed"],
                                   "full_rank_matches": item["text_similarity"]["full_rank_matches_pure_ps"],
                                   "feature": item["feature_metrics"]["quantized_stage3_final512_vs_pure_ps_feature"]}
                                  for item in records],
                      "int32_budget": budgets}, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage2-b", default="artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int16act-007")
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--text-features", default="artifacts/board-debug-20261004/host/s1-onnx-001/text-features.f32")
    parser.add_argument("--text-manifest", default="artifacts/board-debug-20261004/host/s1-onnx-001/manifest.json")
    parser.add_argument("--board-feature-dir", default="artifacts/board-debug-20261004/network/runtime/board-runs")
    parser.add_argument("--output", required=True)
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
