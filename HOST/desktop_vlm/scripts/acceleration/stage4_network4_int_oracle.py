"""Generate the network4 INT16/INT8 oracle from a HOST_ONLY or BOARD_PS trace.

Quantization, bias, signed Q31, ties-even, GELU LUT and saturation arithmetic
are reused from build_network2_int_oracle.py. This emits CPU oracle data only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import onnx

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import build_network2_int_oracle as n2

MODEL_SHA256 = "5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587"
BLOCK_COUNT = 20
BOUNDARY_LABELS = ("input", "dw3", "dw7", "pw1", "gelu", "pw2", "scale", "add")
INT16_LIMIT = 32767


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_array(root: Path, relative: str, array, dtype):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    packed = np.ascontiguousarray(array, dtype=dtype)
    packed.tofile(path)
    return {"path": relative.replace("\\", "/"), "dtype": dtype,
            "shape": list(packed.shape), "bytes": path.stat().st_size,
            "sha256": sha256(path)}


def load_samples(trace_path: Path, report):
    if report.get("source_model_sha256") != MODEL_SHA256:
        raise ValueError("trace source model SHA mismatch")
    if report.get("status") not in ("HOST_NETWORK4_TRACE_REFERENCE_NOT_BOARD_PS_CAPTURE",
                                     "BOARD_PS_CPU_NETWORK4_TRACE_COLLECTION"):
        raise ValueError("unknown network4 trace provenance")
    root = trace_path.resolve().parent
    samples = []
    for sample in report.get("samples", []):
        if sample.get("sample_id") not in ("image-00", "image-01", "image-02"):
            raise ValueError("unexpected/non-frozen image sample")
        blocks = [dict() for _ in range(BLOCK_COUNT)]
        seen = set()
        for item in sample.get("files", []):
            key = (int(item["block"]), item["label"])
            if key in seen or key[0] not in range(BLOCK_COUNT) or key[1] not in BOUNDARY_LABELS:
                raise ValueError("duplicate or invalid boundary entry")
            seen.add(key)
            path = root / item["path"]
            if sha256(path) != item.get("sha256") or path.stat().st_size != int(item["bytes"]):
                raise ValueError("trace tensor SHA/size mismatch: " + str(path))
            if item.get("dtype") != "<f4":
                raise ValueError("trace tensor must be little-endian float32")
            value = np.fromfile(path, dtype="<f4").reshape(item["shape"])
            if not np.isfinite(value).all():
                raise ValueError("nonfinite trace tensor")
            blocks[key[0]][key[1]] = value[0].copy()
        expected = {(i, label) for i in range(BLOCK_COUNT) for label in BOUNDARY_LABELS}
        if seen != expected:
            raise ValueError("each image requires all eight boundaries for 20 blocks")
        for i, block in enumerate(blocks):
            for label, value in block.items():
                if value.ndim != 3:
                    raise ValueError("expected CHW boundary tensors")
            if i and blocks[i]["input"].shape != blocks[i - 1]["add"].shape:
                raise ValueError("shape discontinuity across network4 Add boundary")
        samples.append({"sample_id": sample["sample_id"],
                        "input_sha256": sample["input_sha256"], "blocks": blocks})
    if len(samples) != 3 or {item["sample_id"] for item in samples} != {
            "image-00", "image-01", "image-02"}:
        raise ValueError("exactly the three frozen calibration inputs are required")
    return samples


def calibrate(samples):
    result = []
    for i in range(BLOCK_COUNT):
        current = {}
        for label in BOUNDARY_LABELS:
            maximum = max(float(np.max(np.abs(sample["blocks"][i][label].astype(np.float64))))
                          for sample in samples)
            current[label] = maximum / INT16_LIMIT if maximum else 1.0
        if i:
            # Add INT16 codes and scale are the exact next block input.
            current["input"] = result[-1]["add"]
        result.append(current)
    return result


def block_parameters(layers, scales):
    input_for = {"dw3": "input", "dw7": "dw3", "pw1": "dw7", "pw2": "gelu"}
    output_for = {"dw3": "dw3", "dw7": "dw7", "pw1": "pw1", "pw2": "pw2"}
    params = {}
    arrays = {}
    for label in ("dw3", "dw7", "pw1", "pw2"):
        layer = layers[label]
        acc_scale = layer["weight_scales"] * float(scales[input_for[label]])
        bias = n2.quantize_bias_i32(layer["bias_f32"], acc_scale)
        mult, shift = n2.q31_parameters(acc_scale / float(scales[output_for[label]]))
        qweight = layer["weight_i8"].astype(np.int8, copy=False)
        reduce_axis = tuple(range(1, qweight.ndim))
        l1 = np.sum(np.abs(qweight.astype(np.int64)), axis=reduce_axis)
        bound = l1 * INT16_LIMIT + np.abs(bias.astype(np.int64))
        if np.any(bound > np.iinfo(np.int32).max):
            raise OverflowError(f"block {label} conservative INT32 accumulation bound failed")
        params[label] = {"bias_i32": bias, "multiplier_i32": mult,
                         "shift_i32": shift, "accumulator_scales": acc_scale,
                         "worst_case_abs_including_bias": bound}
        arrays[label] = {"weights_i8": qweight, "weight_scales_f64": layer["weight_scales"],
                         "bias_i32": bias, "multiplier_i32": mult,
                         "shift_i32": shift, "accumulator_scales_f64": acc_scale}
    residual_scale = np.asarray(layers["residual_scale"], dtype=np.float64)
    params["scale_multiplier_i32"], params["scale_shift_i32"] = n2.q31_parameters(
        residual_scale * float(scales["pw2"]) / float(scales["add"]), signed=True)
    params["residual_multiplier_i32"], params["residual_shift_i32"] = n2.q31_parameters(
        np.asarray([float(scales["dw3"]) / float(scales["add"])]), signed=True)
    arrays["layer_scale_f32"] = np.asarray(layers["residual_scale"], dtype="<f4")
    arrays["scale_multiplier_i32"] = params["scale_multiplier_i32"]
    arrays["scale_shift_i32"] = params["scale_shift_i32"]
    arrays["residual_multiplier_i32"] = params["residual_multiplier_i32"]
    arrays["residual_shift_i32"] = params["residual_shift_i32"]
    arrays["gelu_lut_i16"] = n2.gelu_lut(scales["pw1"], scales["gelu"])
    arrays["activation_scales_f64"] = np.asarray(
        [scales[label] for label in BOUNDARY_LABELS], dtype="<f8")
    return params, arrays


def execute_and_write(out, model, trace, samples, scales_by_block):
    node_map = {n.name: n for n in model.graph.node}
    results = []
    block_manifests = []
    files = {}
    for index, block in enumerate(trace["blocks"]):
        layers = n2.extract_block_parameters(model, block)
        params, arrays = block_parameters(layers, scales_by_block[index])
        block_params_files = {}
        for layer, layer_arrays in arrays.items():
            if layer in ("dw3", "dw7", "pw1", "pw2"):
                for suffix, array in layer_arrays.items():
                    dtype = "|i1" if suffix == "weights_i8" else "<f8" if suffix.endswith("f64") else "<i4"
                    key = layer + "_" + suffix
                    meta = write_array(out, f"block-{index:02d}/{key}.bin", array, dtype)
                    block_params_files[key] = meta
            else:
                dtype = "<f4" if layer.endswith("f32") else "<i2" if layer.endswith("i16") else "<i4"
                meta = write_array(out, f"block-{index:02d}/{layer}.bin", layer_arrays, dtype)
                block_params_files[layer] = meta
        block_params_files["residual_scale_f32"] = write_array(
            out, f"block-{index:02d}/residual_scale_f32.bin", layers["residual_scale"], "<f4")
        block_record = {"index": index, "nodes": block["nodes"],
                        "tensor_names": {"input": block["input"], **block["outputs"]},
                        "calibration_scales": {k: float(v) for k, v in scales_by_block[index].items()},
                        "parameters": block_params_files,
                        "contracts": {"activation": "symmetric INT16 zero-point 0, ties-even, clip [-32767,32767]",
                                      "weight": "symmetric per-output-channel INT8 zero-point 0, ties-even, clip [-127,127]",
                                      "bias": "round-even(float_bias/(input_scale*weight_scale)), checked INT32",
                                      "accumulator": "independent signed INT64 raw sum; raw and bias-included value checked against INT32",
                                      "q31": "signed multiplier and nonnegative right shift; nearest ties-even",
                                      "gelu": "65536-entry exact GELU lookup; signed input code + 32768; ties-even output quantization",
                                      "scale_add": "Q31 branch rounding to INT64, INT64 branch sum, saturate once at final INT16 Add",
                                      "boundary": "Add INT16 codes and its scale pass unchanged to next input"}}
        block_manifests.append(block_record)

    for sample in samples:
        blocks_out = []
        qinput = n2.quantize_symmetric(sample["blocks"][0]["input"],
                                       scales_by_block[0]["input"], 16)
        for index, block in enumerate(trace["blocks"]):
            layers = n2.extract_block_parameters(model, block)
            params, arrays = block_parameters(layers, scales_by_block[index])
            qadd, stages = n2.execute_block(qinput, params, scales_by_block[index],
                                            layers, arrays["gelu_lut_i16"])
            prefix = f"results/{sample['sample_id']}/block-{index:02d}"
            stage_values = {
                "input_i16": (qinput, "<i2"),
                "dw3_raw_i64": (stages["accumulators"]["dw3"]["raw"], "<i8"),
                "dw3_bias_included_i32": (stages["accumulators"]["dw3"]["bias_included"], "<i4"),
                "dw3_output_i16": (stages["dw3"], "<i2"),
                "dw7_raw_i64": (stages["accumulators"]["dw7"]["raw"], "<i8"),
                "dw7_bias_included_i32": (stages["accumulators"]["dw7"]["bias_included"], "<i4"),
                "dw7_output_i16": (stages["dw7"], "<i2"),
                "pw1_raw_i64": (stages["accumulators"]["pw1"]["raw"], "<i8"),
                "pw1_bias_included_i32": (stages["accumulators"]["pw1"]["bias_included"], "<i4"),
                "pw1_output_i16": (stages["pw1"], "<i2"),
                "gelu_output_i16": (stages["gelu"], "<i2"),
                "pw2_raw_i64": (stages["accumulators"]["pw2"]["raw"], "<i8"),
                "pw2_bias_included_i32": (stages["accumulators"]["pw2"]["bias_included"], "<i4"),
                "pw2_output_i16": (n2.requantize_q31(
                    stages["pw2_acc_bias_included"], params["pw2"]["multiplier_i32"],
                    params["pw2"]["shift_i32"]), "<i2"),
                "scale_branch_i64": (stages["scale"], "<i8"),
                "residual_branch_i64": (stages["residual"], "<i8"),
                "add_output_i16": (qadd, "<i2"),
            }
            output_refs = {}
            bounds = {}
            for key, (value, dtype) in stage_values.items():
                meta = write_array(out, prefix + "-" + key + ".bin", value, dtype)
                output_refs[key] = meta
                files[meta["path"]] = {k: v for k, v in meta.items() if k != "path"}
                if key.endswith("raw_i64") or key.endswith("bias_included_i32"):
                    bounds[key] = {"min": int(value.min()), "max": int(value.max()),
                                   "fits_int32": bool(int(value.min()) >= np.iinfo(np.int32).min and
                                                       int(value.max()) <= np.iinfo(np.int32).max)}
            blocks_out.append({"index": index, "input_sha256": output_refs["input_i16"]["sha256"],
                               "outputs": output_refs, "accumulator_bounds": bounds})
            qinput = qadd
        results.append({"sample_id": sample["sample_id"], "input_sha256": sample["input_sha256"],
                        "blocks": blocks_out,
                        "final_output_sha256": blocks_out[-1]["outputs"]["add_output_i16"]["sha256"]})
    return block_manifests, results, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-manifest", required=True)
    parser.add_argument("--model", default="artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    trace_path = Path(args.trace_manifest)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    samples = load_samples(trace_path, trace)
    model_path = Path(args.model)
    if sha256(model_path) != MODEL_SHA256:
        raise ValueError("source ONNX SHA mismatch")
    model = onnx.load(str(model_path))
    scales_by_block = calibrate(samples)
    out = Path(args.output)
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")
    out.mkdir(parents=True)
    block_records, results, files = execute_and_write(out, model, trace, samples, scales_by_block)
    board_ps = trace["status"] == "BOARD_PS_CPU_NETWORK4_TRACE_COLLECTION"
    report = {
        "schema_version": 1,
        "status": "NETWORK4_BOARD_PS_CALIBRATED_INT16_ACTIVATION_INT8_WEIGHT_CPU_ORACLE_NOT_PL" if board_ps
                  else "NETWORK4_HOST_ONLY_INT16_ACTIVATION_INT8_WEIGHT_CPU_ORACLE_NOT_BOARD_PS_OR_PL",
        "source_model_sha256": MODEL_SHA256,
        "trace_manifest_sha256": sha256(trace_path),
        "trace_provenance": trace["status"],
        "pl_execution": False,
        "scope": {"first": "network.4.0", "last": "network.4.19", "block_count": BLOCK_COUNT,
                  "spatial_positions": 256, "boundary_labels": list(BOUNDARY_LABELS)},
        "shape_contract": {"block_input": {"shape": [1, 256, 16, 16], "dtype": "signed INT16 NCHW"},
                           "dw3": {"shape": [1, 256, 16, 16]},
                           "dw7": {"shape": [1, 256, 16, 16]},
                           "pw1": {"shape": [1, 768, 16, 16]},
                           "gelu": {"shape": [1, 768, 16, 16]},
                           "pw2": {"shape": [1, 256, 16, 16]},
                           "scale": {"shape": [1, 256, 16, 16]},
                           "add": {"shape": [1, 256, 16, 16], "dtype": "signed INT16 NCHW"}},
        "calibration": {"method": "symmetric maxabs / 32767 over exactly image-00..02 per boundary",
                        "inter_block": "each Add output scale and codes pass unchanged as next input",
                        "zero_point": 0, "rounding": "ties-to-even", "activation_clip": [-32767, 32767],
                        "weight": "per-output-channel symmetric INT8 maxabs / 127, clip [-127,127]"},
        "quant_contract": {"raw_accumulation": "signed INT64 independently accumulated; per-stage raw outputs emitted",
                           "bias": "INT32 independently round-even quantized, checked with raw sum against INT32",
                           "requantization": "signed per-channel Q31, nearest ties-even, right shift",
                           "gelu": "65536-entry LUT from exact erf GELU, round-even, saturate [-32767,32767]",
                           "scale_add": "Q31 each branch, retain signed INT64 through branch sum, saturate once to INT16"},
        "calibration_scales_by_block": [{k: float(v) for k, v in scales.items()}
                                        for scales in scales_by_block],
        "blocks": block_records,
        "results": results,
        "files": files,
        "checks": {"all_20_blocks_present": len(block_records) == BLOCK_COUNT,
                   "three_fixed_samples": len(results) == 3,
                   "all_raw_accumulators_serialized": True,
                   "integer_oracle_is_cpu_only": True,
                   "board_ps_calibration": board_ps},
    }
    manifest = out / "manifest.json"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out.resolve()), "status": report["status"],
                      "manifest_sha256": sha256(manifest), "block_count": len(block_records),
                      "result_count": len(results), "output_file_count": len(files)}, indent=2))


if __name__ == "__main__":
    main()
