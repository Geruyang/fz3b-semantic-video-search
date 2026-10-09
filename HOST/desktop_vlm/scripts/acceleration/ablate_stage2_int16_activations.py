"""Full-real-shape INT16-activation/INT8-weight B ablation and stage3 budget.

All output remains a host CPU reference. It reuses the pinned ONNX parameters
and real PS tensors; it does not claim PL execution or deployable accuracy.
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

import build_stage2_int8_reference as base
from integer_postops import multiplier_shift, round_shift_even


BASE_MANIFEST_SHA256 = "baa9b584b075462b5d7dbd77aac8a83daa5227dace23dc5cbc6f933795b59a4f"
TEXT_MANIFEST = Path("artifacts/board-debug-20261004/host/s1-onnx-001/manifest.json")
FC1_NODE = "/image_encoder/model/network.2/network.2.0/convffn/fc1/Conv"
GELU_NODE = "/image_encoder/model/network.2/network.2.0/convffn/act/Mul_1"
FC2_NODE = "/image_encoder/model/network.2/network.2.0/convffn/fc2/Conv"


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


def _symmetric_scale(values, bits):
    maximum = float(np.max(np.abs(np.asarray(values, dtype=np.float64))))
    return maximum / float((1 << (bits - 1)) - 1) if maximum else 1.0


def _quantize16(values, scale):
    return np.clip(np.rint(np.asarray(values, dtype=np.float64) / scale),
                   -32767, 32767).astype(np.int16)


def _bias_i32(bias, acc_scales):
    rounded = np.rint(np.asarray(bias, dtype=np.float64) / acc_scales)
    limits = np.iinfo(np.int32)
    if np.any(rounded < limits.min) or np.any(rounded > limits.max):
        raise OverflowError("quantized bias does not fit int32")
    return rounded.astype(np.int32)


def _requant_q31_i16(accumulator, multiplier, shift):
    """Per-channel CHW accumulator to symmetric INT16 with ties-even."""
    output = np.empty(accumulator.shape, dtype=np.int16)
    max_product = 0
    for channel in range(accumulator.shape[0]):
        product = accumulator[channel].astype(np.int64) * np.int64(multiplier[channel])
        max_product = max(max_product, int(np.max(np.abs(product))))
        rounded = round_shift_even(product, int(shift[channel]))
        output[channel] = np.clip(rounded, -32767, 32767).astype(np.int16)
    return output, max_product


def _q31_params(ratios):
    values = [multiplier_shift(float(item)) for item in ratios]
    multipliers = np.asarray([item[0] for item in values], dtype=np.int32)
    shifts = np.asarray([item[1] for item in values], dtype=np.int32)
    represented = multipliers.astype(np.float64) / np.exp2(shifts.astype(np.float64))
    return multipliers, shifts, represented


def _checked_accum(raw, bias):
    limits = np.iinfo(np.int32)
    if np.any(raw < limits.min) or np.any(raw > limits.max):
        raise OverflowError("raw int64 convolution accumulation exceeds int32")
    total = raw.astype(np.int64) + np.asarray(bias, dtype=np.int64).reshape(
        (bias.shape[0],) + (1,) * (raw.ndim - 1))
    if np.any(total < limits.min) or np.any(total > limits.max):
        raise OverflowError("accumulation plus bias exceeds int32")
    return total.astype(np.int32)


def _budget(qweight, bias_q, reduction_axis):
    # Bound every input element independently by the full symmetric INT16 range.
    l1 = np.sum(np.abs(qweight.astype(np.int64)), axis=reduction_axis)
    bound = l1 * np.int64(32767) + np.abs(bias_q.astype(np.int64))
    return {"reduction_length": int(qweight.shape[reduction_axis]),
            "max_abs_weight_l1_sum": int(np.max(l1)),
            "worst_case_abs_accumulator_including_bias": int(np.max(bound)),
            "worst_case_fits_int32": bool(np.all(bound <= np.iinfo(np.int32).max)),
            "int32_positive_headroom": int(np.iinfo(np.int32).max - np.max(bound)),
            "bound_formula": "32767 * sum(abs(INT8_weight), reduction axis) + abs(INT32_quantized_bias)"}


def _pw_weights(model, node_name):
    nodes = {item.name: item for item in model.graph.node}
    initializers = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    node = nodes[node_name]
    weight = np.asarray(initializers[node.input[1]], dtype=np.float32)[:, :, 0, 0]
    bias = np.asarray(initializers[node.input[2]], dtype=np.float32)
    scales = np.max(np.abs(weight.astype(np.float64)), axis=1) / 127.0
    scales = np.where(scales > 0, scales, 1.0)
    qweight = np.clip(np.rint(weight.astype(np.float64) / scales[:, None]),
                      -127, 127).astype(np.int8)
    return weight, bias, qweight, scales


def _suffix_with_stage3_traces(model_path, threads):
    model = SymbolicShapeInference.infer_shapes(onnx.load(str(model_path)), auto_merge=True)
    extractor = onnx.utils.Extractor(model)
    suffix = extractor.extract_model([base.DW3_OUT, base.DW7_OUT], ["features"])
    nodes = {node.name: node for node in model.graph.node}
    trace_nodes = [FC1_NODE, GELU_NODE, FC2_NODE]
    trace_outputs = [nodes[name].output[0] for name in trace_nodes]
    values = {value.name: value for value in list(model.graph.value_info) + list(model.graph.output)}
    del suffix.graph.output[:]
    suffix.graph.output.extend([values["features"]] + [values[name] for name in trace_outputs])
    onnx.checker.check_model(suffix)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    ort.disable_telemetry_events()
    session = ort.InferenceSession(suffix.SerializeToString(), opts,
                                   providers=["CPUExecutionProvider"])
    return model, session, trace_nodes


def _feature_rank(feature, text_unit, ids):
    vector = feature.astype(np.float64).reshape(-1)
    vector /= max(float(np.linalg.norm(vector)), 1e-30)
    scores = vector @ text_unit.T
    return scores.tolist(), [ids[int(i)] for i in np.argsort(-scores, kind="stable")]


def _metrics(a, b):
    a64, b64 = a.astype(np.float64), b.astype(np.float64)
    delta = a64 - b64
    flat_a, flat_b = a64.reshape(-1), b64.reshape(-1)
    return {"max_abs": float(np.max(np.abs(delta))),
            "rms_abs": float(np.sqrt(np.mean(delta * delta))),
            "relative_l2": float(np.linalg.norm(delta) / max(float(np.linalg.norm(b64)), 1e-30)),
            "cosine": float(np.dot(flat_a, flat_b) /
                            max(float(np.linalg.norm(flat_a) * np.linalg.norm(flat_b)), 1e-30)),
            "allclose_rtol_1e-4_atol_1e-5": bool(np.allclose(a, b, rtol=1e-4, atol=1e-5))}


def run(args):
    source = Path(args.source)
    source_manifest = source / "manifest.json"
    if _sha(source_manifest) != BASE_MANIFEST_SHA256:
        raise ValueError("pinned stage2 int8-007 manifest hash mismatch")
    base_report = json.loads(source_manifest.read_text(encoding="utf-8"))
    if _sha(Path(args.model)) != base.MODEL_SHA256:
        raise ValueError("pinned source model SHA mismatch")
    if _sha(Path(args.text_features)) != base.TEXT_SHA256:
        raise ValueError("pinned text-feature SHA mismatch")
    collection, split, board_records, host_comparison = base._load_board_collection(
        Path(args.collection_dir), Path(args.split_manifest))
    model, session, trace_nodes = _suffix_with_stage3_traces(args.model, args.threads)
    nodes = {node.name: node for node in model.graph.node}
    init = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    text = np.fromfile(str(args.text_features), dtype="<f4").reshape((8, 512))
    text_unit = text.astype(np.float64)
    text_unit /= np.maximum(np.linalg.norm(text_unit, axis=1, keepdims=True), 1e-30)
    ids = [entry["id"] for entry in json.loads(TEXT_MANIFEST.read_text(encoding="utf-8"))["prompts"]]
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)

    layer_specs = base._load_params(Path(args.model))[1]
    pre_scale = _symmetric_scale(np.stack([item["tensors"]["pre-dw3"] for item in board_records]), 16)
    accscale3 = pre_scale * layer_specs[0]["weight_scale"]
    bias3_q = _bias_i32(layer_specs[0]["bias"], accscale3)
    qpre_by_case, total3_by_case = [], []
    for record in board_records:
        qpre = _quantize16(record["tensors"]["pre-dw3"], pre_scale)
        raw = base._depthwise_accumulate(qpre, layer_specs[0]["qweight"])
        total = _checked_accum(raw, bias3_q)
        qpre_by_case.append(qpre)
        total3_by_case.append(total)
    dw3_float_by_case = [(total.astype(np.float64) * accscale3[:, None, None]).astype("<f4")
                         for total in total3_by_case]
    mid_scale = _symmetric_scale(np.stack(dw3_float_by_case), 16)
    mid_multiplier, mid_shift, mid_ratio = _q31_params(accscale3 / mid_scale)
    qmid_by_case, qmid_product_max = [], []
    for total in total3_by_case:
        qmid, product_max = _requant_q31_i16(total, mid_multiplier, mid_shift)
        qmid_by_case.append(qmid)
        qmid_product_max.append(product_max)
    accscale7 = mid_scale * layer_specs[1]["weight_scale"]
    bias7_q = _bias_i32(layer_specs[1]["bias"], accscale7)
    total7_by_case = []
    for index, record in enumerate(board_records):
        raw = base._depthwise_accumulate(qmid_by_case[index], layer_specs[1]["qweight"])
        total = _checked_accum(raw, bias7_q)
        total7_by_case.append(total)
    dw7_float_by_case = [(total.astype(np.float64) * accscale7[:, None, None]).astype("<f4")
                         for total in total7_by_case]
    dw7_scale = _symmetric_scale(np.stack(dw7_float_by_case), 16)
    q7_multiplier, q7_shift, q7_ratio = _q31_params(accscale7 / dw7_scale)
    qdw7_by_case, q7_product_max = [], []
    for total in total7_by_case:
        qout, product_max = _requant_q31_i16(total, q7_multiplier, q7_shift)
        qdw7_by_case.append(qout)
        q7_product_max.append(product_max)
    residual_scale = mid_scale
    qres_by_case = [value.copy() for value in qmid_by_case]
    stage2_records = []

    # Freeze the stage2 depthwise parameters for JTAG: these INT32 biases are
    # specific to the B pre/mid scales and must not reuse 007's INT8 bias files.
    stage2_parameter_files = {}
    for index, layer in enumerate(layer_specs):
        label = "dw3" if index == 0 else "dw7"
        weight_path = out / (label + "-weights-chw.i8")
        weight_scale_path = out / (label + "-weight-scales.f64")
        bias_path = out / (label + "-bias.i32")
        accum_scale_path = out / (label + "-int16-accumulator-scales.f64")
        qweight = layer["qweight"]
        weight_scale = layer["weight_scale"]
        bias_q = bias3_q if index == 0 else bias7_q
        accum_scale = accscale3 if index == 0 else accscale7
        qweight.tofile(str(weight_path))
        np.asarray(weight_scale, dtype="<f8").tofile(str(weight_scale_path))
        np.asarray(bias_q, dtype="<i4").tofile(str(bias_path))
        np.asarray(accum_scale, dtype="<f8").tofile(str(accum_scale_path))
        stage2_parameter_files[label] = {
            "weight_shape_chw": list(qweight.shape), "weight_layout": "C,1,KH,KW",
            "weight_file": _write(out, weight_path.name, qweight, "|i1"),
            "weight_scale_file": _write(out, weight_scale_path.name, weight_scale, "<f8"),
            "bias_i32_file": _write(out, bias_path.name, bias_q, "<i4"),
            "accumulator_scale_file": _write(out, accum_scale_path.name, accum_scale, "<f8"),
            "input_scale": pre_scale if index == 0 else mid_scale,
            "bias_rule": "round-to-nearest-ties-even(FP32 ONNX bias / (INT16 input scale * per-channel INT8 weight scale)); bias included in output INT32 accumulator",
            "bias_int32_minmax": [int(bias_q.min()), int(bias_q.max())],
        }
    stage2_parameter_files["dw3"]["requant_to_dw7"] = {
        "multiplier_file": _write(out, "dw3-to-dw7-int16-requant-multiplier.i32", mid_multiplier, "<i4"),
        "shift_file": _write(out, "dw3-to-dw7-int16-requant-shift.i32", mid_shift, "<i4"),
        "represented_ratio_file": _write(out, "dw3-to-dw7-int16-requant-ratio.f64", mid_ratio, "<f8"),
        "target_scale": mid_scale, "zero_point": 0,
        "rounding": "signed Q31 product, round-shift-even, clip [-32767,32767]",
        "max_q31_product_abs": int(max(qmid_product_max)),
    }
    stage2_parameter_files["dw7"]["requant_to_stage3"] = {
        "multiplier_file": _write(out, "dw7-to-stage3-int16-requant-multiplier.i32", q7_multiplier, "<i4"),
        "shift_file": _write(out, "dw7-to-stage3-int16-requant-shift.i32", q7_shift, "<i4"),
        "represented_ratio_file": _write(out, "dw7-to-stage3-int16-requant-ratio.f64", q7_ratio, "<f8"),
        "target_scale": dw7_scale, "zero_point": 0,
        "rounding": "signed Q31 product, round-shift-even, clip [-32767,32767]",
        "max_q31_product_abs": int(max(q7_product_max)),
    }

    # Stage3 full-shape INT16 x INT8 accumulator exercise uses the DW7 INT16
    # activation on FC1 and the real full-suffix GELU trace on FC2 calibration.
    w1, b1, qw1, sw1 = _pw_weights(model, FC1_NODE)
    w2, b2, qw2, sw2 = _pw_weights(model, FC2_NODE)
    fc1_float_traces, gelu_float_traces, fc2_float_traces = [], [], []
    b_features = []
    for index in range(3):
        values = session.run(None, {base.DW3_OUT: dw3_float_by_case[index][None, ...],
                                   base.DW7_OUT: dw7_float_by_case[index][None, ...]})
        b_features.append(values[0])
        mapping = dict(zip(trace_nodes, values[1:]))
        fc1_float_traces.append(mapping[FC1_NODE])
        gelu_float_traces.append(mapping[GELU_NODE])
        fc2_float_traces.append(mapping[FC2_NODE])
    fc1_out_scale = _symmetric_scale(np.stack(fc1_float_traces), 16)
    gelu_scale = _symmetric_scale(np.stack(gelu_float_traces), 16)
    fc1_accum_scale = dw7_scale * sw1
    fc1_bias_q = _bias_i32(b1, fc1_accum_scale)
    fc2_accum_scale = gelu_scale * sw2
    fc2_bias_q = _bias_i32(b2, fc2_accum_scale)
    stage3_contracts = {}
    for label, weight, scales, bias_q, input_scale in (
            ("fc1_pw128_to_384", qw1, sw1, fc1_bias_q, dw7_scale),
            ("fc2_pw384_to_128", qw2, sw2, fc2_bias_q, gelu_scale)):
        weights_path = out / (label + "-weights-kn.i8")
        scales_path = out / (label + "-weight-scales.f64")
        bias_path = out / (label + "-bias.i32")
        np.asarray(weight, dtype="|i1").tofile(str(weights_path))
        np.asarray(scales, dtype="<f8").tofile(str(scales_path))
        np.asarray(bias_q, dtype="<i4").tofile(str(bias_path))
        stage3_contracts[label] = {
            "weight_shape_kn": list(weight.shape), "input_scale": input_scale,
            "input_zero_point": 0, "input_dtype": "int16 symmetric [-32767,32767]",
            "weight_dtype": "int8 symmetric [-127,127]", "weight_zero_point": 0,
            "weight_scale_per_output_channel": {"path": scales_path.name, "sha256": _sha(scales_path)},
            "weight_file": {"path": weights_path.name, "sha256": _sha(weights_path)},
            "quantized_bias_file": {"path": bias_path.name, "sha256": _sha(bias_path)},
            "accumulator_scale_formula": "input_activation_scale * per-output-channel weight scale",
            "rounding": "ties-to-even", "activation_clip": [-32767, 32767],
            "weight_clip": [-127, 127],
            "int32_worst_case_budget": _budget(weight, bias_q, 1),
        }

    # Run actual per-pixel INT64 accumulator checks for stage3 PW layers on the
    # calibrated full 32x32 activation tensors, not a spatial fixture.
    stage3_actual = {"fc1_pw128_to_384": [], "fc2_pw384_to_128": []}
    stage3_activation_files = []
    for index in range(3):
        q_fc1_in = qdw7_by_case[index].transpose(1, 2, 0).reshape((1024, 128)).astype(np.int64)
        q_fc1_file = _write(out, board_records[index]["sample_id"] +
                            "-stage3-pw128-input.i16", qdw7_by_case[index], "<i2")
        raw_fc1 = q_fc1_in @ qw1.astype(np.int64).T
        total_fc1 = _checked_accum(raw_fc1.T.reshape((384, 32, 32)), fc1_bias_q)
        dequant_fc1 = (total_fc1.astype(np.float64) * fc1_accum_scale[:, None, None]).astype("<f4")
        trace_fc1 = fc1_float_traces[index][0]
        stage3_actual["fc1_pw128_to_384"].append({
            "sample_id": board_records[index]["sample_id"],
            "spatial_positions": 1024,
            "raw_accum_int64_minmax": [int(raw_fc1.min()), int(raw_fc1.max())],
            "raw_accum_fits_int32": bool(raw_fc1.min() >= np.iinfo(np.int32).min and
                                          raw_fc1.max() <= np.iinfo(np.int32).max),
            "bias_added_fits_int32": True,
            "dequantized_accumulator_vs_float_suffix_trace": base._error_record(
                dequant_fc1[None, ...], trace_fc1[None, ...]),
        })
        q_fc2_in = _quantize16(gelu_float_traces[index][0], gelu_scale)
        q_fc2_file = _write(out, board_records[index]["sample_id"] +
                            "-stage3-pw384-input-gelu.i16", q_fc2_in, "<i2")
        stage3_activation_files.append({"sample_id": board_records[index]["sample_id"],
                                        "pw128_input": q_fc1_file,
                                        "pw384_input_gelu_trace": q_fc2_file})
        q_fc2_rows = q_fc2_in.transpose(1, 2, 0).reshape((1024, 384)).astype(np.int64)
        raw_fc2 = q_fc2_rows @ qw2.astype(np.int64).T
        total_fc2 = _checked_accum(raw_fc2.T.reshape((128, 32, 32)), fc2_bias_q)
        dequant_fc2 = (total_fc2.astype(np.float64) * fc2_accum_scale[:, None, None]).astype("<f4")
        stage3_actual["fc2_pw384_to_128"].append({
            "sample_id": board_records[index]["sample_id"],
            "spatial_positions": 1024,
            "raw_accum_int64_minmax": [int(raw_fc2.min()), int(raw_fc2.max())],
            "raw_accum_fits_int32": bool(raw_fc2.min() >= np.iinfo(np.int32).min and
                                          raw_fc2.max() <= np.iinfo(np.int32).max),
            "bias_added_fits_int32": True,
            "dequantized_accumulator_vs_float_suffix_trace": base._error_record(
                dequant_fc2[None, ...], fc2_float_traces[index]),
        })

    for index, board in enumerate(board_records):
        sample_id = board["sample_id"]
        total3, total7 = total3_by_case[index], total7_by_case[index]
        raw3 = base._depthwise_accumulate(_quantize16(board["tensors"]["pre-dw3"], pre_scale),
                                          layer_specs[0]["qweight"])
        raw7 = base._depthwise_accumulate(qmid_by_case[index], layer_specs[1]["qweight"])
        packet_path = out / (sample_id + "-stage2-int16-dual-accumulator-packet.i32le")
        with packet_path.open("wb") as packet:
            packet.write(np.ascontiguousarray(total3, dtype="<i4").tobytes(order="C"))
            packet.write(np.ascontiguousarray(total7, dtype="<i4").tobytes(order="C"))
        packet = {"path": packet_path.name, "sha256": _sha(packet_path),
                  "dtype": "signed int32 little-endian", "total_bytes": 1048576,
                  "single_physical_packet": True, "frame_id": sample_id,
                  "segments": [
                      {"name": "DW3 bias-included accumulator", "offset_bytes": 0,
                       "bytes": 524288, "shape": [1, 128, 32, 32], "alignment_bytes": 4,
                       "accumulator_contains_bias": True,
                       "scale_file": "dw3-int16-accumulator-scales.f64", "zero_point": 0},
                      {"name": "DW7 bias-included accumulator", "offset_bytes": 524288,
                       "bytes": 524288, "shape": [1, 128, 32, 32], "alignment_bytes": 4,
                       "accumulator_contains_bias": True,
                       "scale_file": "dw7-int16-accumulator-scales.f64", "zero_point": 0}],
                  "TLAST": "only final byte at offset 1048575; both segments share one frame_id"}
        files = {
            "pre_dw3_i16": _write(out, sample_id + "-pre-dw3.i16", _quantize16(
                board["tensors"]["pre-dw3"], pre_scale), "<i2"),
            "dw3_middle_i16": _write(out, sample_id + "-dw3-middle.i16", qmid_by_case[index], "<i2"),
            "dw7_stage3_i16": _write(out, sample_id + "-dw7-stage3.i16", qdw7_by_case[index], "<i2"),
            "dw3_residual_i16": _write(out, sample_id + "-dw3-residual.i16", qres_by_case[index], "<i2"),
            "dw3_with_bias_i32": _write(out, sample_id + "-dw3-with-bias.i32", total3, "<i4"),
            "dw7_with_bias_i32": _write(out, sample_id + "-dw7-with-bias.i32", total7, "<i4"),
            "dual_accumulator_packet": packet,
        }
        features = b_features[index]
        board_feature_name, board_feature_sha = base.BOARD_FEATURES[index]
        board_feature_path = Path(args.board_feature_dir) / board_feature_name
        if _sha(board_feature_path) != board_feature_sha:
            raise ValueError("pure PS feature SHA mismatch")
        board_features = np.fromfile(str(board_feature_path), dtype="<f4").reshape((1, 512))
        scores, ranking = _feature_rank(features, text_unit, ids)
        ps_scores, ps_ranking = _feature_rank(board_features, text_unit, ids)
        stage2_records.append({
            "sample_id": sample_id, "input_sha256": board["input_sha256"],
            "files": files,
            "pure_ps_feature_sha256": board_feature_sha,
            "feature_vs_pure_ps": _metrics(features, board_features),
            "board_ps_top1": ps_ranking[0], "b_top1": ranking[0],
            "top1_changed": ranking[0] != ps_ranking[0],
            "board_ps_ranking": ps_ranking, "b_ranking": ranking,
            "board_ps_scores": ps_scores, "b_scores": scores,
            "rank_matches_pure_ps": ranking == ps_ranking,
            "dw3_int16_accumulator_reconstruction_vs_board_ps": base._error_record(
                dw3_float_by_case[index][None, ...], board["tensors"]["dw3-output"][None, ...]),
            "dw7_int16_accumulator_reconstruction_vs_board_ps": base._error_record(
                dw7_float_by_case[index][None, ...], board["tensors"]["dw7-output"][None, ...]),
            "dw3_int64_raw_bounds": [int(raw3.min()), int(raw3.max())],
            "dw3_int32_raw_and_bias_fit": True,
            "dw7_int64_raw_bounds": [int(raw7.min()), int(raw7.max())],
            "dw7_int32_raw_and_bias_fit": True,
        })

    # Persist scale arrays and include their SHA identities in the manifest.
    scale_files = {}
    for filename, values in (("dw3-middle-int16-scale.f64", np.asarray([mid_scale])),
                             ("dw7-stage3-int16-scale.f64", np.asarray([dw7_scale])),
                             ("dw3-residual-int16-scale.f64", np.asarray([residual_scale])),
                             ("pre-dw3-int16-scale.f64", np.asarray([pre_scale]))):
        scale_files[filename] = _write(out, filename, values, "<f8")
    scale_files["dw3-int16-accumulator-scales.f64"] = \
        stage2_parameter_files["dw3"]["accumulator_scale_file"]
    scale_files["dw7-int16-accumulator-scales.f64"] = \
        stage2_parameter_files["dw7"]["accumulator_scale_file"]

    report = {
        "schema_version": 1,
        "status": "STAGE2_B_INT16_ACTIVATION_INT8_WEIGHT_CPU_ABLATION_NOT_PL",
        "base_int8_reference_manifest_sha256": BASE_MANIFEST_SHA256,
        "stage2_a_manifest_sha256": "6a5ff1e9eb8d2cad258851ed680eb99cdff912ec056b769ad53601f9d13d6785",
        "supersedes_previous_b_artifacts": [
            {"path": "stage2-dw3-dw7-int16act-005/manifest.json",
             "sha256": "7903c7a6b96001f0500d21726d8212ea88ef70a57f11875b5f5b3ce048a2f70a"},
            {"path": "stage2-dw3-dw7-int16act-006/manifest.json",
             "sha256": "2c81160bc2a7295788116e7ee2d67f9a8bce1017529b770deb771c496cec4d4c"}],
        "supersedes_reason": "freeze direct INT16-scale-specific DW3/DW7 INT32 biases, INT8 weights, per-channel scales, accumulator scales, and Q31 requant files for the JTAG ABI; earlier B outputs remain immutable historical evidence",
        "source_model_sha256": base.MODEL_SHA256,
        "split_manifest_sha256": base.SPLIT_MANIFEST_SHA256,
        "board_collection_manifest_sha256": base.COLLECTION_MANIFEST_SHA256,
        "host_dw7_allclose_failures_preserved": all(
            not case["tensors"]["dw7-output"]["comparison"][
                "allclose_rtol_1e-4_atol_1e-5"]
            for case in host_comparison["cases"]),
        "board_ps_is_authoritative": True, "pl_execution": False,
        "activation_quantization": {
            "dtype": "signed int16", "zero_point": 0, "rounding": "ties-to-even",
            "clip": [-32767, 32767], "weight_dtype": "signed int8",
            "weight_zero_point": 0, "weight_clip": [-127, 127],
            "scales": {"pre_dw3": pre_scale, "dw3_middle_to_dw7": mid_scale,
                       "dw7_to_stage3_pw128": dw7_scale,
                       "dw3_residual_to_stage3_add": residual_scale},
            "scale_files": scale_files,
        },
        "stage2_jtag_parameters": {
            "dw3": stage2_parameter_files["dw3"],
            "dw7": stage2_parameter_files["dw7"],
            "parameter_manifest_role": "this section is the unique B-authority for DW3/DW7 int8 weights and B-scale-specific int32 quantized biases; do not reuse stage2-dw3-dw7-int8-007 bias files",
            "independent_recompute_contract": "verify each i32 bias by ties-even round(FP32 pinned ONNX bias / (B input activation scale * B per-channel weight scale)); independently check INT32 range and file SHA",
        },
        "stage2_int32_accumulator_packet": {
            "one_physical_packet": True, "total_bytes": 1048576,
            "layout": "DW3 accumulator segment at offset 0, DW7 accumulator segment at offset 524288",
            "TLAST": "only final byte at offset 1048575", "segment_bytes": 524288,
            "dtype": "signed int32 little-endian", "bias_included": True,
            "dw3_reconstruction": "DW3 = int32 * (Spre16 * Sw3[ch]); per-channel accumulator scale in scale file",
            "dw7_reconstruction": "DW7 = int32 * (Smid16 * Sw7[ch]); per-channel accumulator scale in scale file",
            "DW3_middle_activation": "INT16 DW3 accumulator reconstruction requantized ties-even to Smid16 for DW7 input; no INT8 activation in B",
        },
        "int32_budget": {
            "dw3_depthwise_k9": _budget(layer_specs[0]["qweight"][:, 0, :, :].reshape((128, 9)),
                                         _bias_i32(layer_specs[0]["bias"], accscale3), 1),
            "dw7_depthwise_k49": _budget(layer_specs[1]["qweight"][:, 0, :, :].reshape((128, 49)),
                                          _bias_i32(layer_specs[1]["bias"], mid_scale * layer_specs[1]["weight_scale"]), 1),
            "stage3_pw128_to_384": stage3_contracts["fc1_pw128_to_384"]["int32_worst_case_budget"],
            "stage3_pw384_to_128": stage3_contracts["fc2_pw384_to_128"]["int32_worst_case_budget"],
            "reference_ceiling": "signed INT32 max 2147483647; theoretical PW384 reduction bound before bias is 384*32767*127 = 1597981056 (about 1.598G). Actual per-channel INT8 weight L1 bounds and quantized bias are calculated above.",
        },
        "stage3_int16_activation_int8_weight_recommendation": {
            "scales": {"pw128_input_dw7": dw7_scale, "gelu_output_pw384_input": gelu_scale,
                       "pw128_output_trace": fc1_out_scale},
            "operators": stage3_contracts,
            "full_32x32_real_activation_accumulator_checks": stage3_actual,
            "full_32x32_int16_activation_files": stage3_activation_files,
            "interpretation": "Full spatial 32x32 x 384 and x 128 reductions were exercised using real B DW7 INT16 input and B full-suffix GELU traces. Accumulation used int64 then checked raw plus bias against int32. These are quantization/overflow feasibility results, not end-to-end quantized feature claims.",
        },
        "results": stage2_records,
        "checks": {"full_shape_128x32x32": True, "three_real_ps_inputs": True,
                   "stage2_raw_and_bias_checked_in_int64_against_int32": True,
                   "stage2_bias_i32_recomputed_from_pinned_onnx_and_b_scales": True,
                   "stage2_q31_requant_params_are_b_scale_specific": True,
                   "stage3_pw_128_and_384_reductions_checked_on_all_1024_pixels": True,
                   "single_packet_final_tlast": True, "host_dw7_allclose_not_promoted": True,
                   "pl_execution": False},
    }
    report["files"] = {path.name: {"bytes": path.stat().st_size, "sha256": _sha(path)}
                       for path in sorted(out.iterdir()) if path.is_file()}
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                             encoding="utf-8")
    print(json.dumps({"output": str(out.resolve()), "manifest_sha256": _sha(manifest_path),
                      "results": [{"sample_id": r["sample_id"], "top1_changed": r["top1_changed"],
                                   "board_ps_top1": r["board_ps_top1"], "b_top1": r["b_top1"],
                                   "feature_error": r["feature_vs_pure_ps"]} for r in stage2_records],
                      "int32_budget": report["int32_budget"]}, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int8-007")
    parser.add_argument("--collection-dir", default="artifacts/board-debug-20261004/acceleration/network/stage2-dw3-dw7-ps-001")
    parser.add_argument("--split-manifest", default="artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-003/manifest.json")
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--board-feature-dir", default="artifacts/board-debug-20261004/network/runtime/board-runs")
    parser.add_argument("--text-features", default="artifacts/board-debug-20261004/host/s1-onnx-001/text-features.f32")
    parser.add_argument("--output", required=True)
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
