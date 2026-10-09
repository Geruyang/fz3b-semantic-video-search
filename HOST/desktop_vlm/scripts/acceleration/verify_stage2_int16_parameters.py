"""Independently recompute B-scale DW3/DW7 INT8 weights and INT32 biases."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper


EXPECTED_MODEL_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
DW3 = "/image_encoder/model/network.2/network.2.0/token_mixer/reparam_conv/Conv"
DW7 = "/image_encoder/model/network.2/network.2.0/convffn/conv/conv/Conv"


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_one(model_nodes, initializers, root, param, node_name, layer, input_scale):
    node = model_nodes[node_name]
    fp_weight = np.asarray(initializers[node.input[1]], dtype=np.float64)
    fp_bias = np.asarray(initializers[node.input[2]], dtype=np.float64)
    axis = tuple(range(1, fp_weight.ndim))
    recomputed_weight_scale = np.max(np.abs(fp_weight), axis=axis) / 127.0
    recomputed_weight_scale = np.where(recomputed_weight_scale > 0,
                                       recomputed_weight_scale, 1.0)
    quantized_weight = np.clip(np.rint(fp_weight / recomputed_weight_scale.reshape(
        (-1,) + (1,) * (fp_weight.ndim - 1))), -127, 127).astype(np.int8)
    per_channel_acc_scale = input_scale * recomputed_weight_scale
    independently_rounded_bias = np.rint(fp_bias / per_channel_acc_scale)
    limits = np.iinfo(np.int32)
    if np.any(independently_rounded_bias < limits.min) or \
            np.any(independently_rounded_bias > limits.max):
        raise OverflowError(layer + " independently recomputed quantized bias exceeds INT32")
    quantized_bias = independently_rounded_bias.astype(np.int32)

    checks = {}
    for key, expected, dtype in (
            ("weight_file", quantized_weight, np.int8),
            ("weight_scale_file", recomputed_weight_scale, np.dtype("<f8")),
            ("bias_i32_file", quantized_bias, np.dtype("<i4")),
            ("accumulator_scale_file", per_channel_acc_scale, np.dtype("<f8"))):
        file_record = param[key]
        path = root / file_record["path"]
        if _sha(path) != file_record["sha256"] or path.stat().st_size != file_record["bytes"]:
            raise ValueError(layer + " SHA/size mismatch for " + path.name)
        stored = np.fromfile(str(path), dtype=dtype)
        if stored.size != expected.size or not np.array_equal(stored.reshape(expected.shape), expected):
            raise ValueError(layer + " independently recomputed array mismatch: " + path.name)
        checks[path.name] = {"sha256": _sha(path), "exact_array_match": True,
                             "shape": list(expected.shape), "dtype": str(np.dtype(dtype))}

    requant_key = "requant_to_dw7" if layer == "dw3" else "requant_to_stage3"
    requant = param[requant_key]
    target_scale = float(requant["target_scale"])
    ratios = per_channel_acc_scale / target_scale
    muls, shifts = [], []
    for ratio in ratios:
        fraction, exponent = math.frexp(float(ratio))
        multiplier = int(round(fraction * (1 << 31)))
        if multiplier == (1 << 31):
            multiplier >>= 1
            exponent += 1
        shift = 31 - exponent
        muls.append(multiplier)
        shifts.append(shift)
    for key, values, dtype in (("multiplier_file", np.asarray(muls), np.dtype("<i4")),
                               ("shift_file", np.asarray(shifts), np.dtype("<i4"))):
        record = requant[key]
        path = root / record["path"]
        if _sha(path) != record["sha256"]:
            raise ValueError(layer + " Q31 parameter SHA mismatch: " + path.name)
        actual = np.fromfile(str(path), dtype=dtype)
        if not np.array_equal(actual, values):
            raise ValueError(layer + " Q31 coefficient mismatch: " + path.name)
        checks[path.name] = {"sha256": _sha(path), "exact_array_match": True,
                             "shape": list(actual.shape), "dtype": str(np.dtype(dtype))}
    ratio_record = requant["represented_ratio_file"]
    ratio_path = root / ratio_record["path"]
    ratios_saved = np.fromfile(str(ratio_path), dtype="<f8")
    represented = np.asarray(muls, dtype=np.float64) / np.exp2(np.asarray(shifts, dtype=np.float64))
    if not np.array_equal(ratios_saved, represented):
        raise ValueError(layer + " Q31 represented ratio file mismatch")
    checks[ratio_path.name] = {"sha256": _sha(ratio_path), "exact_array_match": True,
                               "max_abs_ratio_error": float(np.max(np.abs(represented - ratios)))}
    return {"input_scale": input_scale, "quantized_bias_int32_minmax": [
                int(quantized_bias.min()), int(quantized_bias.max())],
            "bias_rounding": "independently recomputed np.rint ties-to-even",
            "parameters": checks}


def verify(args):
    root = Path(args.stage2_b)
    manifest_path = root / "manifest.json"
    manifest_sha = _sha(manifest_path)
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    model_path = Path(args.model)
    if _sha(model_path) != EXPECTED_MODEL_SHA256 or report["source_model_sha256"] != EXPECTED_MODEL_SHA256:
        raise ValueError("source model SHA mismatch")
    if report["status"] != "STAGE2_B_INT16_ACTIVATION_INT8_WEIGHT_CPU_ABLATION_NOT_PL":
        raise ValueError("unexpected stage2 B status")
    model = onnx.load(str(model_path))
    nodes = {item.name: item for item in model.graph.node}
    initializers = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    scales = report["activation_quantization"]["scales"]
    stages = report["stage2_jtag_parameters"]
    checks = {
        "dw3": _verify_one(nodes, initializers, root, stages["dw3"], DW3,
                           "dw3", float(scales["pre_dw3"])),
        "dw7": _verify_one(nodes, initializers, root, stages["dw7"], DW7,
                           "dw7", float(scales["dw3_middle_to_dw7"])),
    }
    result = {"status": "PASS_INDEPENDENT_B_DW_BIAS_WEIGHT_Q31_RECOMPUTE",
              "stage2_b_manifest_path": str(manifest_path),
              "stage2_b_manifest_sha256": manifest_sha,
              "source_model_sha256": EXPECTED_MODEL_SHA256,
              "checks": checks,
              "note": "weights/scales and scale-specific quantized biases were recomputed from pinned ONNX FP32 initializers; no stage2 INT8-007 bias file was read"}
    if getattr(args, "report", None):
        report_path = Path(args.report)
        report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                               encoding="utf-8")
        result["verification_report_path"] = str(report_path)
        result["verification_report_sha256"] = _sha(report_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage2-b", required=True)
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--report")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
