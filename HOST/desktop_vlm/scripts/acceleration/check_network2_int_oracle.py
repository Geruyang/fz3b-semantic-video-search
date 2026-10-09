"""Validate network.2 integer-oracle manifests and every referenced SHA."""
from __future__ import print_function

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

STAGE3_004_SHA256 = "164fdff3ab1a09e0b6282f4281ed09e7846cb44ace36ddbdca86ab57237e94c7"
BOARD_TRACE_SHA256 = "0d29af9faab0557f453cf64d31ed76e09fc63d92c569906a7de2abb24d8c4d82"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest_data(manifest, require_board=False, require_complete=False):
    provenance = manifest.get("provenance", {})
    mode = provenance.get("mode")
    expected_status = ("NETWORK2_INT_ORACLE_BOARD_PS_CALIBRATED_CPU_NOT_PL"
                       if mode == "BOARD_PS" else
                       "NETWORK2_INT_ORACLE_HOST_ONLY_NOT_BOARD_PS_OR_PL")
    if manifest.get("status") != expected_status:
        raise ValueError("oracle status does not agree with provenance mode")
    if mode not in ("HOST_ONLY", "BOARD_PS"):
        raise ValueError("unknown or missing provenance mode")
    if require_board and mode != "BOARD_PS":
        raise ValueError("HOST_ONLY artifact cannot satisfy board-PS requirement")
    if mode == "HOST_ONLY" and manifest.get("board_golden_claim"):
        raise ValueError("HOST_ONLY artifact must not claim board golden status")
    if int(manifest.get("block_count", -1)) != 12:
        raise ValueError("oracle manifest must cover 12 blocks")
    if require_complete and manifest.get("artifact_completeness") != "FULL_CASCADE":
        raise ValueError("parameter-only artifact is not a full 12-block cascade report")
    if require_complete and not manifest.get("checks", {}).get("full_feature_metrics_and_rank"):
        raise ValueError("full feature metrics and ranking were not produced")
    if require_complete and (len(manifest.get("results", [])) != 3 or any(
            len(item.get("block_metrics", [])) != 12 for item in manifest.get("results", []))):
        raise ValueError("full cascade requires 3 samples and 12 checked blocks per sample")
    blocks = manifest.get("blocks")
    if not isinstance(blocks, list) or len(blocks) != 12:
        raise ValueError("oracle manifest missing 12 block submanifests")
    expected = set(range(12))
    actual = set(int(item.get("index", -1)) for item in blocks)
    if actual != expected:
        raise ValueError("block submanifest indices are incomplete or duplicated")
    if not manifest.get("dependencies"):
        raise ValueError("manifest must explicitly pin source dependencies")
    return True


def validate_oracle_directory(directory, require_board=False, require_complete=False):
    directory = Path(directory)
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest_data(manifest, require_board=require_board,
                           require_complete=require_complete)
    checked = []
    for record in _all_file_records(manifest):
        relative = record["path"]
        candidate = (directory / relative).resolve()
        try:
            candidate.relative_to(directory.resolve())
        except ValueError:
            raise ValueError("manifest path escapes artifact directory")
        if not candidate.is_file():
            raise ValueError("referenced artifact file is missing: %s" % relative)
        actual_sha = sha256_file(candidate)
        if actual_sha != record.get("sha256"):
            raise ValueError("SHA mismatch for %s" % relative)
        if candidate.stat().st_size != int(record.get("bytes", -1)):
            raise ValueError("byte count mismatch for %s" % relative)
        checked.append(relative)
    for block in manifest["blocks"]:
        if block.get("parameter_manifest_sha256") != block.get("verified_parameter_manifest_sha256"):
            raise ValueError("block submanifest identity is not verified from disk")
    return {"valid": True, "provenance_mode": manifest["provenance"]["mode"],
            "verified_file_count": len(checked), "files": checked}


def _all_file_records(manifest):
    for value in manifest.get("files", {}).values():
        if isinstance(value, dict) and "path" in value:
            yield value
    for block in manifest.get("blocks", []):
        value = block.get("parameter_manifest")
        if isinstance(value, dict) and "path" in value:
            yield value
        for record in block.get("files", {}).values():
            if isinstance(record, dict) and "path" in record:
                yield record


def _array_from_record(root, record):
    path = (Path(root) / record["path"]).resolve()
    try:
        path.relative_to(Path(root).resolve())
    except ValueError:
        raise ValueError("array path escapes artifact directory")
    raw = path.read_bytes()
    if len(raw) != int(record.get("bytes", -1)) or sha256_file(path) != record.get("sha256"):
        raise ValueError("parameter/result file SHA or byte count mismatch: %s" % path)
    dtype = np.dtype(record["dtype"])
    if len(raw) % dtype.itemsize:
        raise ValueError("binary file byte count is not aligned to dtype")
    value = np.frombuffer(raw, dtype=dtype)
    shape = tuple(record["shape"])
    if value.size != int(np.prod(shape)):
        raise ValueError("binary file shape mismatch: %s" % path)
    return value.reshape(shape).copy()


