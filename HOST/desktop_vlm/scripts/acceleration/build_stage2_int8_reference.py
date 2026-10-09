"""Build a full-shape INT8 DW3->DW7 reference from actual board PS tensors.

This is a CPU-only independent integer model. Calibration uses the three
existing board collection tensors and is engineering evidence, not held-out
accuracy. The board's FP32 tensors remain authoritative for comparison.
"""
import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference

from integer_postops import gelu_lut, multiplier_shift, round_shift_even, requantize
from prepare_pointwise import error, quantize, sha, symmetric_scale


MODEL_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
SPLIT_MANIFEST_SHA256 = "bc02f542e5fdb58f440f851cdb76fe2bcb466f58fcb1f17c8de3f108d102132a"
COLLECTION_MANIFEST_SHA256 = "100a106ce7688223cc9e45dd459a2025174127395aeebef936a2f3b05cd06791"
HOST_COMPARISON_SHA256 = "c624d847eff2e70e49ab53d8b59402faa31a3c4a3deff90045bcdab4ab35de66"
DW3_NODE = "/image_encoder/model/network.2/network.2.0/token_mixer/reparam_conv/Conv"
DW7_NODE = "/image_encoder/model/network.2/network.2.0/convffn/conv/conv/Conv"
DW3_OUT = DW3_NODE + "_output_0"
DW7_OUT = DW7_NODE + "_output_0"
INPUTS = [
    ("image-00", "bb1d68f60f660ef824270dac40b0211df4c235d58944bafcc831845c17809e51"),
    ("image-01", "32693e16acc4ee99beef72f25546e3b19fbbc8fcdd0988df3884bc63da115c8d"),
    ("image-02", "eaec02ff7d4ac81ca3f3e01f88395f56bc8c997f8a224d721dff3dcad756c0e0"),
]
BOARD_FEATURES = [
    ("image-00-board.f32", "f6a0e6d361734116efd8b7e105e48e0d608aab5a3ba23536645142ee87f26fe9"),
    ("image-01-board.f32", "df5f942f6affab9edee7f6eab44a0f76d1f14ad2c814105562e39a11f0363e48"),
    ("image-02-board.f32", "818e3184bb66ea0bd897184d6c583d3109b119211da75496a4e71aa0a74ed70e"),
]
TEXT_SHA256 = "00be2a8375f38f6bb055be272047067fa0f090ae0877737929ef6678eed02fd9"
RUN_RECORDS = ["image-00-run.json", "pillow-eval-01-result.json", "pillow-eval-02-result.json"]


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _conv_attributes(node, kernel):
    attributes = {item.name: onnx.helper.get_attribute_value(item) for item in node.attribute}
    expected = {"group": 128, "kernel_shape": [kernel, kernel],
                "strides": [1, 1], "pads": [kernel // 2] * 4}
    for key, value in expected.items():
        actual = attributes.get(key, [0, 0, 0, 0] if key == "pads" else None)
        if isinstance(actual, (list, tuple)):
            actual = list(actual)
        if actual != value:
            raise ValueError("ONNX convolution contract mismatch for %s: %s" % (node.name, key))
    return expected


def _load_board_collection(collection_dir, split_manifest_path):
    collection_dir = Path(collection_dir)
    collection_path = collection_dir / "board-ps-collection-manifest.json"
    if _hash(collection_path) != COLLECTION_MANIFEST_SHA256:
        raise ValueError("actual board collection manifest SHA256 mismatch")
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    host_comparison_path = collection_dir / "verification.json"
    if _hash(host_comparison_path) != HOST_COMPARISON_SHA256:
        raise ValueError("pinned host-vs-board comparison report SHA256 mismatch")
    host_comparison = json.loads(host_comparison_path.read_text(encoding="utf-8"))
    if host_comparison.get("host_reference_role") != \
            "independent numerical comparison only; never the board golden":
        raise ValueError("host comparison provenance is not explicit")
    if any(case["tensors"]["dw7-output"]["comparison"][
            "allclose_rtol_1e-4_atol_1e-5"] for case in host_comparison["cases"]):
        raise ValueError("expected the three pinned host DW7 allclose checks to remain false")
    if collection.get("status") != "BOARD_PS_CPU_DW3_TO_DW7_COLLECTION":
        raise ValueError("input is not a board PS CPU collection")
    if collection.get("provenance", {}).get("pl_used") is not False:
        raise ValueError("board collection must explicitly state pl_used=false")
    if collection.get("source_model_sha256") != MODEL_SHA256:
        raise ValueError("board collection model SHA256 mismatch")
    if collection.get("split_manifest_sha256") != SPLIT_MANIFEST_SHA256:
        raise ValueError("board collection split manifest SHA256 mismatch")
    if _hash(split_manifest_path) != SPLIT_MANIFEST_SHA256:
        raise ValueError("stage2 split manifest SHA256 mismatch")
    split = json.loads(Path(split_manifest_path).read_text(encoding="utf-8"))
    if split.get("source_model", {}).get("sha256") != MODEL_SHA256:
        raise ValueError("split source model identity mismatch")
    if collection.get("stage_model_sha256") != {
            name: split["stages"][name]["sha256"] for name in ("prefix", "region")}:
        raise ValueError("board collector stage model identity mismatch")
    if len(collection.get("cases", [])) != 3:
        raise ValueError("board collection must have exactly three cases")
    records = []
    for index, ((sample_id, expected_input_sha), case) in enumerate(zip(INPUTS, collection["cases"])):
        if case.get("sample_id") != sample_id or case.get("input", {}).get("sha256") != expected_input_sha:
            raise ValueError("board collection input ordering/hash mismatch")
        tensors = {}
        for label, expected_tensor_name in (("pre-dw3", split["boundary"]["input_tensor"]),
                                            ("dw3-output", DW3_OUT), ("dw7-output", DW7_OUT)):
            item = case.get("files", {}).get(label, {})
            if item.get("tensor_name") != expected_tensor_name or item.get("dtype") != "<f4" or \
                    item.get("shape") != [1, 128, 32, 32] or item.get("bytes") != 524288:
                raise ValueError("board tensor contract mismatch for %s/%s" % (sample_id, label))
            path = collection_dir / item["path"]
            if _hash(path) != item.get("sha256") or path.stat().st_size != 524288:
                raise ValueError("board tensor SHA/size mismatch for %s/%s" % (sample_id, label))
            value = np.fromfile(str(path), dtype="<f4").reshape((1, 128, 32, 32))
            if not np.isfinite(value).all():
                raise ValueError("non-finite board tensor: %s/%s" % (sample_id, label))
            tensors[label] = value[0]
        records.append({"sample_id": sample_id, "input_sha256": expected_input_sha,
                        "board_files": {key: case["files"][key] for key in
                                        ("pre-dw3", "dw3-output", "dw7-output")},
                        "tensors": tensors})
    return collection, split, records, host_comparison


def _load_params(model_path):
    model = SymbolicShapeInference.infer_shapes(onnx.load(str(model_path)), auto_merge=True)
    nodes = {node.name: node for node in model.graph.node}
    initializers = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    specs = []
    for node_name, kernel in ((DW3_NODE, 3), (DW7_NODE, 7)):
        node = nodes.get(node_name)
        if node is None or node.op_type != "Conv":
            raise ValueError("missing pinned depthwise convolution: " + node_name)
        _conv_attributes(node, kernel)
        weight = np.asarray(initializers[node.input[1]], dtype=np.float32)
        bias = np.asarray(initializers[node.input[2]], dtype=np.float32)
        if weight.shape != (128, 1, kernel, kernel) or bias.shape != (128,):
            raise ValueError("depthwise parameter shape mismatch: " + node_name)
        scales = np.max(np.abs(weight.astype(np.float64)), axis=(1, 2, 3)) / 127.0
        scales = np.where(scales > 0, scales, 1.0)
        qweight = np.clip(np.rint(weight.astype(np.float64) / scales[:, None, None, None]),
                           -127, 127).astype(np.int8)
        specs.append({"node": node_name, "kernel": kernel, "weight": weight,
                      "bias": bias, "weight_scale": scales, "qweight": qweight,
                      "weight_name": node.input[1], "bias_name": node.input[2]})
    return model, specs


def _depthwise_accumulate(qinput, qweight):
    channels, height, width = qinput.shape
    _, _, kernel_h, kernel_w = qweight.shape
    pad_h, pad_w = kernel_h // 2, kernel_w // 2
    padded = np.pad(qinput.astype(np.int64), ((0, 0), (pad_h, pad_h), (pad_w, pad_w)),
                    mode="constant")
    accum = np.zeros((channels, height, width), dtype=np.int64)
    for ky in range(kernel_h):
        for kx in range(kernel_w):
            accum += (padded[:, ky:ky + height, kx:kx + width] *
                      qweight[:, 0, ky, kx].astype(np.int64)[:, None, None])
    return accum


def _requant_params(input_scale, weight_scales, output_scale, bias):
    acc_scales = input_scale * weight_scales
    bias64 = np.rint(bias.astype(np.float64) / acc_scales)
    i32 = np.iinfo(np.int32)
    if np.any(bias64 < i32.min) or np.any(bias64 > i32.max):
        raise OverflowError("quantized per-channel bias exceeds INT32")
    bias_q = bias64.astype(np.int32)
    coefficients = [multiplier_shift(float(scale / output_scale)) for scale in acc_scales]
    multipliers = np.asarray([item[0] for item in coefficients], dtype=np.int32)
    shifts = np.asarray([item[1] for item in coefficients], dtype=np.int32)
    represented = multipliers.astype(np.float64) / np.exp2(shifts.astype(np.float64))
    return bias_q, multipliers, shifts, represented, acc_scales


def _checked_q31(accum, bias_q, multiplier, shift):
    i32 = np.iinfo(np.int32)
    if np.any(accum < i32.min) or np.any(accum > i32.max):
        raise OverflowError("raw depthwise INT64 accumulation does not fit INT32")
    with_bias = accum + bias_q.astype(np.int64)[:, None, None]
    if np.any(with_bias < i32.min) or np.any(with_bias > i32.max):
        raise OverflowError("depthwise INT32 accumulator plus quantized bias overflow")
    q = requantize(with_bias.transpose(1, 2, 0), np.zeros(128, dtype=np.int32),
                   multiplier, shift).transpose(2, 0, 1)
    return with_bias, q


def _round_reference(accum_with_bias, ratio):
    rounded = np.rint(accum_with_bias.astype(np.float64) * ratio[:, None, None])
    return np.clip(rounded, -127, 127).astype(np.int8)


def _write_array(out, filename, array, dtype):
    path = out / filename
    packed = np.ascontiguousarray(array, dtype=dtype)
    packed.tofile(str(path))
    return {"path": filename, "shape": list(packed.shape), "dtype": dtype,
            "bytes": path.stat().st_size, "sha256": _hash(path)}


def _error_record(actual, expected):
    result = error(actual, expected)
    result["rms_abs"] = result["rmse"]
    result["allclose_rtol_1e-4_atol_1e-5"] = bool(np.allclose(
        actual, expected, rtol=1e-4, atol=1e-5))
    return result


def _read_board_run_identity(path, index):
    raw = Path(path).read_text(encoding="utf-8")
    if index == 0:
        outer = json.loads(raw)
        stdout = outer.get("stdout", "")
        match = re.search(r"OUTPUT_SHA256=([0-9a-f]{64})", stdout)
        if not match:
            raise ValueError("image-00 board run is missing its output SHA256")
        lines = [line for line in stdout.splitlines() if line.startswith("{")]
        records = []
        for line in lines:
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
        result = next((item for item in records if "cosine_scores" in item), None)
        runtime = next((item for item in records if item.get("ort_version")), None)
        if result is None or runtime is None:
            raise ValueError("image-00 board run lacks feature or runtime record")
        return {"output_sha256": match.group(1), "input_sha256": None,
                "model_sha256": None, "text_features_sha256": None,
                "scores_by_id": None, "cosine_scores": result["cosine_scores"],
                "ranking": result["ranking"], "runtime": runtime,
                "source": str(path)}
    result = json.loads(raw)
    return {"output_sha256": result["output_sha256"],
            "input_sha256": result["input_sha256"],
            "model_sha256": result["model_sha256"],
            "text_features_sha256": result["text_features_sha256"],
            "scores_by_id": {item["id"]: item["score"] for item in result["ranking"]},
            "cosine_scores": None,
            "ranking": [item["id"] for item in result["ranking"]],
            "runtime": result["runtime"], "source": str(path)}


def _export_stage3_abi(model, trace_records, output_dir, dw7_input_scale,
                       dw3_residual_scale):
    fc1_name = "/image_encoder/model/network.2/network.2.0/convffn/fc1/Conv"
    fc2_name = "/image_encoder/model/network.2/network.2.0/convffn/fc2/Conv"
    layer_scale_node_name = "/image_encoder/model/network.2/network.2.0/Mul"
    nodes = {node.name: node for node in model.graph.node}
    initializers = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    fc1, fc2 = nodes[fc1_name], nodes[fc2_name]
    w1 = np.asarray(initializers[fc1.input[1]], dtype=np.float32)
    w2 = np.asarray(initializers[fc2.input[1]], dtype=np.float32)
    b1 = np.asarray(initializers[fc1.input[2]], dtype=np.float32)
    b2 = np.asarray(initializers[fc2.input[2]], dtype=np.float32)
    if w1.shape != (384, 128, 1, 1) or w2.shape != (128, 384, 1, 1):
        raise ValueError("stage3 pointwise hotspot shape differs from real 128->384->128 model")
    fc1_trace_node = fc1_name
    gelu_trace_node = "/image_encoder/model/network.2/network.2.0/convffn/act/Mul_1"
    fc2_trace_node = fc2_name
    traces = {name: [record["trace_tensors"][trace_node]
                     for record in trace_records]
              for name, trace_node in (("fc1", fc1_trace_node),
                                       ("gelu", gelu_trace_node),
                                       ("fc2", fc2_trace_node))}
    scale_fc1_out = float(symmetric_scale(np.asarray([
        np.max(np.abs(item.astype(np.float64))) for item in traces["fc1"]], dtype=np.float64)))
    scale_gelu_out = float(symmetric_scale(np.asarray([
        np.max(np.abs(item.astype(np.float64))) for item in traces["gelu"]], dtype=np.float64)))
    scale_fc2_out = float(symmetric_scale(np.asarray([
        np.max(np.abs(item.astype(np.float64))) for item in traces["fc2"]], dtype=np.float64)))
    layer_scale = np.asarray(initializers[
        next(name for name in nodes[layer_scale_node_name].input if name in initializers)],
        dtype=np.float32).reshape(-1)
    if layer_scale.shape != (128,):
        raise ValueError("network.2.0 layer-scale shape must be 128")

    stage3_records = {}
    for name, weight, bias, scale_in, scale_out in (
            ("fc1", w1, b1, dw7_input_scale, scale_fc1_out),
            ("fc2", w2, b2, scale_gelu_out, scale_fc2_out)):
        matrix_kn = weight[:, :, 0, 0].T.copy()
        scales = np.max(np.abs(matrix_kn.astype(np.float64)), axis=0) / 127.0
        scales = np.where(scales > 0, scales, 1.0)
        qweight_kn = np.clip(np.rint(matrix_kn.astype(np.float64) / scales[None, :]),
                             -127, 127).astype(np.int8)
        bias_q, multipliers, shifts, represented, accum_scales = _requant_params(
            scale_in, scales, scale_out, bias)
        weight_path = output_dir / ("stage3-%s-weights-kn.i8" % name)
        scale_path = output_dir / ("stage3-%s-weight-scales.f64" % name)
        bias_path = output_dir / ("stage3-%s-bias.i32" % name)
        multiplier_path = output_dir / ("stage3-%s-requant-multiplier.i32" % name)
        shift_path = output_dir / ("stage3-%s-requant-shift.i32" % name)
        accum_scale_path = output_dir / ("stage3-%s-accumulator-scales.f64" % name)
        for path, array, dtype in (
                (weight_path, qweight_kn, "|i1"), (scale_path, scales, "<f8"),
                (bias_path, bias_q, "<i4"), (multiplier_path, multipliers, "<i4"),
                (shift_path, shifts, "<i4"), (accum_scale_path, accum_scales, "<f8")):
            np.asarray(array, dtype=dtype).tofile(str(path))
        stage3_records[name] = {
            "onnx_node": fc1_name if name == "fc1" else fc2_name,
            "onnx_weight_shape": list(weight.shape), "weight_kn_shape": list(qweight_kn.shape),
            "input_scale": scale_in, "output_scale": scale_out,
            "weight_scale_granularity": "per output channel (N), symmetric zero-point=0",
            "bias_rule": "int32 round-to-nearest-ties-even(bias/(input_scale*weight_scale))",
            "requant_rule": "Q31 multiplier / 2**shift, signed round-shift-even, saturate [-127,127]",
            "files": {path.name: {"bytes": path.stat().st_size, "sha256": _hash(path)}
                      for path in (weight_path, scale_path, bias_path,
                                   multiplier_path, shift_path, accum_scale_path)},
            "q31_ratio_max_abs_error": float(np.max(np.abs(
                represented - scale_in * scales / scale_out))),
        }
    gelu_path = output_dir / "stage3-gelu-lut.i8"
    table = gelu_lut(scale_fc1_out, scale_gelu_out)
    table.tofile(str(gelu_path))
    layer_scale_path = output_dir / "stage3-layer-scale.f32"
    layer_scale.astype("<f4").tofile(str(layer_scale_path))
    stage3_records["gelu"] = {
        "input_scale": scale_fc1_out, "output_scale": scale_gelu_out,
        "lut_contract": "256 entries; index is uint8 reinterpretation of signed int8; zero-point=0",
        "file": {"path": gelu_path.name, "bytes": gelu_path.stat().st_size,
                 "sha256": _hash(gelu_path)},
    }
    stage3_records["layer_scale_and_residual"] = {
        "layer_scale_shape": list(layer_scale.shape), "layer_scale_dtype": "<f4",
        "layer_scale_file": {"path": layer_scale_path.name,
                             "bytes": layer_scale_path.stat().st_size,
                             "sha256": _hash(layer_scale_path)},
        "residual_source": DW3_OUT, "residual_activation_scale": dw3_residual_scale,
        "residual_zero_point": 0,
        "suggestion": "keep layer-scale multiply and residual add in FP32 initially; q3 remains the DW3 bypass",
    }
    return {
        "network_scope": "MobileCLIP-S1 image_encoder.model.network.2.network.2.0/convffn",
        "shape_source": "all 128x32x32 actual-board input cases passed through the full host CPU suffix; no spatial truncation",
        "hotspot_shapes": {
            "pw128_to_384": [1, 128, 32, 32],
            "pw128_to_384_weight": list(w1.shape),
            "gelu_input_output": [1, 384, 32, 32],
            "pw384_to_128_weight": list(w2.shape),
            "pw384_to_128_output": [1, 128, 32, 32],
            "layer_scale": [128], "residual_add_output": [1, 128, 32, 32],
        },
        "activation_scales": {"input_from_dw7": dw7_input_scale,
                              "fc1_output_and_gelu_input": scale_fc1_out,
                              "gelu_output_and_fc2_input": scale_gelu_out,
                              "fc2_output": scale_fc2_out,
                              "residual_from_dw3": dw3_residual_scale},
        "parameters_and_abi": stage3_records,
        "note": "Scales are calibrated on these three old inputs and the actual PS stage2 boundary values; no held-out accuracy claim.",
    }


def _save_suffix_and_features(model, params, records, out, text_features,
                              board_feature_dir, board_run_dir, threads):
    extractor = onnx.utils.Extractor(model)
    suffix = extractor.extract_model([DW3_OUT, DW7_OUT], ["features"])
    trace_nodes = [
        "/image_encoder/model/network.2/network.2.0/convffn/fc1/Conv",
        "/image_encoder/model/network.2/network.2.0/convffn/act/Mul_1",
        "/image_encoder/model/network.2/network.2.0/convffn/fc2/Conv",
        "/image_encoder/model/network.2/network.2.0/Mul",
        "/image_encoder/model/network.2/network.2.0/Add",
    ]
    node_by_name = {node.name: node for node in model.graph.node}
    trace_names = [node_by_name[name].output[0] for name in trace_nodes]
    value_info = {item.name: item for item in
                  list(model.graph.value_info) + list(model.graph.output)}
    del suffix.graph.output[:]
    suffix.graph.output.extend([value_info["features"]] + [value_info[name] for name in trace_names])
    onnx.checker.check_model(suffix)
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    ort.disable_telemetry_events()
    session = ort.InferenceSession(suffix.SerializeToString(), options,
                                   providers=["CPUExecutionProvider"])
    result_records, trace_records = [], []
    prompts = json.loads(Path("artifacts/board-debug-20261004/host/s1-onnx-001/manifest.json")
                         .read_text(encoding="utf-8"))["prompts"]
    ids = [item["id"] for item in prompts]
    text_unit = text_features.astype(np.float64)
    text_unit /= np.maximum(np.linalg.norm(text_unit, axis=1, keepdims=True), 1e-30)
    for index, record in enumerate(records):
        feeds_board = {DW3_OUT: record["tensors"]["dw3-output"][None, ...],
                       DW7_OUT: record["tensors"]["dw7-output"][None, ...]}
        board_suffix_values = session.run(None, feeds_board)
        pure_host_suffix = board_suffix_values[0]
        board_stage3_traces = dict(zip(trace_nodes, board_suffix_values[1:]))
        # Stage 3 uses the DW3 residual and the DW7 activation as its two real inputs.
        feeds_quant = {DW3_OUT: params[0]["dw3_dequant"][index],
                       DW7_OUT: params[1]["q7_dequant"][index:index + 1]}
        feeds_quant[DW3_OUT] = params[0]["dw3_dequant"][index:index + 1]
        quantized_features = session.run(["features"], feeds_quant)[0]
        baseline_name, expected_hash = BOARD_FEATURES[index]
        board_path = board_feature_dir / baseline_name
        if _hash(board_path) != expected_hash:
            raise ValueError("pure PS 512 feature SHA mismatch: " + str(board_path))
        board_run_path = board_run_dir / RUN_RECORDS[index]
        board_run = _read_board_run_identity(board_run_path, index)
        if board_run["output_sha256"] != expected_hash:
            raise ValueError("pure PS run record output SHA differs from feature file")
        if index and (board_run["input_sha256"] != record["input_sha256"] or
                      board_run["model_sha256"] != MODEL_SHA256 or
                      board_run["text_features_sha256"] != TEXT_SHA256):
            raise ValueError("pure PS run record model/input/text identity mismatch")
        board_features = np.fromfile(str(board_path), dtype="<f4").reshape((1, 512))
        def cosine_scores(features):
            image_unit = features.astype(np.float64)
            image_unit /= max(float(np.linalg.norm(image_unit)), 1e-30)
            return image_unit @ text_unit.T
        board_scores = cosine_scores(board_features)
        host_scores = cosine_scores(pure_host_suffix)
        quant_scores = cosine_scores(quantized_features)
        def ranking(scores):
            return [ids[int(i)] for i in np.argsort(-scores.reshape(-1), kind="stable")]
        if board_run["cosine_scores"] is None:
            saved_board_scores = [board_run["scores_by_id"][item] for item in ids]
        else:
            saved_board_scores = board_run["cosine_scores"]
        files = {
            "board_ps_features": _write_array(out, "image-%02d-board-ps-features.f32" % index,
                                               board_features, "<f4"),
            "host_suffix_on_board_dw_outputs": _write_array(
                out, "image-%02d-host-float-suffix-features.f32" % index,
                pure_host_suffix, "<f4"),
            "quantized_stage2_features": _write_array(
                out, "image-%02d-int8-stage2-suffix-features.f32" % index,
                quantized_features, "<f4"),
        }
        trace_files = {}
        for trace_name, array in board_stage3_traces.items():
            short_name = trace_name.rsplit("/", 1)[-1].replace(".", "-")
            filename = "%s-float-stage3-%s.f32" % (record["sample_id"], short_name)
            trace_files[trace_name] = _write_array(out, filename, array, "<f4")
        trace_records.append({"sample_id": record["sample_id"],
                              "trace_tensors": board_stage3_traces,
                              "files": trace_files})
        result_records.append({
            "sample_id": record["sample_id"],
            "input_sha256": record["input_sha256"],
            "pure_ps_feature_source": {"path": str(board_path),
                                       "sha256": expected_hash,
                                       "board_run_record": str(board_run_path),
                                       "runtime": board_run["runtime"]},
            "files": files,
            "host_float_suffix_vs_pure_ps": _error_record(pure_host_suffix, board_features),
            "quantized_suffix_vs_pure_ps": _error_record(quantized_features, board_features),
            "quantized_suffix_vs_host_float_suffix": _error_record(
                quantized_features, pure_host_suffix),
            "text_similarity": {
                "text_features_sha256": TEXT_SHA256,
                "board_ps_scores": board_scores.reshape(-1).tolist(),
                "board_ps_run_record_scores": saved_board_scores,
                "recomputed_board_scores_max_abs_diff": float(np.max(np.abs(
                    board_scores.reshape(-1) - np.asarray(saved_board_scores, dtype=np.float64)))),
                "recomputed_board_rank_matches_run_record": ranking(board_scores) == board_run["ranking"],
                "host_float_suffix_scores": host_scores.reshape(-1).tolist(),
                "int8_stage2_scores": quant_scores.reshape(-1).tolist(),
                "board_ps_ranking": ranking(board_scores),
                "host_float_suffix_ranking": ranking(host_scores),
                "int8_stage2_ranking": ranking(quant_scores),
                "int8_rank_matches_pure_ps": ranking(quant_scores) == ranking(board_scores),
            },
        })
    suffix_sha256 = hashlib.sha256(suffix.SerializeToString()).hexdigest()
    return result_records, trace_records, suffix_sha256


def build(args):
    model_path = Path(args.model)
    if _hash(model_path) != MODEL_SHA256:
        raise ValueError("source ONNX model SHA256 mismatch")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    collection, split, records, host_comparison = _load_board_collection(
        args.collection_dir, args.split_manifest)
    model, layers = _load_params(model_path)

    # Symmetric activation scales are calibrated only from these three real PS tensors.
    input_scale = float(symmetric_scale(np.asarray([
        np.max(np.abs(item["tensors"]["pre-dw3"].astype(np.float64)))
        for item in records], dtype=np.float64)))
    dw3_scale = float(symmetric_scale(np.asarray([
        np.max(np.abs(item["tensors"]["dw3-output"].astype(np.float64)))
        for item in records], dtype=np.float64)))
    dw7_scale = float(symmetric_scale(np.asarray([
        np.max(np.abs(item["tensors"]["dw7-output"].astype(np.float64)))
        for item in records], dtype=np.float64)))

    parameter_records = {}
    for layer in layers:
        kernel = layer["kernel"]
        weight_q_path = out / ("dw%d-weights-chw.i8" % kernel)
        layer["qweight"].tofile(str(weight_q_path))
        scale_path = out / ("dw%d-weight-scales.f64" % kernel)
        np.asarray(layer["weight_scale"], dtype="<f8").tofile(str(scale_path))
        bias_path = out / ("dw%d-bias.f32" % kernel)
        np.asarray(layer["bias"], dtype="<f4").tofile(str(bias_path))
        parameter_records["dw%d" % kernel] = {
            "onnx_node": layer["node"], "weight_initializer": layer["weight_name"],
            "bias_initializer": layer["bias_name"],
            "weight_float_shape": list(layer["weight"].shape),
            "weight_int8_shape": list(layer["qweight"].shape),
            "weight_scale": {"path": scale_path.name, "shape": [128], "dtype": "<f8",
                             "sha256": _hash(scale_path)},
            "quantized_weight": {"path": weight_q_path.name,
                                 "shape": list(layer["qweight"].shape), "dtype": "|i1",
                                 "sha256": _hash(weight_q_path)},
            "float_bias": {"path": bias_path.name, "shape": [128], "dtype": "<f4",
                           "sha256": _hash(bias_path)},
            "quantization": "symmetric per-output-channel, zero-point=0, ties-even, clip[-127,127]",
        }

    per_sample = []
    output_records = {}
    layer_stats = {"dw3": {"bias": None, "multiplier": None},
                   "dw7": {"bias": None, "multiplier": None}}
    for index, record in enumerate(records):
        stem = record["sample_id"]
        pre = record["tensors"]["pre-dw3"]
        ps_dw3 = record["tensors"]["dw3-output"]
        ps_dw7 = record["tensors"]["dw7-output"]
        qinput = quantize(pre, input_scale)
        raw3 = _depthwise_accumulate(qinput, layers[0]["qweight"])
        bias3, mult3, shift3, represented3, acc_scale3 = _requant_params(
            input_scale, layers[0]["weight_scale"], dw3_scale, layers[0]["bias"])
        total3, q3 = _checked_q31(raw3, bias3, mult3, shift3)
        q3_dequant = (q3.astype(np.float64) * dw3_scale).astype("<f4")[None, ...]
        raw7 = _depthwise_accumulate(q3, layers[1]["qweight"])
        bias7, mult7, shift7, represented7, acc_scale7 = _requant_params(
            dw3_scale, layers[1]["weight_scale"], dw7_scale, layers[1]["bias"])
        total7, q7 = _checked_q31(raw7, bias7, mult7, shift7)
        dw7_accum_dequant = (total7.astype(np.float64) * acc_scale7[:, None, None]).astype("<f4")[None, ...]
        q7_dequant = (q7.astype(np.float64) * dw7_scale).astype("<f4")[None, ...]
        float_ref_q3 = _round_reference(total3, input_scale * layers[0]["weight_scale"] / dw3_scale)
        float_ref_q7 = _round_reference(total7, dw3_scale * layers[1]["weight_scale"] / dw7_scale)

        if "bias_q" not in layer_stats["dw3"]:
            for name, vals in (("dw3", (bias3, mult3, shift3, represented3, acc_scale3)),
                               ("dw7", (bias7, mult7, shift7, represented7, acc_scale7))):
                layer_stats[name] = {"bias_q": bias3 if name == "dw3" else bias7,
                                     "multiplier": vals[1], "shift": vals[2],
                                     "represented_ratio": vals[3], "accumulator_scale": vals[4]}
        arrays = {
            "pre-dw3-quant.i8": (qinput, "|i1"),
            "dw3-accum-i64-check.i64": (raw3, "<i8"),
            "dw3-with-bias.i32": (total3, "<i4"),
            "dw3-output.i8": (q3, "|i1"),
            "dw3-dequant.f32": (q3_dequant, "<f4"),
            "dw7-accum-i64-check.i64": (raw7, "<i8"),
            "dw7-with-bias.i32": (total7, "<i4"),
            "dw7-accum-dequant.f32": (dw7_accum_dequant, "<f4"),
            "dw7-output.i8": (q7, "|i1"),
            "dw7-dequant.f32": (q7_dequant, "<f4"),
        }
        file_records = {}
        for label, (array, dtype) in arrays.items():
            filename = "%s-%s" % (stem, label)
            file_records[label] = _write_array(out, filename, array, dtype)
            output_records[filename] = file_records[label]
        # The stage2 cut exposes both the DW3 residual and DW7 activation.
        # Keep two packet payloads concatenated in a single file for deterministic
        # host/JTAG handoff; each tensor packet remains contiguous NCHW.
        dual_packet_path = out / (stem + "-stage2-dual-output-packet.i8")
        with dual_packet_path.open("wb") as packet:
            packet.write(np.asarray(q3, dtype="|i1").tobytes(order="C"))
            packet.write(np.asarray(q7, dtype="|i1").tobytes(order="C"))
        dual_packet = {
            "path": dual_packet_path.name, "bytes": dual_packet_path.stat().st_size,
            "sha256": _hash(dual_packet_path), "dtype": "signed int8",
            "byte_order": "little-endian (one-byte elements; byte order is identity)",
            "layout": "packet0 DW3 NCHW contiguous, immediately followed by packet1 DW7 NCHW contiguous",
            "packets": [
                {"index": 0, "tensor": DW3_OUT, "shape": [1, 128, 32, 32],
                 "offset_bytes": 0, "bytes": 131072, "scale": dw3_scale,
                 "zero_point": 0, "range": [-127, 127], "tlast": "assert on byte 131071"},
                {"index": 1, "tensor": DW7_OUT, "shape": [1, 128, 32, 32],
                 "offset_bytes": 131072, "bytes": 131072, "scale": dw7_scale,
                 "zero_point": 0, "range": [-127, 127], "tlast": "assert on byte 262143"},
            ],
            "frame_relation": "both packets belong to the same input frame/sample_id; packet_index distinguishes DW3 residual from DW7 activation",
            "note": "DW3 remains internally directly connected to DW7 in PL; this packet exposes the requantized DW3 value only for stage3 residual reconstruction/debug and exposes requantized DW7 for the next stage.",
        }
        file_records["stage2_dual_output_packet"] = dual_packet
        output_records[dual_packet_path.name] = dual_packet
        ps_dw3_batched, ps_dw7_batched = ps_dw3[None, ...], ps_dw7[None, ...]
        per_sample.append({
            "sample_id": stem, "input_sha256": record["input_sha256"],
            "actual_board_ps_tensors": record["board_files"],
            "files": file_records,
            "dw3_requantized_value_is_stage3_residual_source": True,
            "dw7_requantized_value_is_stage3_main_input": True,
            "qinput_saturation_count": int(np.count_nonzero(np.abs(qinput.astype(np.int16)) == 127)),
            "dw3": {
                "raw_accum_int64_minmax": [int(raw3.min()), int(raw3.max())],
                "raw_accum_fits_int32": bool(raw3.min() >= np.iinfo(np.int32).min and
                                              raw3.max() <= np.iinfo(np.int32).max),
                "accum_plus_bias_fits_int32": True,
                "bias_q_range": [int(bias3.min()), int(bias3.max())],
                "q31_multiply_rounding_differs_from_fp64_reference": int(np.count_nonzero(q3 != float_ref_q3)),
                "output_saturation_count": int(np.count_nonzero(np.abs(q3.astype(np.int16)) == 127)),
                "dequant_vs_actual_board_ps": _error_record(q3_dequant, ps_dw3_batched),
            },
            "dw7": {
                "raw_accum_int64_minmax": [int(raw7.min()), int(raw7.max())],
                "raw_accum_fits_int32": bool(raw7.min() >= np.iinfo(np.int32).min and
                                              raw7.max() <= np.iinfo(np.int32).max),
                "accum_plus_bias_fits_int32": True,
                "bias_q_range": [int(bias7.min()), int(bias7.max())],
                "q31_multiply_rounding_differs_from_fp64_reference": int(np.count_nonzero(q7 != float_ref_q7)),
                "accumulator_dequant_vs_actual_board_ps": _error_record(
                    dw7_accum_dequant, ps_dw7_batched),
                "requant_output_saturation_count": int(np.count_nonzero(np.abs(q7.astype(np.int16)) == 127)),
                "requant_dequant_vs_actual_board_ps": _error_record(q7_dequant, ps_dw7_batched),
            },
        })
        # Stash arrays for the final original FP32 suffix boundary.
        layers[0].setdefault("dw3_dequant", []).append(q3_dequant)
        layers[1].setdefault("q7_dequant", []).append(q7_dequant)

    layers[0]["dw3_dequant"] = np.concatenate(layers[0]["dw3_dequant"], axis=0)
    layers[1]["q7_dequant"] = np.concatenate(layers[1]["q7_dequant"], axis=0)
    text_path = Path(args.text_features)
    if _hash(text_path) != TEXT_SHA256:
        raise ValueError("8-candidate text feature SHA256 mismatch")
    text_features = np.fromfile(str(text_path), dtype="<f4").reshape((8, 512))
    board_dir = Path(args.board_feature_dir)
    board_run_dir = Path(args.board_run_dir)
    # Assign per-case suffix feeds in index order; all features are computed on CPU host ORT.
    feature_records, trace_records, suffix_sha256 = _save_suffix_and_features(
        model, layers, records, out,
        text_features, board_dir, board_run_dir, args.threads)
    stage3_abi = _export_stage3_abi(model, trace_records, out,
                                    dw7_input_scale=dw7_scale,
                                    dw3_residual_scale=dw3_scale)
    del trace_records

    multiplier_files = {}
    for name, field in (("dw3", "dw3"), ("dw7", "dw7")):
        stat = layer_stats[name]
        for suffix, array in (("bias.i32", stat["bias_q"]),
                              ("requant-multiplier.i32", stat["multiplier"]),
                              ("requant-shift.i32", stat["shift"]),
                              ("requant-ratio.f64", stat["represented_ratio"]),
                              ("accumulator-scale.f64", stat["accumulator_scale"])):
            filename = name + "-" + suffix
            dtype = "<f8" if array.dtype.kind == "f" else "<i4"
            record = _write_array(out, filename, array, dtype)
            multiplier_files[filename] = record
            output_records[filename] = record
    dw3_bias_q = layer_stats["dw3"]["bias_q"]
    dw7_bias_q = layer_stats["dw7"]["bias_q"]
    del dw3_bias_q, dw7_bias_q
    # No suffix ONNX is exported: it is reconstructed from the pinned source model per run.
    report = {
        "schema_version": 1,
        "status": "STAGE2_INT8_CPU_REFERENCE_FROM_ACTUAL_BOARD_PS_TENSORS_NOT_PL",
        "source_model_sha256": MODEL_SHA256,
        "split_manifest_sha256": SPLIT_MANIFEST_SHA256,
        "board_collection_manifest_sha256": COLLECTION_MANIFEST_SHA256,
        "host_comparison_report": {
            "path": str(Path(args.collection_dir) / "verification.json"),
            "sha256": HOST_COMPARISON_SHA256,
            "role": host_comparison["host_reference_role"],
            "dw7_allclose_by_sample": {
                case["sample_id"]: case["tensors"]["dw7-output"]["comparison"]
                for case in host_comparison["cases"]},
            "failures_preserved": True,
        },
        "board_ps_collection_status": collection["status"],
        "board_ps_provenance": collection["provenance"],
        "actual_board_outputs_are_authoritative": True,
        "host_ort_is_independent_comparison_only": True,
        "input_identity": [
            {"sample_id": item["sample_id"], "sha256": item["input_sha256"],
             "pre_dw3_sha256": item["actual_board_ps_tensors"]["pre-dw3"]["sha256"],
             "dw3_output_sha256": item["actual_board_ps_tensors"]["dw3-output"]["sha256"],
             "dw7_output_sha256": item["actual_board_ps_tensors"]["dw7-output"]["sha256"]}
            for item in per_sample],
        "calibration": {
            "method": "per-tensor max-abs/127 using exactly the three board PS tensors; engineering-only, no held-out accuracy",
            "activation_scales": {"pre_dw3": input_scale, "dw3_to_dw7": dw3_scale,
                                  "dw7_to_stage3": dw7_scale},
            "weight_scales": "symmetric per output channel from pinned ONNX FP32 weights",
            "bias": "int32 per output channel; round-to-nearest-ties-even(bias/(input_scale*weight_scale))",
            "zero_points": {"activation": 0, "weights": 0},
            "signed_int8_range": [-127, 127],
            "rounding": "ties-to-even; conv requant uses positive Q31 multiplier and round-shift-even",
            "multiplier_error_max_abs": {
                "dw3": float(np.max(np.abs(layer_stats["dw3"]["represented_ratio"] -
                                           input_scale * layers[0]["weight_scale"] / dw3_scale))),
                "dw7": float(np.max(np.abs(layer_stats["dw7"]["represented_ratio"] -
                                           dw3_scale * layers[1]["weight_scale"] / dw7_scale))),
            },
        },
        "operators": {
            "dw3": {"kernel": [3, 3], "groups": 128, "stride": [1, 1], "pad": [1, 1],
                    "input_shape_chw": [128, 32, 32], "output_shape_chw": [128, 32, 32],
                    "parameters": parameter_records["dw3"],
                    "accumulator": "signed INT32 result; accumulated independently in INT64; bias included in checked INT64 then checked INT32",
                    "requant": "per-output-channel Q31 ratio (Spre*Sw3/Smid), ties-even, saturate int8 [-127,127]"},
            "dw7": {"kernel": [7, 7], "groups": 128, "stride": [1, 1], "pad": [3, 3],
                    "input_shape_chw": [128, 32, 32], "output_shape_chw": [128, 32, 32],
                    "parameters": parameter_records["dw7"],
                    "accumulator": "signed INT32 result; accumulated independently in INT64; bias included in checked INT64 then checked INT32",
                    "requant": "per-output-channel Q31 ratio (Smid*Sw7/Sout), ties-even, saturate int8 [-127,127]"},
        },
        "stage3_handoff": {
            "next_node": "/image_encoder/model/network.2/network.2.0/convffn/fc1/Conv",
            "pw_input_channels": 128, "pw_output_channels": 384,
            "input_shape": [1, 128, 32, 32], "dtype": "signed int8",
            "activation_scale": dw7_scale, "zero_point": 0, "range": [-127, 127],
            "network2_block0_residual": "DW3 output q3 is packet0 and its PS suffix reconstruction MUST use q3*DW3_scale returned by PL; do not use original board FP32 DW3 or host float intermediates. Add q3-dequant residual after PW384->128 and layer-scale.",
            "suggested_abi": "cut returns packet0 q3 (DW3 residual) and packet1 q7 (DW7 main input), each [1,128,32,32] signed int8 NCHW; internally DW3 remains directly connected to DW7. q7 feeds PW128x384; carry q3 for final residual. Expose optional raw INT32 debug taps separately, never as stage3 activation.",
            "dual_output_packet_contract": {
                "file_order": ["DW3 q3 packet", "DW7 q7 packet"],
                "packet_dtype": "signed int8, one byte per element, little-endian byte stream",
                "packet_shape": [1, 128, 32, 32], "packet_bytes": 131072,
                "frame_relation": "two ordered packets share one frame_id/sample_id",
                "tlast": "one TLAST per tensor packet: after byte 131071 for DW3 and after byte 262143 for DW7 in concatenated packet file; TLAST does not replace shared frame_id/packet_index metadata",
                "scales": {"dw3_q3": dw3_scale, "dw7_q7": dw7_scale},
                "zero_points": {"dw3_q3": 0, "dw7_q7": 0},
                "range": [-127, 127],
            },
        },
        "stage3_real_shape_quantization_abi": stage3_abi,
        "results": per_sample,
        "final_feature_results": feature_records,
        "suffix_model": {"source_model_sha256": MODEL_SHA256,
                         "ephemeral_model_sha256": suffix_sha256,
                         "input_tensors": [DW3_OUT, DW7_OUT], "output": "features",
                         "runtime": ort.__version__, "threads": args.threads,
                         "host_float_suffix_is_actual_board_run": False},
        "pure_ps_feature_references": {
            "text_features_sha256": TEXT_SHA256,
            "files": [{"path": name, "sha256": digest} for name, digest in BOARD_FEATURES],
        },
        "files": {path.name: {"bytes": path.stat().st_size, "sha256": _hash(path)}
                  for path in sorted(out.iterdir()) if path.is_file()},
        "checks": {"all_board_collection_files_sha_verified": True,
                   "all_source_identities_pinned": True,
                   "int64_accumulators_checked_before_int32": True,
                   "bias_addition_checked_for_int32_overflow": True,
                   "host_allclose_failures_preserved_as_failures": True,
                   "pl_execution": False, "full_accuracy_claim": False},
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                        sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out.resolve()),
                      "manifest_sha256": _hash(manifest_path),
                      "status": report["status"],
                      "activation_scales": report["calibration"]["activation_scales"],
                      "results": [{"sample_id": item["sample_id"],
                                   "dw3_error": item["dw3"]["dequant_vs_actual_board_ps"],
                                   "dw7_error": item["dw7"]["accumulator_dequant_vs_actual_board_ps"],
                                   "feature_error": item2["quantized_suffix_vs_pure_ps"],
                                   "rank_match": item2["text_similarity"]["int8_rank_matches_pure_ps"]}
                                  for item, item2 in zip(per_sample, feature_records)]},
                     indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--collection-dir", default="artifacts/board-debug-20261004/acceleration/network/stage2-dw3-dw7-ps-001")
    parser.add_argument("--split-manifest", default="artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-003/manifest.json")
    parser.add_argument("--board-feature-dir", default="artifacts/board-debug-20261004/network/runtime/board-runs")
    parser.add_argument("--board-run-dir", default="artifacts/board-debug-20261004/network/runtime/board-runs")
    parser.add_argument("--text-features", default="artifacts/board-debug-20261004/host/s1-onnx-001/text-features.f32")
    parser.add_argument("--output", required=True)
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    build(parser.parse_args())


if __name__ == "__main__":
    main()
