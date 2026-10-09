"""Build a generic network.2 INT16-activation/INT8-weight CPU oracle.

This tool distinguishes HOST_ONLY schema development from BOARD_PS-calibrated
evidence. It never communicates with a board or claims PL execution.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np

try:
    from integer_postops import multiplier_shift, round_shift_even
except ImportError:
    from .integer_postops import multiplier_shift, round_shift_even


TRACE_LABELS = ("input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")
HOST_TRACE_STATUS = "HOST_NETWORK2_TRACE_SPLIT_VALIDATED_NOT_BOARD_PS_CAPTURE"
BOARD_TRACE_STATUS = "BOARD_PS_CPU_NETWORK2_BLOCK_TRACE_COLLECTION"
HOST_ORACLE_STATUS = "NETWORK2_INT_ORACLE_HOST_ONLY_NOT_BOARD_PS_OR_PL"
BOARD_ORACLE_STATUS = "NETWORK2_INT_ORACLE_BOARD_PS_CALIBRATED_CPU_NOT_PL"
MODEL_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
STAGE3_004_SHA256 = "164fdff3ab1a09e0b6282f4281ed09e7846cb44ace36ddbdca86ab57237e94c7"
STAGE3_004_MANIFEST = Path("artifacts/board-debug-20261004/acceleration/host/stage3-network20-int16-004/manifest.json")
DEFAULT_TEXT_MANIFEST = Path("artifacts/board-debug-20261004/host/s1-onnx-001/manifest.json")
EXPECTED_BLOCKS = 12
INT16_LIMIT = 32767


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_array(array, dtype):
    packed = np.ascontiguousarray(array, dtype=dtype)
    return hashlib.sha256(packed.tobytes()).hexdigest()


def canonical_json_sha256(data):
    packed = json.dumps(data, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def symmetric_scale(values, bits=16):
    values = np.asarray(values, dtype=np.float64)
    if not values.size or not np.all(np.isfinite(values)):
        raise ValueError("calibration tensor must be nonempty and finite")
    maximum = float(np.max(np.abs(values)))
    return maximum / float((1 << (bits - 1)) - 1) if maximum else 1.0


def quantize_symmetric(values, scale, bits=16):
    if not math.isfinite(float(scale)) or float(scale) <= 0:
        raise ValueError("quantization scale must be positive finite")
    low, high = -((1 << (bits - 1)) - 1), (1 << (bits - 1)) - 1
    dtype = np.int16 if bits == 16 else np.int8 if bits == 8 else None
    if dtype is None:
        raise ValueError("supported symmetric widths are 8 and 16")
    return np.clip(np.rint(np.asarray(values, dtype=np.float64) / float(scale)),
                   low, high).astype(dtype)


def quantize_weights_int8(weight):
    """Per-output-channel maxabs symmetric quantization; weights stored OI... ."""
    values = np.asarray(weight, dtype=np.float64)
    if values.ndim < 2:
        raise ValueError("weight tensor must have output and reduction dimensions")
    axes = tuple(range(1, values.ndim))
    maximum = np.max(np.abs(values), axis=axes)
    scales = np.where(maximum > 0.0, maximum / 127.0, 1.0)
    reshape = (scales.shape[0],) + (1,) * (values.ndim - 1)
    qweight = np.clip(np.rint(values / scales.reshape(reshape)), -127, 127).astype(np.int8)
    return qweight, scales.astype(np.float64)


def quantize_bias_i32(bias, accumulator_scales):
    bias = np.asarray(bias, dtype=np.float64)
    scales = np.asarray(accumulator_scales, dtype=np.float64)
    if np.any(~np.isfinite(scales)) or np.any(scales <= 0):
        raise ValueError("accumulator scales must be positive finite")
    rounded = np.rint(bias / scales)
    limits = np.iinfo(np.int32)
    if np.any(rounded < limits.min) or np.any(rounded > limits.max):
        raise OverflowError("quantized bias does not fit int32")
    return rounded.astype(np.int32)


def q31_parameters(ratios, signed=False):
    multipliers, shifts = [], []
    for ratio in np.asarray(ratios, dtype=np.float64).reshape(-1):
        ratio = float(ratio)
        if ratio == 0.0 and signed:
            multipliers.append(0)
            shifts.append(0)
        else:
            if not math.isfinite(ratio) or ratio == 0.0:
                raise ValueError("Q31 ratios must be finite and nonzero")
            magnitude, shift = multiplier_shift(abs(ratio))
            multipliers.append(int(-magnitude if ratio < 0 else magnitude))
            shifts.append(int(shift))
    return np.asarray(multipliers, dtype=np.int32), np.asarray(shifts, dtype=np.int32)


def requantize_q31(accumulator, multiplier, shift, clip=(-32767, 32767)):
    """Per-channel CHW Q31 requantization with signed ties-to-even rounding."""
    values = np.asarray(accumulator)
    if values.dtype.kind not in "iu" or values.ndim != 3:
        raise ValueError("requant input must be an integer CHW tensor")
    multipliers = np.asarray(multiplier, dtype=np.int32).reshape(-1)
    shifts = np.asarray(shift, dtype=np.int32).reshape(-1)
    if multipliers.shape != shifts.shape or multipliers.size not in (1, values.shape[0]):
        raise ValueError("Q31 coefficient channel shape mismatch")
    out = np.empty(values.shape, dtype=np.int16 if clip is not None else np.int64)
    for channel in range(values.shape[0]):
        ci = 0 if multipliers.size == 1 else channel
        product = values[channel].astype(np.int64) * np.int64(multipliers[ci])
        if product.size and int(np.max(np.abs(product))) > (1 << 62):
            raise OverflowError("Q31 product exceeds independent int64 oracle budget")
        rounded = round_shift_even(product, int(shifts[ci]))
        if clip is None:
            out[channel] = rounded.astype(np.int64)
        else:
            out[channel] = np.clip(rounded, clip[0], clip[1]).astype(np.int16)
    return out


def checked_accumulator_with_bias(raw, bias_i32):
    """Independently accumulated INT64 values, then checked bias-included INT32."""
    raw = np.asarray(raw, dtype=np.int64)
    bias = np.asarray(bias_i32, dtype=np.int64).reshape(-1)
    if raw.ndim != 3 or raw.shape[0] != bias.size:
        raise ValueError("accumulator/bias must be CHW and per-output-channel")
    limits = np.iinfo(np.int32)
    if np.any(raw < limits.min) or np.any(raw > limits.max):
        raise OverflowError("raw int64 accumulator exceeds int32")
    total = raw + bias[:, None, None]
    if np.any(total < limits.min) or np.any(total > limits.max):
        raise OverflowError("raw accumulator plus bias exceeds int32")
    return total.astype(np.int32)


def depthwise_accumulate(qinput_chw, qweight_oihw):
    x = np.asarray(qinput_chw, dtype=np.int16)
    w = np.asarray(qweight_oihw, dtype=np.int8)
    if x.ndim != 3 or w.ndim != 4 or w.shape[1] != 1 or w.shape[0] != x.shape[0]:
        raise ValueError("depthwise input/weight shape mismatch")
    kh, kw = w.shape[2:]
    ph, pw = kh // 2, kw // 2
    padded = np.pad(x.astype(np.int64), ((0, 0), (ph, ph), (pw, pw)), mode="constant")
    result = np.zeros(x.shape, dtype=np.int64)
    for row in range(kh):
        for col in range(kw):
            result += padded[:, row:row + x.shape[1], col:col + x.shape[2]] * \
                      w[:, 0, row, col].astype(np.int64)[:, None, None]
    return result


def pointwise_accumulate(qinput_chw, qweight_oi):
    x = np.asarray(qinput_chw, dtype=np.int16)
    w = np.asarray(qweight_oi, dtype=np.int8)
    if x.ndim != 3 or w.ndim != 2 or w.shape[1] != x.shape[0]:
        raise ValueError("pointwise input/weight shape mismatch")
    channels, height, width = x.shape
    rows = x.transpose(1, 2, 0).reshape((height * width, channels)).astype(np.int64)
    raw = rows @ w.astype(np.int64).T
    return raw.T.reshape((w.shape[0], height, width))


def validate_block_chain(blocks):
    if len(blocks) != EXPECTED_BLOCKS:
        raise ValueError("trace manifest must describe exactly 12 blocks")
    for index, block in enumerate(blocks):
        if int(block.get("index", -1)) != index:
            raise ValueError("block indices must be contiguous from 0 through 11")
        if index and block.get("input") != blocks[index - 1].get("outputs", {}).get("add"):
            raise ValueError("block Add to next input tensor-name chain is broken")
    return True


def _sample_records(manifest):
    if "host_reference" in manifest:
        return manifest["host_reference"].get("samples", []), "HOST_ONLY"
    return manifest.get("cases", []), "BOARD_PS"


def _record_files(sample, mode):
    if mode == "HOST_ONLY":
        return sample.get("files", [])
    # Board collection schema: case.blocks[block].files keyed by trace label.
    flat = []
    block_values = sample.get("blocks", [])
    if isinstance(block_values, dict):
        def block_sort(pair):
            value = pair[1]
            return int(value.get("index", str(pair[0]).replace("block-", "")))
        block_values = [item[1] for item in sorted(block_values.items(), key=block_sort)]
    for block_index, block in enumerate(block_values):
        files = block.get("files", {})
        if isinstance(files, dict):
            for label, entry in files.items():
                value = dict(entry)
                value.setdefault("block", block_index)
                value.setdefault("label", label)
                if value.get("path") and not Path(value["path"]).is_absolute():
                    value["path"] = str(Path(_sample_id(sample)) / value["path"])
                flat.append(value)
        else:
            for entry in files:
                value = dict(entry)
                if value.get("path") and not Path(value["path"]).is_absolute():
                    value["path"] = str(Path(_sample_id(sample)) / value["path"])
                flat.append(value)
    return flat


def _sample_id(sample):
    return sample.get("sample_id") or sample.get("id") or sample.get("case_id")


def _input_sha256(sample):
    source = sample.get("source_input", {})
    return sample.get("input_sha256") or (source.get("sha256") if isinstance(source, dict) else None)


def validate_trace_manifest(manifest):
    blocks = manifest.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("trace manifest missing block list")
    validate_block_chain(blocks)
    samples, mode = _sample_records(manifest)
    if len(samples) != 3:
        raise ValueError("network.2 calibration requires exactly three trace samples")
    if mode == "HOST_ONLY" and manifest.get("status") != HOST_TRACE_STATUS:
        raise ValueError("unrecognized HOST_ONLY trace provenance")
    if mode == "BOARD_PS" and manifest.get("status") != BOARD_TRACE_STATUS:
        raise ValueError("board trace provenance status is not the frozen PS collector")
    names_by_sample = set()
    for sample in samples:
        grouped = {}
        for item in _record_files(sample, mode):
            key = (int(item.get("block", -1)), item.get("label"))
            if key in grouped:
                raise ValueError("duplicate trace label %r" % (key,))
            grouped[key] = item
            if mode == "HOST_ONLY" and item.get("provenance") != \
                    "HOST_ORT_REFERENCE_ONLY_NOT_BOARD_PS_CAPTURE":
                raise ValueError("HOST_ONLY record has unexpected provenance")
        expected = {(b, label) for b in range(EXPECTED_BLOCKS) for label in TRACE_LABELS}
        if set(grouped) != expected:
            raise ValueError("each sample must include all 8 trace labels for blocks 0..11")
        sample_id = _sample_id(sample)
        if sample_id not in ("image-00", "image-01", "image-02"):
            raise ValueError("sample ID must be one of fixed image-00..02")
        if sample_id in names_by_sample:
            raise ValueError("sample IDs must be unique")
        names_by_sample.add(sample_id)
        input_sha = _input_sha256(sample)
        if not isinstance(input_sha, str) or len(input_sha) != 64 or any(
                char not in "0123456789abcdef" for char in input_sha.lower()):
            raise ValueError("each fixed sample must pin the original input SHA256")
        for block_index, block_spec in enumerate(blocks):
            for label in TRACE_LABELS:
                entry = grouped[(block_index, label)]
                expected_shape = ([1, 384, 32, 32] if label in ("pw1", "gelu")
                                  else [1, 128, 32, 32])
                expected_name = block_spec.get("input") if label == "input" else \
                    block_spec.get("outputs", {}).get(label)
                expected_bytes = int(np.prod(expected_shape)) * 4
                if list(entry.get("shape", [])) != expected_shape or entry.get("dtype") != "<f4":
                    raise ValueError("trace label %s block %d has wrong shape/dtype" % (label, block_index))
                if int(entry.get("bytes", -1)) != expected_bytes:
                    raise ValueError("trace label %s block %d has wrong byte count" % (label, block_index))
                if entry.get("tensor_name") != expected_name:
                    raise ValueError("trace tensor name does not match exact split node boundary")
    return {"provenance": mode, "sample_count": len(samples),
            "block_count": len(blocks), "labels_per_block": list(TRACE_LABELS)}


def load_trace_arrays(manifest_path, manifest):
    """Verify file metadata and load trace arrays, returning sample/block maps."""
    root = Path(manifest_path).resolve().parent
    samples, mode = _sample_records(manifest)
    loaded = []
    for sample in samples:
        blocks = [dict() for unused in range(EXPECTED_BLOCKS)]
        for item in _record_files(sample, mode):
            path = (root / item["path"]).resolve()
            raw = path.read_bytes()
            if len(raw) != int(item["bytes"]) or sha256_file(path) != item["sha256"]:
                raise ValueError("trace tensor byte count or SHA mismatch: %s" % path)
            dtype = item.get("dtype")
            shape = item.get("shape")
            if dtype != "<f4":
                raise ValueError("trace tensor must use little-endian float32")
            count = int(np.prod(shape))
            if count * 4 != len(raw):
                raise ValueError("trace tensor shape does not match byte size")
            blocks[int(item["block"])][item["label"]] = np.frombuffer(
                raw, dtype="<f4").reshape(shape).copy()
        feature_record = sample.get("feature", sample.get("suffix_feature"))
        feature = _load_feature_record(feature_record, root)
        loaded.append({"sample_id": _sample_id(sample),
                       "input_sha256": _input_sha256(sample), "blocks": blocks,
                       "feature": feature})
    return loaded


def _load_feature_record(record, root):
    if not isinstance(record, dict) or "path" not in record:
        return None
    path = (root / record["path"]).resolve()
    raw = path.read_bytes()
    if len(raw) != int(record.get("bytes", -1)) or sha256_file(path) != record.get("sha256"):
        raise ValueError("same-run suffix feature byte count or SHA mismatch")
    if record.get("dtype") != "<f4" or list(record.get("shape", [])) not in ([1, 512], [512]):
        raise ValueError("same-run suffix feature must be little-endian float32 [1,512]")
    return np.frombuffer(raw, dtype="<f4").reshape((1, 512)).copy()


def symmetric_calibration_scales(samples):
    """One scale per boundary, calibrated jointly over the three trace cases."""
    result = []
    for block_index in range(EXPECTED_BLOCKS):
        sample_blocks = [record["blocks"][block_index] for record in samples]
        scales = {}
        for label in TRACE_LABELS:
            values = [np.asarray(item[label], dtype=np.float64) for item in sample_blocks]
            maximum = max(float(np.max(np.abs(value))) for value in values)
            scales[label] = maximum / float(INT16_LIMIT) if maximum else 1.0
        if block_index:
            # No boundary requantization: the preceding Add code and scale pass through.
            scales["input"] = result[-1]["add"]
        result.append(scales)
    return result


def gelu_lut(scale_in, scale_out):
    lut = np.empty((65536,), dtype=np.int16)
    for encoded in range(65536):
        signed = encoded - 32768
        x = signed * float(scale_in)
        y = 0.5 * x * (1.0 + math.erf(x / math.sqrt(2.0)))
        lut[encoded] = np.int16(np.clip(np.rint(y / float(scale_out)), -32767, 32767))
    return lut


def apply_gelu_lut(qinput, lut):
    codes = np.asarray(qinput, dtype=np.int16).astype(np.int32) + 32768
    return np.asarray(lut, dtype=np.int16)[codes]


def _write_array(directory, filename, array, dtype):
    path = Path(directory) / filename
    packed = np.ascontiguousarray(array, dtype=dtype)
    packed.tofile(str(path))
    return {"path": filename, "dtype": dtype, "shape": list(packed.shape),
            "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def validate_model_identity(model_path, expected_sha=MODEL_SHA256):
    actual = sha256_file(model_path)
    if actual != expected_sha:
        raise ValueError("source ONNX SHA mismatch: %s" % actual)
    try:
        import onnx
    except ImportError:
        raise RuntimeError("onnx is required to extract block parameters")
    return onnx.load(str(model_path))


def extract_block_parameters(model, block):
    """Extract OI8 weights/biases and channel scale from named ONNX nodes."""
    from onnx import numpy_helper
    nodes = {node.name: node for node in model.graph.node}
    init = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    labels = ("dw3", "dw7", "pw1", "pw2")
    result = {}
    for label in labels:
        node_name = block["nodes"][label]
        node = nodes[node_name]
        if len(node.input) < 3 or node.input[1] not in init or node.input[2] not in init:
            raise ValueError("node must have frozen weight+bias initializers: %s" % node_name)
        weight = np.asarray(init[node.input[1]], dtype=np.float32)
        bias = np.asarray(init[node.input[2]], dtype=np.float32).reshape(-1)
        if label in ("pw1", "pw2"):
            if weight.ndim != 4 or weight.shape[2:] != (1, 1):
                raise ValueError("pointwise Conv weights must be OI11")
            weight = weight[:, :, 0, 0]
        qweight, weight_scales = quantize_weights_int8(weight)
        result[label] = {"node": node_name, "weight_f32": weight,
                         "bias_f32": bias, "weight_i8": qweight,
                         "weight_scales": weight_scales,
                         "weight_layout": "OI" if label.startswith("pw") else "O1HW"}
    scale_node = nodes[block["nodes"]["scale"]]
    scale = None
    for name in scale_node.input:
        if name in init:
            scale = np.asarray(init[name], dtype=np.float32).reshape(-1)
            break
    if scale is None:
        raise ValueError("per-channel residual scale initializer not found")
    result["residual_scale"] = scale
    return result


def _layer_parameters(layer, input_scale, output_scale, multiplier_scale=None):
    accum_scale = np.asarray(layer["weight_scales"], dtype=np.float64) * float(input_scale)
    bias_q = quantize_bias_i32(layer["bias_f32"], accum_scale)
    ratios = accum_scale / float(output_scale) if multiplier_scale is None else multiplier_scale
    multiplier, shift = q31_parameters(ratios)
    qweight = layer["weight_i8"]
    if qweight.ndim == 4:
        reduce_axis = (1, 2, 3)
    else:
        reduce_axis = 1
    l1 = np.sum(np.abs(qweight.astype(np.int64)), axis=reduce_axis)
    worst = l1 * INT16_LIMIT + np.abs(bias_q.astype(np.int64))
    return {"accumulator_scales": accum_scale, "bias_i32": bias_q,
            "multiplier_i32": multiplier, "shift_i32": shift,
            "worst_case_abs_accumulator_including_bias": worst,
            "worst_case_fits_int32": bool(np.all(worst <= np.iinfo(np.int32).max))}


def make_block_parameter_arrays(layers, scales):
    """Create serializer-facing standard arrays for one block (no wire packing)."""
    specs = {
        "dw3": _layer_parameters(layers["dw3"], scales["input"], scales["dw3"]),
        "dw7": _layer_parameters(layers["dw7"], scales["dw3"], scales["dw7"]),
        "pw1": _layer_parameters(layers["pw1"], scales["dw7"], scales["pw1"]),
        "pw2": _layer_parameters(layers["pw2"], scales["gelu"], scales["pw2"]),
    }
    if not all(item["worst_case_fits_int32"] for item in specs.values()):
        raise OverflowError("conservative activation16 accumulator bound exceeds int32")
    weights = {
        "dw3_weights": layers["dw3"]["weight_i8"].reshape((128, 9)),
        "dw7_weights": layers["dw7"]["weight_i8"].reshape((128, 49)),
        "pw1_weights": layers["pw1"]["weight_i8"],
        "pw2_weights": layers["pw2"]["weight_i8"],
    }
    biases = np.concatenate([specs[name]["bias_i32"]
                             for name in ("dw3", "dw7", "pw1", "pw2")])
    multipliers = np.concatenate([specs[name]["multiplier_i32"]
                                  for name in ("dw3", "dw7", "pw1", "pw2")])
    shifts = np.concatenate([specs[name]["shift_i32"]
                             for name in ("dw3", "dw7", "pw1", "pw2")])
    scale_multiplier, scale_shift = q31_parameters(
        np.asarray(layers["residual_scale"], dtype=np.float64) * scales["pw2"] / scales["add"],
        signed=True)
    residual_multiplier, residual_shift = q31_parameters(
        np.asarray([scales["dw3"] / scales["add"]], dtype=np.float64), signed=True)
    arrays = dict(weights)
    arrays.update({
        "bias_i32": biases, "multiplier_i32": multipliers, "shift_i32": shifts,
        "bias_f32": np.concatenate([layers[name]["bias_f32"]
                                    for name in ("dw3", "dw7", "pw1", "pw2")]),
        "dw3_weight_f32": layers["dw3"]["weight_f32"].reshape((128, 9)),
        "dw7_weight_f32": layers["dw7"]["weight_f32"].reshape((128, 49)),
        "pw1_weight_f32": layers["pw1"]["weight_f32"],
        "pw2_weight_f32": layers["pw2"]["weight_f32"],
        "gelu_lut": gelu_lut(scales["pw1"], scales["gelu"]),
        "scale_multiplier_i32": scale_multiplier, "scale_shift_i32": scale_shift,
        "residual_multiplier_i32": residual_multiplier, "residual_shift_i32": residual_shift,
        "boundary_scales_f64": np.asarray([scales[label] for label in TRACE_LABELS], dtype="<f8"),
        "dw3_weight_scales_f64": layers["dw3"]["weight_scales"],
        "dw7_weight_scales_f64": layers["dw7"]["weight_scales"],
        "pw1_weight_scales_f64": layers["pw1"]["weight_scales"],
        "pw2_weight_scales_f64": layers["pw2"]["weight_scales"],
        "dw3_accumulator_scales_f64": specs["dw3"]["accumulator_scales"],
        "dw7_accumulator_scales_f64": specs["dw7"]["accumulator_scales"],
        "pw1_accumulator_scales_f64": specs["pw1"]["accumulator_scales"],
        "pw2_accumulator_scales_f64": specs["pw2"]["accumulator_scales"],
        "residual_scale_f32": layers["residual_scale"],
    })
    return arrays, specs


def write_block_parameter_artifact(out_dir, block_index, layers, scales, trace_block):
    block_dir = Path(out_dir) / ("block-%02d" % block_index)
    block_dir.mkdir(parents=True, exist_ok=False)
    arrays, specs = make_block_parameter_arrays(layers, scales)
    dtypes = {
        "dw3_weights": "|i1", "dw7_weights": "|i1", "pw1_weights": "|i1",
        "pw2_weights": "|i1", "bias_i32": "<i4", "multiplier_i32": "<i4",
        "shift_i32": "<i4", "gelu_lut": "<i2", "scale_multiplier_i32": "<i4",
        "bias_f32": "<f4", "dw3_weight_f32": "<f4", "dw7_weight_f32": "<f4",
        "pw1_weight_f32": "<f4", "pw2_weight_f32": "<f4",
        "scale_shift_i32": "<i4", "residual_multiplier_i32": "<i4",
        "residual_shift_i32": "<i4", "boundary_scales_f64": "<f8",
        "dw3_weight_scales_f64": "<f8", "dw7_weight_scales_f64": "<f8",
        "pw1_weight_scales_f64": "<f8", "pw2_weight_scales_f64": "<f8",
        "dw3_accumulator_scales_f64": "<f8", "dw7_accumulator_scales_f64": "<f8",
        "pw1_accumulator_scales_f64": "<f8", "pw2_accumulator_scales_f64": "<f8",
        "residual_scale_f32": "<f4",
    }
    files = {}
    for key in sorted(arrays):
        files[key] = _write_array(block_dir, key + ".bin", arrays[key], dtypes[key])
        files[key]["path"] = "block-%02d/%s" % (block_index, files[key]["path"])
    metadata = {
        "schema_version": 1, "block_index": int(block_index), "parameters": files,
        "semantics": {
            "activation": "symmetric INT16 zero_point=0 ties-even clip [-32767,32767]",
            "weight": "symmetric INT8 zero_point=0 per-output-channel ties-even clip [-127,127]",
            "bias": "INT32, independently round-even quantized; included in exported raw accum result",
            "bias_quantization": "round_even(float_bias/(activation_input_scale*per_channel_weight_scale)); reject outside INT32",
            "q31": "signed multiplier, right shift, round-to-nearest ties-even",
            "raw_accumulator_oracle": "INT64 accumulation; raw and raw+bias independently checked against INT32",
            "block_boundary": "Add INT16 codes and its scale pass unchanged as next block input",
            "weight_layouts": {"dw3_weights": "O,KH*KW; depthwise OIHW flattened across spatial kernel",
                               "dw7_weights": "O,KH*KW; depthwise OIHW flattened across spatial kernel",
                               "pw1_weights": "OI standard pointwise", "pw2_weights": "OI standard pointwise"},
            "merged_channel_order": ["dw3[0:128]", "dw7[128:256]", "pw1[256:640]", "pw2[640:768]"],
        },
        "calibration_scales": {key: float(value) for key, value in scales.items()},
        "trace_tensor_names": {key: value.get("tensor_name") for key, value in trace_block.items()},
        "accumulator_bounds": {
            name: {"worst_case_abs_including_bias": int(np.max(spec["worst_case_abs_accumulator_including_bias"])),
                   "worst_case_fits_int32": bool(spec["worst_case_fits_int32"]),
                   "accumulator_scale_shape": list(spec["accumulator_scales"].shape)}
            for name, spec in specs.items()},
    }
    submanifest = block_dir / "manifest.json"
    submanifest.write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    relative = str(submanifest.relative_to(out_dir)).replace("\\", "/")
    identity = sha256_file(submanifest)
    return {"index": int(block_index), "path": relative,
            "parameter_manifest_sha256": identity,
            "verified_parameter_manifest_sha256": identity,
            "bytes": submanifest.stat().st_size,
            "parameter_manifest": {"path": relative, "sha256": identity,
                                   "bytes": submanifest.stat().st_size},
            "files": files}


def _layer_raw(layer, qinput):
    if layer["weight_i8"].ndim == 4:
        return depthwise_accumulate(qinput, layer["weight_i8"])
    return pointwise_accumulate(qinput, layer["weight_i8"])


def execute_block(qinput, params, scales, layers, lut):
    """Execute one quantized block; returned Add codes directly feed next block."""
    raw_dw3 = _layer_raw(layers["dw3"], qinput)
    total_dw3 = checked_accumulator_with_bias(raw_dw3, params["dw3"]["bias_i32"])
    qdw3 = requantize_q31(total_dw3,
        params["dw3"]["multiplier_i32"], params["dw3"]["shift_i32"])
    raw_dw7 = _layer_raw(layers["dw7"], qdw3)
    total_dw7 = checked_accumulator_with_bias(raw_dw7, params["dw7"]["bias_i32"])
    qdw7 = requantize_q31(total_dw7,
        params["dw7"]["multiplier_i32"], params["dw7"]["shift_i32"])
    raw_pw1 = _layer_raw(layers["pw1"], qdw7)
    total_pw1 = checked_accumulator_with_bias(raw_pw1, params["pw1"]["bias_i32"])
    qpw1 = requantize_q31(total_pw1,
        params["pw1"]["multiplier_i32"], params["pw1"]["shift_i32"])
    qgelu = apply_gelu_lut(qpw1, lut)
    raw_pw2 = _layer_raw(layers["pw2"], qgelu)
    qpw2_acc = checked_accumulator_with_bias(raw_pw2, params["pw2"]["bias_i32"])
    qpw2 = requantize_q31(qpw2_acc, params["pw2"]["multiplier_i32"],
                          params["pw2"]["shift_i32"])
    qscaled = requantize_q31(qpw2, params["scale_multiplier_i32"],
                             params["scale_shift_i32"], clip=None)
    qresidual = requantize_q31(qdw3, params["residual_multiplier_i32"],
                               params["residual_shift_i32"], clip=None)
    summed = qscaled.astype(np.int64) + qresidual.astype(np.int64)
    return np.clip(summed, -32767, 32767).astype(np.int16), {
        "dw3": qdw3, "dw7": qdw7, "pw1": qpw1, "gelu": qgelu,
        "pw2_acc_bias_included": qpw2_acc, "scale": qscaled,
        "residual": qresidual,
        "accumulators": {"dw3": {"raw": raw_dw3, "bias_included": total_dw3},
                         "dw7": {"raw": raw_dw7, "bias_included": total_dw7},
                         "pw1": {"raw": raw_pw1, "bias_included": total_pw1},
                         "pw2": {"raw": raw_pw2, "bias_included": qpw2_acc}}}


def tensor_metrics(actual, expected):
    a, b = np.asarray(actual, dtype=np.float64), np.asarray(expected, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError("metric tensors have different shapes")
    delta = a - b
    af, bf = a.reshape(-1), b.reshape(-1)
    denom = float(np.linalg.norm(af) * np.linalg.norm(bf))
    return {"shape": list(a.shape), "max_abs": float(np.max(np.abs(delta))),
            "rms_abs": float(np.sqrt(np.mean(delta * delta))),
            "cosine": float(np.dot(af, bf) / max(denom, 1e-30)),
            "allclose_rtol_1e-4_atol_1e-5": bool(np.allclose(a, b, rtol=1e-4, atol=1e-5))}


def execute_integer_cascade(model, trace_manifest, trace_samples, scales_by_block,
                            collect_intermediate=True):
    """Run all 12 blocks in sequence; each Add INT16 output directly feeds next input."""
    block_layers = [extract_block_parameters(model, block)
                    for block in trace_manifest["blocks"]]
    all_cases = []
    for sample in trace_samples:
        initial_codes = quantize_symmetric(sample["blocks"][0]["input"],
                                           scales_by_block[0]["input"], 16)[0]
        qinput = initial_codes.copy()
        per_block = []
        for block_index in range(EXPECTED_BLOCKS):
            if block_index and scales_by_block[block_index]["input"] != \
                    scales_by_block[block_index - 1]["add"]:
                raise ValueError("block boundary scale changed; implicit requantization is forbidden")
            layers = block_layers[block_index]
            arrays, specs = make_block_parameter_arrays(layers, scales_by_block[block_index])
            params = dict(specs)
            for key in ("scale_multiplier_i32", "scale_shift_i32",
                        "residual_multiplier_i32", "residual_shift_i32"):
                params[key] = arrays[key]
            qadd, stages = execute_block(qinput, params, scales_by_block[block_index],
                                         layers, arrays["gelu_lut"])
            diagnostics = {}
            if collect_intermediate:
                trace = sample["blocks"][block_index]
                for label in ("dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add"):
                    if label == "pw2":
                        qvalue = stages["pw2_acc_bias_included"]
                        # Convert biased INT32 accumulator to real units before comparison.
                        current = qvalue.astype(np.float64) * params["pw2"]["accumulator_scales"][:, None, None]
                    elif label == "scale":
                        current = stages["scale"].astype(np.float64) * scales_by_block[block_index]["add"]
                    elif label == "add":
                        current = qadd.astype(np.float64) * scales_by_block[block_index]["add"]
                    else:
                        current = stages[label].astype(np.float64) * scales_by_block[block_index][label]
                    expected = np.asarray(trace[label], dtype=np.float64)
                    if expected.ndim == 4:
                        expected = expected[0]
                    diagnostics[label] = tensor_metrics(current, expected)
            bounds = {
                                  name: {"actual_raw_min": int(np.min(stages["accumulators"][name]["raw"])),
                                        "actual_raw_max": int(np.max(stages["accumulators"][name]["raw"])),
                                        "actual_bias_included_min": int(np.min(stages["accumulators"][name]["bias_included"])),
                                        "actual_bias_included_max": int(np.max(stages["accumulators"][name]["bias_included"])),
                                        "actual_abs_max_bias_included": int(np.max(np.abs(
                                            stages["accumulators"][name]["bias_included"].astype(np.int64)))),
                                        "actual_raw_and_bias_fit_int32": True,
                                        "worst_case_abs_including_bias": int(np.max(spec["worst_case_abs_accumulator_including_bias"])),
                                        "worst_case_fits_int32": bool(spec["worst_case_fits_int32"])}
                                  for name, spec in specs.items()}
            checksum_dtypes = {"dw3": "<i2", "dw7": "<i2", "pw1": "<i2",
                               "gelu": "<i2", "pw2_acc_bias_included": "<i4",
                               "scale": "<i8", "residual": "<i8"}
            stage_checksums = {name: {"dtype": dtype, "shape": list(stages[name].shape),
                                      "sha256": sha256_array(stages[name], dtype)}
                               for name, dtype in checksum_dtypes.items()}
            stage_checksums["add"] = {"dtype": "<i2", "shape": list(qadd.shape),
                                      "sha256": sha256_array(qadd, "<i2")}
            for name, values in stages["accumulators"].items():
                stage_checksums[name + "_raw_i64"] = {
                    "dtype": "<i8", "shape": list(values["raw"].shape),
                    "sha256": sha256_array(values["raw"], "<i8")}
                stage_checksums[name + "_bias_included_i32"] = {
                    "dtype": "<i4", "shape": list(values["bias_included"].shape),
                    "sha256": sha256_array(values["bias_included"], "<i4")}
            per_block.append({"block_index": block_index, "add_codes": qadd,
                              "metrics": diagnostics, "accumulator_bounds": bounds,
                              "stage_checksums": stage_checksums})
            qinput = qadd
        all_cases.append({"sample_id": sample["sample_id"],
                          "input_sha256": _input_sha256(sample), "blocks": per_block,
                          "initial_codes": initial_codes,
                          "initial_input_scale": scales_by_block[0]["input"],
                          "final_codes": qinput,
                          "final_dequantized": (qinput.astype(np.float64) *
                                                scales_by_block[-1]["add"]).astype(np.float32)})
    return all_cases


def extract_suffix_session(model_path, input_tensor_name, threads=1):
    """Create a CPU-only suffix session to map final Add to the 512-D feature."""
    import onnx
    import onnxruntime as ort
    from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference
    model = SymbolicShapeInference.infer_shapes(onnx.load(str(model_path)), auto_merge=True)
    suffix = onnx.utils.Extractor(model).extract_model([input_tensor_name], ["features"])
    onnx.checker.check_model(suffix)
    options = ort.SessionOptions()
    options.intra_op_num_threads = max(1, int(threads))
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    ort.disable_telemetry_events()
    return ort.InferenceSession(suffix.SerializeToString(), options,
                                providers=["CPUExecutionProvider"])


def rank_feature(feature, text_features, text_ids):
    vector = np.asarray(feature, dtype=np.float64).reshape(-1)
    text = np.asarray(text_features, dtype=np.float64)
    if vector.shape != (512,) or text.shape != (8, 512) or len(text_ids) != 8:
        raise ValueError("rank contract requires one 512-D image and eight 512-D texts")
    vector /= max(float(np.linalg.norm(vector)), 1e-30)
    text /= np.maximum(np.linalg.norm(text, axis=1, keepdims=True), 1e-30)
    scores = vector @ text.T
    order = np.argsort(-scores, kind="stable")
    return {"scores": scores.tolist(), "ranking": [text_ids[int(i)] for i in order],
            "top1": text_ids[int(order[0])]}


def run_cascade_report(model_path, trace_manifest, trace_samples, scales_by_block,
                       text_features, text_ids, output_dir, threads=1):
    cascades = execute_integer_cascade(validate_model_identity(model_path), trace_manifest,
                                       trace_samples, scales_by_block, collect_intermediate=True)
    final_input_name = trace_manifest["blocks"][-1]["outputs"]["add"]
    suffix_session = extract_suffix_session(model_path, final_input_name, threads)
    result_records, file_records = [], {}
    mode = _sample_records(trace_manifest)[1]
    for sample, cascade in zip(trace_samples, cascades):
        results_dir = Path(output_dir) / "results"
        results_dir.mkdir(exist_ok=True)
        qinput_file = _write_array(results_dir, cascade["sample_id"] + "-qinput.i16",
                                   cascade["initial_codes"][None, ...], "<i2")
        qinput_file["path"] = "results/" + qinput_file["path"]
        file_records[qinput_file["path"]] = qinput_file
        block_files = []
        for block in cascade["blocks"]:
            filename = "%s-block-%02d-add.i16" % (cascade["sample_id"], block["block_index"])
            ref = _write_array(results_dir, filename, block["add_codes"][None, ...], "<i2")
            ref["path"] = "results/" + filename
            file_records[ref["path"]] = ref
            block_files.append(ref)
            del block["add_codes"]
        quant_feature = suffix_session.run(["features"], {
            final_input_name: cascade["final_dequantized"].reshape((1, 128, 32, 32)).astype("<f4")})[0]
        if sample["feature"] is None and mode == "BOARD_PS":
            raise ValueError("BOARD_PS trace lacks same-run suffix feature; cannot claim PS comparison")
        if sample["feature"] is None:
            final_fp32 = sample["blocks"][-1]["add"].astype("<f4")
            if final_fp32.ndim == 3:
                final_fp32 = final_fp32[None, ...]
            reference_feature = suffix_session.run(["features"], {final_input_name: final_fp32})[0]
            reference_kind = "HOST_ORT_SUFFIX_REFERENCE_ONLY_NOT_BOARD_PS"
        else:
            if sample["feature"] is None:
                raise ValueError("board trace sample missing same-run suffix feature")
            reference_feature = sample["feature"]
            reference_kind = "SAME_RUN_BOARD_PS_SUFFIX_FEATURE"
        feature_metric = tensor_metrics(quant_feature, reference_feature)
        quant_rank = rank_feature(quant_feature, text_features, text_ids)
        reference_rank = rank_feature(reference_feature, text_features, text_ids)
        qfeature_file = _write_array(results_dir, cascade["sample_id"] + "-quant-feature.f32",
                                     quant_feature, "<f4")
        qfeature_file["path"] = "results/" + qfeature_file["path"]
        file_records[qfeature_file["path"]] = qfeature_file
        reference_file = _write_array(results_dir, cascade["sample_id"] + "-reference-feature.f32",
                                      reference_feature, "<f4")
        reference_file["path"] = "results/" + reference_file["path"]
        file_records[reference_file["path"]] = reference_file
        final_codes_file = _write_array(results_dir, cascade["sample_id"] + "-final-add.i16",
                                        cascade["final_codes"][None, ...], "<i2")
        final_codes_file["path"] = "results/" + final_codes_file["path"]
        file_records[final_codes_file["path"]] = final_codes_file
        result_records.append({
            "sample_id": cascade["sample_id"], "input_sha256": cascade["input_sha256"],
            "suffix_reference_kind": reference_kind,
            "feature_metrics_quantized_vs_reference": feature_metric,
            "top1_changed": quant_rank["top1"] != reference_rank["top1"],
            "full_rank_matches": quant_rank["ranking"] == reference_rank["ranking"],
            "reference_ranking": reference_rank["ranking"], "quantized_ranking": quant_rank["ranking"],
            "reference_top1": reference_rank["top1"], "quantized_top1": quant_rank["top1"],
            "qinput_scale": float(cascade["initial_input_scale"]),
            "block_metrics": [{"block_index": item["block_index"], "metrics": item["metrics"],
                               "accumulator_bounds": item["accumulator_bounds"],
                               "stage_checksums": item["stage_checksums"],
                               "add_file": block_files[index]}
                              for index, item in enumerate(cascade["blocks"])],
            "qinput_file": qinput_file, "quantized_feature_file": qfeature_file,
            "reference_feature_file": reference_file,
            "final_add_file": final_codes_file,
        })
    return {"results": result_records, "files": file_records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-manifest", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("host-only", "board-ps"), required=True)
    parser.add_argument("--text-features")
    parser.add_argument("--text-manifest")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--run-cascade", action="store_true",
                        help="execute 12 blocks, suffix feature, full rank, and metric comparison")
    args = parser.parse_args(argv)
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(limits=max(1, int(args.threads))).__enter__()
    except ImportError:
        pass
    trace_path = Path(args.trace_manifest)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace_info = validate_trace_manifest(trace)
    expected_mode = "HOST_ONLY" if args.mode == "host-only" else "BOARD_PS"
    if trace_info["provenance"] != expected_mode:
        parser.error("--mode does not match trace provenance")
    model = validate_model_identity(args.model)
    import onnx
    try:
        import onnxruntime
        ort_version = onnxruntime.__version__
    except ImportError:
        ort_version = None
    samples = load_trace_arrays(trace_path, trace)
    scales_by_block = symmetric_calibration_scales(samples)
    final_out = Path(args.output)
    if final_out.exists():
        parser.error("output directory already exists; refusing to overwrite")
    out_dir = final_out.with_name(final_out.name + ".partial")
    if out_dir.exists():
        parser.error("partial output directory already exists; inspect it before retry")
    out_dir.mkdir(parents=True, exist_ok=False)
    block_records = []
    for index, block in enumerate(trace["blocks"]):
        layers = extract_block_parameters(model, block)
        block_records.append(write_block_parameter_artifact(
            out_dir, index, layers, scales_by_block[index], _trace_names(block)))
    status = HOST_ORACLE_STATUS if expected_mode == "HOST_ONLY" else BOARD_ORACLE_STATUS
    trace_sha = sha256_file(trace_path)
    model_sha = sha256_file(args.model)
    results = []
    result_files = {}
    dependencies = [{"role": "trace_manifest", "path": str(trace_path), "sha256": trace_sha},
                    {"role": "source_onnx", "path": str(Path(args.model)), "sha256": model_sha}]
    if args.run_cascade:
        if not args.text_features or not args.text_manifest:
            parser.error("--run-cascade requires pinned --text-features and --text-manifest")
        stage3_path = STAGE3_004_MANIFEST
        if sha256_file(stage3_path) != STAGE3_004_SHA256:
            parser.error("frozen Stage3-004 manifest identity mismatch")
        stage3_report = json.loads(stage3_path.read_text(encoding="utf-8"))
        text_manifest_path = Path(args.text_manifest)
        text_features_path = Path(args.text_features)
        text_manifest_sha = sha256_file(text_manifest_path)
        text_features_sha = sha256_file(text_features_path)
        if text_manifest_sha != stage3_report["text_manifest_sha256"]:
            parser.error("text-manifest SHA does not match Stage3-004 dependency")
        if text_features_sha != stage3_report["text_features_sha256"]:
            parser.error("text-feature SHA does not match Stage3-004 dependency")
        text_manifest = json.loads(text_manifest_path.read_text(encoding="utf-8"))
        text_ids = [item["id"] for item in text_manifest["prompts"]]
        text_features = np.fromfile(str(text_features_path), dtype="<f4")
        if text_features.size != 8 * 512:
            parser.error("pinned text features must contain exactly 8x512 float32 values")
        text_features = text_features.reshape((8, 512))
        text_copy = out_dir / "text-features.f32"
        text_copy.write_bytes(text_features_path.read_bytes())
        text_ref = {"path": text_copy.name, "bytes": text_copy.stat().st_size,
                    "dtype": "<f4", "shape": [8, 512], "sha256": sha256_file(text_copy)}
        result_files[text_copy.name] = text_ref
        dependencies.extend([
            {"role": "stage3_004_manifest", "path": str(stage3_path),
             "sha256": STAGE3_004_SHA256},
            {"role": "text_manifest", "path": str(text_manifest_path),
             "sha256": text_manifest_sha},
            {"role": "text_features_copy", "path": text_copy.name,
             "sha256": text_ref["sha256"]},
        ])
        cascade = run_cascade_report(args.model, trace, samples, scales_by_block,
                                     text_features, text_ids, out_dir, args.threads)
        results, cascade_files = cascade["results"], cascade["files"]
        result_files.update(cascade_files)
    manifest = {
        "schema_version": 1, "status": status, "block_count": EXPECTED_BLOCKS,
        "provenance": {"mode": expected_mode, "source_trace_status": trace.get("status"),
                       "claim": "host CPU integer parameters; not PL execution"},
        "source_trace_manifest": {"path": str(trace_path), "sha256": trace_sha},
        "source_model": {"path": str(Path(args.model)), "sha256": model_sha},
        "runtime": {"python_executable": sys.executable,
                    "python_version": sys.version.split()[0], "numpy_version": np.__version__,
                    "onnx_version": onnx.__version__, "onnxruntime_version": ort_version,
                    "thread_limit": max(1, int(args.threads))},
        "dependencies": dependencies,
        "calibration": {"activation": "symmetric INT16 maxabs/32767 over three trace samples",
                        "boundary_policy": "Add codes and scale pass unchanged to next block input",
                        "weight": "per-output-channel symmetric INT8 maxabs/127; ties-even"},
        "checks": {"all_12_blocks_present": True, "block_chain_exact_by_tensor_name": True,
                   "conservative_accumulators_fit_int32": True,
                   "full_feature_metrics_and_rank": bool(args.run_cascade),
                   "board_ps_calibration": expected_mode == "BOARD_PS"},
        "artifact_completeness": "FULL_CASCADE" if args.run_cascade else "PARAMETERS_ONLY_CASCADE_NOT_RUN",
        "text_feature_reference": text_ref if args.run_cascade else None,
        "blocks": block_records, "files": result_files, "results": results,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                                            encoding="utf-8")
    out_dir.rename(final_out)
    note = ("full host CPU integer cascade/suffix comparison; no board or PL execution"
            if args.run_cascade else "parameter generation only; no board or PL execution")
    print(json.dumps({"output": str(final_out), "status": status,
                      "blocks": len(block_records), "note": note}, indent=2, sort_keys=True))


def validate_model_identity(model_path, expected_sha=MODEL_SHA256):
    actual = sha256_file(model_path)
    if actual != expected_sha:
        raise ValueError("source ONNX SHA mismatch: %s" % actual)
    try:
        import onnx
    except ImportError:
        raise RuntimeError("onnx is required to extract model parameters")
    return onnx.load(str(model_path))


def extract_block_parameters(model, block):
    """Extract per-block Conv weights and the residual multiplier from ONNX."""
    from onnx import numpy_helper
    nodes = {node.name: node for node in model.graph.node}
    initializers = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    result = {}
    for label in ("dw3", "dw7", "pw1", "pw2"):
        node = nodes[block["nodes"][label]]
        if len(node.input) < 3 or node.input[1] not in initializers or node.input[2] not in initializers:
            raise ValueError("Conv node lacks frozen weight/bias initializers: %s" % node.name)
        weight = np.asarray(initializers[node.input[1]], dtype=np.float32)
        bias = np.asarray(initializers[node.input[2]], dtype=np.float32).reshape(-1)
        if label in ("pw1", "pw2"):
            if weight.ndim != 4 or weight.shape[2:] != (1, 1):
                raise ValueError("pointwise Conv weights must have OI11 layout")
            weight = weight[:, :, 0, 0]
        quantized, weight_scales = quantize_weights_int8(weight)
        result[label] = {"node": node.name, "weight_f32": weight,
                         "bias_f32": bias, "weight_i8": quantized,
                         "weight_scales": weight_scales}
    scale_node = nodes[block["nodes"]["scale"]]
    scale = None
    for name in scale_node.input:
        if name in initializers:
            scale = np.asarray(initializers[name], dtype=np.float32).reshape(-1)
            break
    if scale is None:
        raise ValueError("frozen per-channel residual scale initializer not found")
    if scale.size != result["pw2"]["weight_i8"].shape[0]:
        raise ValueError("residual multiplier channel count mismatch")
    result["residual_scale"] = scale
    return result


def _trace_names(block):
    return {label: {"tensor_name": block.get("outputs", {}).get(label)}
            for label in TRACE_LABELS if label != "input"}


if __name__ == "__main__":
    main()