def _round_shift_even_independent(values, shift):
    if shift < 0 or shift > 62:
        raise ValueError("independent Q31 shift outside [0,62]")
    source = np.asarray(values, dtype=np.int64)
    if shift == 0:
        return source.copy()
    divisor = 1 << shift
    flat = source.reshape(-1)
    result = np.empty(flat.shape, dtype=np.int64)
    for index, signed in enumerate(flat):
        value = int(signed)
        negative = value < 0
        magnitude = -value if negative else value
        quotient, remainder = divmod(magnitude, divisor)
        if remainder * 2 > divisor or (remainder * 2 == divisor and quotient & 1):
            quotient += 1
        result[index] = -quotient if negative else quotient
    return result.reshape(source.shape)


def _q31_independent(values, multipliers, shifts, clip=None):
    data = np.asarray(values)
    if data.ndim != 3 or data.dtype.kind not in "iu":
        raise ValueError("independent Q31 input must be integer CHW")
    mult = np.asarray(multipliers, dtype=np.int32).reshape(-1)
    shift = np.asarray(shifts, dtype=np.int32).reshape(-1)
    if mult.shape != shift.shape or mult.size not in (1, data.shape[0]):
        raise ValueError("independent Q31 channel parameter shape mismatch")
    out = np.empty(data.shape, dtype=np.int64)
    for channel in range(data.shape[0]):
        ci = 0 if mult.size == 1 else channel
        product = data[channel].astype(np.int64) * np.int64(mult[ci])
        if product.size and int(np.max(np.abs(product))) > (1 << 62):
            raise OverflowError("independent Q31 multiplication exceeds signed int64 range")
        out[channel] = _round_shift_even_independent(product, int(shift[ci]))
    if clip is None:
        return out
    return np.clip(out, clip[0], clip[1]).astype(np.int16)


def _checked_bias_independent(raw, bias):
    raw = np.asarray(raw, dtype=np.int64)
    bias = np.asarray(bias, dtype=np.int64).reshape(-1)
    limits = np.iinfo(np.int32)
    if raw.ndim != 3 or raw.shape[0] != bias.size:
        raise ValueError("independent accumulation/bias shape mismatch")
    if np.any(raw < limits.min) or np.any(raw > limits.max):
        raise OverflowError("independent raw INT64 accumulation does not fit INT32")
    total = raw + bias[:, None, None]
    if np.any(total < limits.min) or np.any(total > limits.max):
        raise OverflowError("independent raw+bias does not fit INT32")
    return total.astype(np.int32)


def _depthwise_independent(qinput, flat_weights, kernel):
    channels, height, width = qinput.shape
    weights = np.asarray(flat_weights, dtype=np.int8).reshape((channels, kernel, kernel))
    padded = np.pad(qinput.astype(np.int64), ((0, 0), (kernel // 2, kernel // 2),
                                              (kernel // 2, kernel // 2)), mode="constant")
    raw = np.zeros((channels, height, width), dtype=np.int64)
    for row in range(kernel):
        for column in range(kernel):
            raw += padded[:, row:row + height, column:column + width] * \
                   weights[:, row, column].astype(np.int64)[:, None, None]
    return raw


def _pointwise_independent(qinput, weights_oi):
    channels, height, width = qinput.shape
    weights = np.asarray(weights_oi, dtype=np.int8)
    rows = qinput.transpose(1, 2, 0).reshape((height * width, channels)).astype(np.int64)
    return (rows @ weights.astype(np.int64).T).T.reshape((weights.shape[0], height, width))


def _trace_sample_records(trace):
    if "host_reference" in trace:
        return trace["host_reference"].get("samples", []), "HOST_ONLY"
    return trace.get("cases", []), "BOARD_PS"


def _trace_files(sample, mode):
    if mode == "HOST_ONLY":
        return sample.get("files", [])
    result = []
    blocks = sample.get("blocks", [])
    if isinstance(blocks, dict):
        def get_index(pair):
            return int(pair[1].get("index", str(pair[0]).replace("block-", "")))
        blocks = [entry for key, entry in sorted(blocks.items(), key=get_index)]
    for index, block in enumerate(blocks):
        items = block.get("files", {})
        if isinstance(items, dict):
            for label, item in items.items():
                copied = dict(item)
                copied.setdefault("block", index)
                copied.setdefault("label", label)
                if copied.get("path") and not Path(copied["path"]).is_absolute():
                    copied["path"] = str(Path(_sample_identity(sample)) / copied["path"])
                result.append(copied)
        else:
            for item in items:
                copied = dict(item)
                if copied.get("path") and not Path(copied["path"]).is_absolute():
                    copied["path"] = str(Path(_sample_identity(sample)) / copied["path"])
                result.append(copied)
    return result


def _sample_identity(sample):
    return sample.get("sample_id") or sample.get("id") or sample.get("case_id")


def _sample_input_sha(sample):
    source = sample.get("source_input", {})
    return sample.get("input_sha256") or (source.get("sha256") if isinstance(source, dict) else None)


def _load_trace_input(trace_path, sample, mode):
    records = [item for item in _trace_files(sample, mode)
               if int(item.get("block", -1)) == 0 and item.get("label") == "input"]
    if len(records) != 1:
        raise ValueError("source trace must contain exactly one block-0 input")
    record = records[0]
    path = (Path(trace_path).resolve().parent / record["path"]).resolve()
    raw = path.read_bytes()
    if len(raw) != int(record["bytes"]) or sha256_file(path) != record["sha256"]:
        raise ValueError("source pre-DW3 trace tensor SHA mismatch")
    if record.get("dtype") != "<f4" or record.get("shape") != [1, 128, 32, 32]:
        raise ValueError("source pre-DW3 trace tensor must be [1,128,32,32] little-endian f32")
    return np.frombuffer(raw, dtype="<f4").reshape((128, 32, 32)).copy()


def _independent_block(qinput, arrays, scales):
    bias = arrays["bias_i32"].reshape(-1)
    multiplier = arrays["multiplier_i32"].reshape(-1)
    shift = arrays["shift_i32"].reshape(-1)
    qdw3_acc_raw = _depthwise_independent(qinput, arrays["dw3_weights"], 3)
    qdw3_acc = _checked_bias_independent(qdw3_acc_raw, bias[0:128])
    qdw3 = _q31_independent(qdw3_acc, multiplier[0:128], shift[0:128], (-32767, 32767))
    qdw7_acc_raw = _depthwise_independent(qdw3, arrays["dw7_weights"], 7)
    qdw7_acc = _checked_bias_independent(qdw7_acc_raw, bias[128:256])
    qdw7 = _q31_independent(qdw7_acc, multiplier[128:256], shift[128:256], (-32767, 32767))
    pw1_acc_raw = _pointwise_independent(qdw7, arrays["pw1_weights"])
    pw1_acc = _checked_bias_independent(pw1_acc_raw, bias[256:640])
    pw1 = _q31_independent(pw1_acc, multiplier[256:640], shift[256:640], (-32767, 32767))
    encoded = pw1.astype(np.int32) + 32768
    gelu = arrays["gelu_lut"][encoded]
    pw2_acc_raw = _pointwise_independent(gelu, arrays["pw2_weights"])
    pw2_acc = _checked_bias_independent(pw2_acc_raw, bias[640:768])
    pw2 = _q31_independent(pw2_acc, multiplier[640:768], shift[640:768], (-32767, 32767))
    scale_branch = _q31_independent(pw2, arrays["scale_multiplier_i32"],
                                    arrays["scale_shift_i32"], None)
    residual_branch = _q31_independent(qdw3, arrays["residual_multiplier_i32"],
                                       arrays["residual_shift_i32"], None)
    output = np.clip(scale_branch + residual_branch, -32767, 32767).astype(np.int16)
    stages = {"dw3": qdw3, "dw7": qdw7, "pw1": pw1, "gelu": gelu,
              "pw2_acc_bias_included": pw2_acc, "scale": scale_branch,
              "residual": residual_branch, "add": output}
    accumulators = {"dw3": (qdw3_acc_raw, qdw3_acc), "dw7": (qdw7_acc_raw, qdw7_acc),
                    "pw1": (pw1_acc_raw, pw1_acc), "pw2": (pw2_acc_raw, pw2_acc)}
    return output, stages, accumulators


def _q31_pair_independent(ratio, signed=False):
    ratio = float(ratio)
    if not math.isfinite(ratio) or (ratio == 0.0 and not signed):
        raise ValueError("invalid independent Q31 ratio")
    if ratio == 0.0:
        return 0, 0
    fraction, exponent = math.frexp(abs(ratio))
    multiplier = int(round(fraction * (1 << 31)))
    if multiplier == (1 << 31):
        multiplier >>= 1
        exponent += 1
    shift = 31 - exponent
    if not 0 <= shift <= 62:
        raise ValueError("independent Q31 ratio outside frozen coefficient range")
    if ratio < 0:
        multiplier = -multiplier
    return multiplier, shift


def _assert_same_array(actual, expected, description):
    if not np.array_equal(actual, expected):
        raise ValueError("independent recalculation mismatch: %s" % description)


def _verify_frozen_parameters(arrays):
    labels = ("input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")
    scales = dict(zip(labels, np.asarray(arrays["boundary_scales_f64"], dtype=np.float64)))
    layers = [
        ("dw3", 0, 128, arrays["dw3_weight_f32"], arrays["dw3_weights"], arrays["dw3_weight_scales_f64"], arrays["dw3_accumulator_scales_f64"], scales["input"], scales["dw3"]),
        ("dw7", 128, 128, arrays["dw7_weight_f32"], arrays["dw7_weights"], arrays["dw7_weight_scales_f64"], arrays["dw7_accumulator_scales_f64"], scales["dw3"], scales["dw7"]),
        ("pw1", 256, 384, arrays["pw1_weight_f32"], arrays["pw1_weights"], arrays["pw1_weight_scales_f64"], arrays["pw1_accumulator_scales_f64"], scales["dw7"], scales["pw1"]),
        ("pw2", 640, 128, arrays["pw2_weight_f32"], arrays["pw2_weights"], arrays["pw2_weight_scales_f64"], arrays["pw2_accumulator_scales_f64"], scales["gelu"], scales["pw2"]),
    ]
    all_bias = arrays["bias_i32"].reshape(-1)
    float_bias = arrays["bias_f32"].reshape(-1)
    q31_m = arrays["multiplier_i32"].reshape(-1)
    q31_s = arrays["shift_i32"].reshape(-1)
    for name, offset, count, fpweight, qweight, weight_scales, acc_scales, in_scale, out_scale in layers:
        fp = np.asarray(fpweight, dtype=np.float64)
        reduce_axes = tuple(range(1, fp.ndim))
        maximum = np.max(np.abs(fp), axis=reduce_axes)
        expected_scales = np.where(maximum > 0.0, maximum / 127.0, 1.0)
        _assert_same_array(np.asarray(weight_scales), expected_scales, name + " weight scales")
        reshape = (expected_scales.shape[0],) + (1,) * (fp.ndim - 1)
        expected_q = np.clip(np.rint(fp / expected_scales.reshape(reshape)), -127, 127).astype(np.int8)
        _assert_same_array(np.asarray(qweight, dtype=np.int8), expected_q, name + " INT8 weights")
        expected_acc = expected_scales * in_scale
        _assert_same_array(np.asarray(acc_scales), expected_acc, name + " accumulator scales")
        b = np.rint(float_bias[offset:offset + count].astype(np.float64) / expected_acc)
        limits = np.iinfo(np.int32)
        if np.any(b < limits.min) or np.any(b > limits.max):
            raise OverflowError(name + " independently quantized bias exceeds INT32")
        _assert_same_array(all_bias[offset:offset + count], b.astype(np.int32), name + " bias")
        for channel, ratio in enumerate(expected_acc / out_scale):
            expected_m, expected_s = _q31_pair_independent(ratio)
            if int(q31_m[offset + channel]) != expected_m or int(q31_s[offset + channel]) != expected_s:
                raise ValueError("independent Q31 parameters mismatch: %s[%d]" % (name, channel))
    gamma = np.asarray(arrays["residual_scale_f32"], dtype=np.float64)
    if gamma.size != 128:
        raise ValueError("residual multiplier must have 128 channels")
    for channel, ratio in enumerate(gamma * scales["pw2"] / scales["add"]):
        expected_m, expected_s = _q31_pair_independent(ratio, signed=True)
        if (int(arrays["scale_multiplier_i32"][channel]) != expected_m or
                int(arrays["scale_shift_i32"][channel]) != expected_s):
            raise ValueError("scale-to-Add Q31 coefficients mismatch at channel %d" % channel)
    expected_m, expected_s = _q31_pair_independent(scales["dw3"] / scales["add"])
    if (int(arrays["residual_multiplier_i32"][0]) != expected_m or
            int(arrays["residual_shift_i32"][0]) != expected_s):
        raise ValueError("residual-to-Add Q31 coefficients mismatch")
    lut = np.empty((65536,), dtype=np.int16)
    for encoded in range(65536):
        signed_code = encoded - 32768
        x = signed_code * scales["pw1"]
        y = 0.5 * x * (1.0 + math.erf(x / math.sqrt(2.0)))
        lut[encoded] = np.int16(np.clip(np.rint(y / scales["gelu"]), -32767, 32767))
    _assert_same_array(arrays["gelu_lut"], lut, "GELU LUT")
    return scales


def _verify_model_initializers(model_path, trace_blocks, root, submanifests):
    """Bind saved float parameters to the exact initializers of the pinned ONNX."""
    try:
        import onnx
        from onnx import numpy_helper
    except ImportError:
        raise RuntimeError("onnx is required to verify model initializer provenance")
    model = onnx.load(str(model_path))
    nodes = {node.name: node for node in model.graph.node}
    initializers = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    layer_specs = (("dw3", 0, 128, "dw3_weight_f32"),
                   ("dw7", 128, 128, "dw7_weight_f32"),
                   ("pw1", 256, 384, "pw1_weight_f32"),
                   ("pw2", 640, 128, "pw2_weight_f32"))
    checked = 0
    for index, (trace_block, submanifest) in enumerate(zip(trace_blocks, submanifests)):
        params = submanifest["parameters"]
        arrays = {name: _array_from_record(root, record) for name, record in params.items()}
        biases = arrays["bias_f32"].reshape(-1)
        for label, offset, count, weight_key in layer_specs:
            node_name = trace_block["nodes"][label]
            node = nodes.get(node_name)
            if node is None or len(node.input) < 3:
                raise ValueError("bound ONNX node/weight/bias missing: block %d %s" % (index, label))
            weight_name, bias_name = node.input[1], node.input[2]
            if weight_name not in initializers or bias_name not in initializers:
                raise ValueError("bound ONNX initializer missing: block %d %s" % (index, label))
            source_weight = np.asarray(initializers[weight_name])
            source_bias = np.asarray(initializers[bias_name])
            expected_weight_shape = ((128, 1, 3, 3) if label == "dw3" else
                                     (128, 1, 7, 7) if label == "dw7" else
                                     (384, 128, 1, 1) if label == "pw1" else
                                     (128, 384, 1, 1))
            expected_saved_shape = ((128, 9) if label == "dw3" else
                                    (128, 49) if label == "dw7" else
                                    (384, 128) if label == "pw1" else (128, 384))
            if source_weight.dtype != np.dtype("float32") or source_weight.shape != expected_weight_shape:
                raise ValueError("ONNX weight dtype/shape mismatch: block %d %s" % (index, label))
            if source_bias.dtype != np.dtype("float32") or source_bias.shape != (count,):
                raise ValueError("ONNX bias dtype/shape mismatch: block %d %s" % (index, label))
            shaped_weight = (source_weight.reshape(expected_saved_shape) if label.startswith("dw")
                             else source_weight[:, :, 0, 0])
            _assert_same_array(arrays[weight_key], shaped_weight,
                               "pinned ONNX block %d %s weight initializer" % (index, label))
            _assert_same_array(biases[offset:offset + count], source_bias,
                               "pinned ONNX block %d %s bias initializer" % (index, label))
            checked += 2
        scale_node = nodes.get(trace_block["nodes"]["scale"])
        gamma_name = next((name for name in scale_node.input if name in initializers), None) \
            if scale_node is not None else None
        if gamma_name is None:
            raise ValueError("ONNX residual scale initializer missing: block %d" % index)
        gamma = np.asarray(initializers[gamma_name])
        if gamma.dtype != np.dtype("float32") or gamma.shape not in ((128,), (128, 1, 1)):
            raise ValueError("ONNX residual scale dtype/shape mismatch: block %d" % index)
        _assert_same_array(arrays["residual_scale_f32"], gamma.reshape(-1),
                           "pinned ONNX block %d residual scale initializer" % index)
        checked += 1
    return {"valid": True, "source_model_sha256": sha256_file(model_path),
            "blocks_checked": len(trace_blocks), "initializer_arrays_checked": checked}


def _load_trace_entry(trace_path, entry):
    path = (Path(trace_path).resolve().parent / entry["path"]).resolve()
    raw = path.read_bytes()
    if len(raw) != int(entry["bytes"]) or sha256_file(path) != entry["sha256"]:
        raise ValueError("trace tensor file integrity mismatch: %s" % path)
    if entry.get("dtype") != "<f4":
        raise ValueError("trace tensors must be little-endian float32")
    return np.frombuffer(raw, dtype="<f4").reshape(entry["shape"]).copy()


def _trace_entry_map(sample, mode):
    if mode == "HOST_ONLY":
        records = sample.get("files", [])
    else:
        records = _trace_files(sample, mode)
    return {(int(item["block"]), item["label"]): item for item in records}


def _verify_calibration_scales(trace_path, trace_samples, mode):
    maxima = [{label: 0.0 for label in ("input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")}
              for unused in range(12)]
    for sample in trace_samples:
        entries = _trace_entry_map(sample, mode)
        for index in range(12):
            if index < 11:
                left = entries[(index, "add")]
                right = entries[(index + 1, "input")]
                if left.get("sha256") != right.get("sha256"):
                    raise ValueError("trace Add->next input is not byte-identical within sample")
            for label in ("dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add"):
                values = _load_trace_entry(trace_path, entries[(index, label)])
                maxima[index][label] = max(maxima[index][label],
                                            float(np.max(np.abs(values.astype(np.float64)))))
            if index == 0:
                values = _load_trace_entry(trace_path, entries[(0, "input")])
                maxima[index]["input"] = max(maxima[index]["input"],
                                              float(np.max(np.abs(values.astype(np.float64)))))
    calibrated = []
    for index in range(12):
        record = {label: (maximum / 32767.0 if maximum else 1.0)
                  for label, maximum in maxima[index].items()}
        if index:
            record["input"] = calibrated[index - 1]["add"]
        calibrated.append(record)
    return calibrated


def _metric_independent(actual, expected):
    a, b = np.asarray(actual, dtype=np.float64), np.asarray(expected, dtype=np.float64)
    delta = a - b
    af, bf = a.reshape(-1), b.reshape(-1)
    return {"shape": list(a.shape), "max_abs": float(np.max(np.abs(delta))),
            "rms_abs": float(np.sqrt(np.mean(delta * delta))),
            "cosine": float(np.dot(af, bf) / max(float(np.linalg.norm(af) * np.linalg.norm(bf)), 1e-30)),
            "allclose_rtol_1e-4_atol_1e-5": bool(np.allclose(a, b, rtol=1e-4, atol=1e-5))}


def _validate_rank_flags(qrank, rrank, sample_record):
    if (qrank != sample_record.get("quantized_ranking") or
            rrank != sample_record.get("reference_ranking")):
        raise ValueError("independent final text ranking mismatch: %s" % sample_record.get("sample_id"))
    if (qrank[0] != sample_record.get("quantized_top1") or
            rrank[0] != sample_record.get("reference_top1") or
            (qrank == rrank) != sample_record.get("full_rank_matches") or
            (qrank[0] != rrank[0]) != sample_record.get("top1_changed")):
        raise ValueError("independent top1/full-rank flags mismatch")


def _assert_metric_record(actual, stored, description):
    if actual["shape"] != stored.get("shape") or actual["allclose_rtol_1e-4_atol_1e-5"] != \
            stored.get("allclose_rtol_1e-4_atol_1e-5"):
        raise ValueError("metric boolean/shape mismatch: %s" % description)
    for key in ("max_abs", "rms_abs", "cosine"):
        if abs(float(actual[key]) - float(stored.get(key, float("nan")))) > 1e-12:
            raise ValueError("metric numeric mismatch: %s %s" % (description, key))


def _sha_array(array, dtype):
    return hashlib.sha256(np.ascontiguousarray(array, dtype=dtype).tobytes()).hexdigest()


def _independent_expected_checksums(stages, accumulators):
    dtypes = {"dw3": "<i2", "dw7": "<i2", "pw1": "<i2", "gelu": "<i2",
              "pw2_acc_bias_included": "<i4", "scale": "<i8", "residual": "<i8",
              "add": "<i2"}
    values = dict(stages)
    result = {name: {"dtype": dtype, "shape": list(values[name].shape),
                     "sha256": _sha_array(values[name], dtype)} for name, dtype in dtypes.items()}
    for name, (raw, biased) in accumulators.items():
        result[name + "_raw_i64"] = {"dtype": "<i8", "shape": list(raw.shape),
                                      "sha256": _sha_array(raw, "<i8")}
        result[name + "_bias_included_i32"] = {"dtype": "<i4", "shape": list(biased.shape),
                                               "sha256": _sha_array(biased, "<i4")}
    return result


def _independent_bounds(arrays, accumulators):
    result = {}
    specs = (("dw3", "dw3_weights", slice(0, 128), (1,)),
             ("dw7", "dw7_weights", slice(128, 256), (1,)),
             ("pw1", "pw1_weights", slice(256, 640), (1,)),
             ("pw2", "pw2_weights", slice(640, 768), (1,)))
    biases = arrays["bias_i32"].reshape(-1)
    for name, weight_key, bias_slice, axes in specs:
        weight = np.asarray(arrays[weight_key], dtype=np.int64)
        l1 = np.sum(np.abs(weight), axis=axes)
        worst = l1 * 32767 + np.abs(biases[bias_slice].astype(np.int64))
        raw, total = accumulators[name]
        result[name] = {"actual_raw_min": int(np.min(raw)), "actual_raw_max": int(np.max(raw)),
                        "actual_bias_included_min": int(np.min(total)),
                        "actual_bias_included_max": int(np.max(total)),
                        "actual_abs_max_bias_included": int(np.max(np.abs(total.astype(np.int64)))),
                        "actual_raw_and_bias_fit_int32": True,
                        "worst_case_abs_including_bias": int(np.max(worst)),
                        "worst_case_fits_int32": bool(np.all(worst <= np.iinfo(np.int32).max))}
    return result


def _verify_feature_metrics_and_rank(root, manifest, sample_record, text_features, text_ids):
    qfeature = _array_from_record(root, sample_record["quantized_feature_file"]).astype(np.float64)
    reference = _array_from_record(root, sample_record["reference_feature_file"]).astype(np.float64)
    if qfeature.shape != (1, 512) or reference.shape != (1, 512):
        raise ValueError("saved suffix features must be [1,512]")
    metric = _metric_independent(qfeature, reference)
    _assert_metric_record(metric, sample_record["feature_metrics_quantized_vs_reference"],
                          sample_record["sample_id"] + " final feature")

    def ranking(feature):
        image = feature.reshape(-1)
        image = image / max(float(np.linalg.norm(image)), 1e-30)
        text = text_features.astype(np.float64)
        text = text / np.maximum(np.linalg.norm(text, axis=1, keepdims=True), 1e-30)
        scores = image @ text.T
        order = np.argsort(-scores, kind="stable")
        return [text_ids[int(i)] for i in order]
    qrank, rrank = ranking(qfeature), ranking(reference)
    _validate_rank_flags(qrank, rrank, sample_record)


def verify_numeric_oracle(directory, require_board=False):
    """Independent int64/Q31 replay; deliberately does not call builder.execute_block."""
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    validate_manifest_data(manifest, require_board=require_board, require_complete=True)
    trace_ref = manifest["source_trace_manifest"]
    trace_path = Path(trace_ref["path"])
    if sha256_file(trace_path) != trace_ref["sha256"]:
        raise ValueError("pinned source trace manifest SHA mismatch")
    model_ref = manifest["source_model"]
    if sha256_file(model_ref["path"]) != model_ref["sha256"]:
        raise ValueError("pinned source ONNX SHA mismatch")
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace_samples, mode = _trace_sample_records(trace)
    if mode == "BOARD_PS" and sha256_file(trace_path) != BOARD_TRACE_SHA256:
        raise ValueError("BOARD_PS oracle source is not the pinned board collection manifest")
    expected_mode = manifest["provenance"]["mode"]
    if mode != expected_mode:
        raise ValueError("artifact and source trace provenance modes differ")
    result_by_id = {item["sample_id"]: item for item in manifest.get("results", [])}
    blocks_by_index = {int(item["index"]): item for item in manifest["blocks"]}
    ordered_submanifests = []
    for index in range(12):
        subref = blocks_by_index[index]["parameter_manifest"]
        subpath = root / subref["path"]
        if sha256_file(subpath) != subref["sha256"]:
            raise ValueError("block parameter submanifest SHA mismatch: block %d" % index)
        ordered_submanifests.append(json.loads(subpath.read_text(encoding="utf-8")))
    model_initializer_check = _verify_model_initializers(
        model_ref["path"], trace["blocks"], root, ordered_submanifests)
    calibrated_scales = _verify_calibration_scales(trace_path, trace_samples, mode)
    verified_boundaries = 0
    for sample in trace_samples:
        sample_id = _sample_identity(sample)
        if sample_id not in result_by_id:
            raise ValueError("full cascade result missing sample %s" % sample_id)
        result = result_by_id[sample_id]
        if result.get("input_sha256") != _sample_input_sha(sample):
            raise ValueError("cascade result input SHA mismatch for %s" % sample_id)
        if mode == "BOARD_PS":
            board_feature = sample.get("feature", sample.get("suffix_feature"))
            saved_reference = result.get("reference_feature_file", {})
            if not isinstance(board_feature, dict) or not board_feature.get("path") or \
                    board_feature.get("sha256") != saved_reference.get("sha256"):
                raise ValueError("saved feature is not the same-run BOARD_PS suffix feature")
            board_feature_path = (trace_path.parent / board_feature["path"]).resolve()
            if not board_feature_path.is_file() or \
                    board_feature_path.stat().st_size != int(board_feature.get("bytes", -1)) or \
                    sha256_file(board_feature_path) != board_feature.get("sha256") or \
                    board_feature.get("dtype") != "<f4" or board_feature.get("shape") != [1, 512]:
                raise ValueError("same-run BOARD_PS suffix feature source failed its pinned file check")
            source_input = sample.get("source_input", {})
            if isinstance(source_input, dict) and source_input.get("path"):
                source_input_path = (trace_path.parent / source_input["path"]).resolve()
                if source_input_path.is_file() and \
                        sha256_file(source_input_path) != _sample_input_sha(sample):
                    raise ValueError("original BOARD_PS source input file failed its pinned SHA check")
        trace_entries = _trace_entry_map(sample, mode)
        input_fp = _load_trace_entry(trace_path, trace_entries[(0, "input")])[0]
        qinput = None
        previous_add_scale = None
        for index in range(12):
            block_ref = blocks_by_index[index]
            subref = block_ref["parameter_manifest"]
            subpath = root / subref["path"]
            if sha256_file(subpath) != subref["sha256"]:
                raise ValueError("block parameter submanifest SHA mismatch: block %d" % index)
            submanifest = json.loads(subpath.read_text(encoding="utf-8"))
            parameter_records = submanifest["parameters"]
            arrays = {name: _array_from_record(root, record)
                      for name, record in parameter_records.items()}
            scales = _verify_frozen_parameters(arrays)
            for label, expected_scale in calibrated_scales[index].items():
                if scales[label] != expected_scale:
                    raise ValueError("independent PS maxabs calibration scale mismatch at block %d %s" %
                                     (index, label))
            if previous_add_scale is not None and scales["input"] != previous_add_scale:
                raise ValueError("independent replay found a cross-block requantization")
            if index == 0:
                qinput = np.clip(np.rint(input_fp.astype(np.float64) / scales["input"]),
                                 -32767, 32767).astype(np.int16)
                if float(result.get("qinput_scale", float("nan"))) != scales["input"]:
                    raise ValueError("reported qinput scale differs from pinned pre-DW3 trace")
                saved_qinput = _array_from_record(root, result["qinput_file"])
                _assert_same_array(saved_qinput[0], qinput, sample_id + " initial quantized input")
            output, stages, accumulators = _independent_block(qinput, arrays, scales)
            expected_sums = _independent_expected_checksums(stages, accumulators)
            report_block = result["block_metrics"][index]
            if report_block.get("block_index") != index:
                raise ValueError("result block sequence is not canonical")
            if expected_sums != report_block.get("stage_checksums"):
                raise ValueError("independent intermediate integer checksum mismatch at %s block %d" %
                                 (sample_id, index))
            saved_add = _array_from_record(root, report_block["add_file"])
            _assert_same_array(saved_add[0], output, "%s block %d Add output" % (sample_id, index))
            actual_bounds = _independent_bounds(arrays, accumulators)
            if actual_bounds != report_block.get("accumulator_bounds"):
                raise ValueError("independent accumulator range mismatch at %s block %d" %
                                 (sample_id, index))
            expected_labels = {"dw3": stages["dw3"].astype(np.float64) * scales["dw3"],
                               "dw7": stages["dw7"].astype(np.float64) * scales["dw7"],
                               "pw1": stages["pw1"].astype(np.float64) * scales["pw1"],
                               "gelu": stages["gelu"].astype(np.float64) * scales["gelu"],
                               "pw2": stages["pw2_acc_bias_included"].astype(np.float64) *
                                     arrays["pw2_accumulator_scales_f64"][:, None, None],
                               "scale": stages["scale"].astype(np.float64) * scales["add"],
                               "add": output.astype(np.float64) * scales["add"]}
            for label, actual in expected_labels.items():
                expected = _load_trace_entry(trace_path, trace_entries[(index, label)])[0]
                actual_metric = _metric_independent(actual, expected)
                _assert_metric_record(actual_metric, report_block["metrics"][label],
                                      "%s block %d %s" % (sample_id, index, label))
            qinput = output
            previous_add_scale = scales["add"]
            verified_boundaries += len(expected_sums)
        final_record = result["final_add_file"]
        _assert_same_array(_array_from_record(root, final_record)[0], qinput,
                           sample_id + " final Add cascade")
    if len(result_by_id) != len(trace_samples):
        raise ValueError("cascade contains unexpected or duplicate sample results")

    if manifest.get("artifact_completeness") == "FULL_CASCADE":
        text_ref = manifest.get("text_feature_reference")
        if not text_ref:
            raise ValueError("full cascade report lacks pinned text feature copy")
        text_features = _array_from_record(root, text_ref)
        if text_features.shape != (8, 512):
            raise ValueError("text feature copy shape mismatch")
        stage3_dependency = next(item for item in manifest["dependencies"]
                                 if item.get("role") == "stage3_004_manifest")
        if (stage3_dependency["sha256"] != STAGE3_004_SHA256 or
                sha256_file(stage3_dependency["path"]) != stage3_dependency["sha256"]):
            raise ValueError("pinned Stage3-004 manifest SHA mismatch")
        stage3_reference = json.loads(Path(stage3_dependency["path"]).read_text(encoding="utf-8"))
        text_file_record = next(item for item in manifest["files"].values()
                                if item.get("path") == text_ref.get("path"))
        if (text_file_record["sha256"] != stage3_reference.get("text_features_sha256") or
                text_ref["sha256"] != stage3_reference.get("text_features_sha256")):
            raise ValueError("copied text feature SHA differs from frozen Stage3-004 reference")
        text_dependency = next(item for item in manifest["dependencies"]
                               if item.get("role") == "text_manifest")
        text_manifest_path = Path(text_dependency["path"])
        if sha256_file(text_manifest_path) != text_dependency["sha256"]:
            raise ValueError("pinned text manifest SHA mismatch")
        if text_dependency["sha256"] != stage3_reference.get("text_manifest_sha256"):
            raise ValueError("text manifest dependency differs from frozen Stage3-004 reference")
        text_manifest = json.loads(text_manifest_path.read_text(encoding="utf-8"))
        text_ids = [item["id"] for item in text_manifest["prompts"]]
        for result in result_by_id.values():
            _verify_feature_metrics_and_rank(root, manifest, result, text_features, text_ids)
    return {"valid": True, "independent_integer_replay": True,
            "verified_samples": len(trace_samples), "verified_blocks": len(trace_samples) * 12,
            "verified_stage_boundaries": verified_boundaries,
            "verified_model_initializers": model_initializer_check,
            "suffix_forward_replay": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--require-board", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    result = validate_oracle_directory(args.directory, args.require_board, args.require_complete)
    report = json.loads((Path(args.directory) / "manifest.json").read_text(encoding="utf-8"))
    if report.get("artifact_completeness") == "FULL_CASCADE":
        result["numeric_replay"] = verify_numeric_oracle(args.directory, args.require_board)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
