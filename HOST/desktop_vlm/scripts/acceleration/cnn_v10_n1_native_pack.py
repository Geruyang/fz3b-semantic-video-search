"""Pack the frozen N1 model for the optional AArch64 W8A16 bridge."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "desktop_vlm" / "board"
sys.path.insert(0, str(BOARD))
from cnn_v10_mixed_int import (INT32_MAX, load_n1_contract,
                               quantize_w8_per_output, accumulator_bound)

SCHEMA = "cnn-v10.1-n1-w8a16-native-v1"
MAGIC = b"N1W8A16\0"
HEADER = struct.Struct("<8sIIIIIfff")
PARAM_BYTES = (HEADER.size + 128 * 49 + 128 * 4 * 2 + 128 * 49 * 4 + 128
               + 128 * 128 + 128 * 4 * 2 + 128 * 128 * 4 + 128)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _f32_bytes(values):
    return np.asarray(values, dtype="<f4").tobytes(order="C")


def _read_native_oracle(path: Path, source_sha: str):
    report = json.loads(path.read_text(encoding="utf-8"))
    if (report.get("schema_version") != 2 or
            report.get("contract", {}).get("model_sha256") != source_sha):
        raise ValueError("oracle source_model_sha256 does not match frozen model")
    selection = report.get("layer_error_attribution", {}).get("mixed_candidate_search")
    execution = report.get("mixed_execution_contract")
    expected_semantics = "native_a16_dequant_input_fp32_weights_accum"
    if (not isinstance(selection, dict) or not isinstance(execution, dict) or
            execution.get("fallback_semantics", "").split(";")[0] != expected_semantics):
        raise ValueError("oracle lacks the native A16-dequantized sensitive-channel semantics")
    if execution.get("status") != "PASS" or selection.get("status") != "PASS":
        raise ValueError("native oracle must pass every engineering case")
    gates = selection.get("per_case_gate")
    if not isinstance(gates, list) or len(gates) != 3 or any(
            not isinstance(row, dict) or row.get("pass") is not True for row in gates):
        raise ValueError("native oracle must contain three passing per-case gates")
    for row in gates:
        case_metrics = row.get("metrics")
        if (not isinstance(case_metrics, dict) or float(case_metrics.get("cosine", 0.0)) < 0.999 or
                float(case_metrics.get("relative_l2", float("inf"))) > 0.05):
            raise ValueError("a native oracle case does not meet cosine/relative-L2 gates")
    metrics = selection.get("metrics")
    if (not isinstance(metrics, dict) or float(metrics.get("cosine", 0.0)) < 0.999 or
            float(metrics.get("relative_l2", float("inf"))) > 0.05):
        raise ValueError("native oracle aggregate metrics do not meet cosine/relative-L2 gates")
    dw_channels = selection.get("dw_fp32_channels")
    pw_channels = selection.get("pw_fp32_channels")
    for name, channels in (("dw_fp32_channels", dw_channels),
                           ("pw_fp32_channels", pw_channels)):
        if (not isinstance(channels, list) or
                any(type(c) is not int or c < 0 or c >= 128 for c in channels) or
                len(channels) != len(set(channels))):
            raise ValueError("%s must be an ordered unique list of channels in [0,127]" % name)
    proof_records = report.get("overflow_proofs")
    proof_by_terms = {}
    ranges = []
    if not isinstance(proof_records, list):
        raise ValueError("native oracle must provide overflow_proofs")
    for item in proof_records:
        bound = item.get("bound", {})
        terms = bound.get("reduction_terms")
        proof_by_terms[terms] = bound
        ranges.append({"min": item.get("observed_accumulator_min"),
                       "max": item.get("observed_accumulator_max")})
    proofs = [proof_by_terms.get(49), proof_by_terms.get(128)]
    expected_terms = (49, 128)
    if not isinstance(proofs, list) or len(proofs) != 2:
        raise ValueError("native oracle must provide both full-domain Acc32 proofs")
    for terms, row in zip(expected_terms, proofs):
        expected_bound = terms * 32768 * 128
        if (row.get("reduction_terms") != terms or row.get("activation_abs_max") != 32768 or
                row.get("weight_abs_max") != 128 or row.get("worst_case_abs") != expected_bound or
                row.get("signed32_max") != INT32_MAX or row.get("fits_signed32") is not True):
            raise ValueError("native oracle Acc32 proof does not cover complete INT16/INT8 storage domains")
    if not isinstance(ranges, list) or len(ranges) != 2 or any(
            type(row.get("min")) is not int or type(row.get("max")) is not int or
            row["min"] < -(1 << 31) or row["max"] > INT32_MAX for row in ranges):
        raise ValueError("native oracle must provide observed Acc32 min/max ranges for both layers")
    native = {"metrics": metrics, "per_case_gate": gates,
              "fallback_semantics": expected_semantics,
              "observed_accumulator_ranges": ranges}
    return report, native, dw_channels, pw_channels, proofs


def pack(model_path: Path, oracle_path: Path, output_dir: Path,
         output_scale: float) -> dict:
    if output_dir.exists():
        raise FileExistsError("refusing to overwrite output directory: %s" % output_dir)
    if not np.isfinite(output_scale) or output_scale <= 0:
        raise ValueError("profile0 input output_scale must be finite and positive")
    dw, pw, contract = load_n1_contract(model_path)
    report, native, dw_fp32, pw_fp32, proofs = _read_native_oracle(
        oracle_path, contract["model_sha256"])
    calibration = report.get("calibration", {})
    input_logical_scale = float(calibration.get("input_a16_scale", 0.0))
    output_logical_scale = float(output_scale)
    input_scale = float(np.float32(input_logical_scale))
    pw_input_scale = float(np.float32(calibration.get("pw_input_a16_scale", 0.0)))
    output_scale = float(np.float32(output_logical_scale))
    if any(not np.isfinite(s) or s <= 0 for s in (input_scale, pw_input_scale)):
        raise ValueError("oracle calibration A16 scales are invalid")

    dw_q, dw_scales = quantize_w8_per_output(dw.weight)
    pw_q, pw_scales = quantize_w8_per_output(pw.weight)
    sections = {}
    payload = bytearray(HEADER.pack(MAGIC, 1, 128, 128, 128, 0,
                                    input_scale, pw_input_scale, output_scale))

    def append(name, data):
        start = len(payload)
        payload.extend(data)
        sections[name] = {"offset": start, "bytes": len(data),
                          "sha256": sha256_bytes(data)}

    append("dw7_w8", dw_q.astype("i1", copy=False).tobytes())
    append("dw7_weight_scale_f32", _f32_bytes(dw_scales))
    append("dw7_bias_f32", _f32_bytes(dw.bias))
    append("dw7_fp32_weights", _f32_bytes(dw.weight))
    append("dw7_fp32_channel_mask", bytes(1 if i in dw_fp32 else 0 for i in range(128)))
    append("pw1_w8", pw_q.astype("i1", copy=False).tobytes())
    append("pw1_weight_scale_f32", _f32_bytes(pw_scales))
    append("pw1_bias_f32", _f32_bytes(pw.bias))
    append("pw1_fp32_weights", _f32_bytes(pw.weight))
    append("pw1_fp32_channel_mask", bytes(1 if i in pw_fp32 else 0 for i in range(128)))
    if len(payload) != PARAM_BYTES:
        raise AssertionError("native parameter ABI length mismatch")

    output_dir.mkdir(parents=True)
    params_path = output_dir / "n1-params.bin"
    params_path.write_bytes(payload)
    manifest = {
        "schema": SCHEMA, "status": "PASS",
        "source_model": {"sha256": contract["model_sha256"]},
        "input": {"profile": 2, "shape": [1, 64, 64, 64], "layout": "HCW",
                  "dtype": "<i2", "scale": "profile2_output",
                  "arithmetic_scale_value_f32": input_scale,
                  "logical_pl_scale_value_f64": input_logical_scale,
                  "packed_scale_f32_hex": struct.pack("<f", input_scale).hex()},
        "output": {"profile": 0, "shape": [1, 128, 32, 32], "layout": "HCW",
                   "dtype": "<i2", "scale": "profile0_input",
                   "arithmetic_scale_value_f32": output_scale,
                   "logical_pl_scale_value_f64": output_logical_scale,
                   "packed_scale_f32_hex": struct.pack("<f", output_scale).hex()},
        "pw_input_a16_scale": pw_input_scale,
        "native_threads": 3,
        "stage_profile_scope": {"dw_ms": "AArch64 HCW-to-padded-channel-major reorder plus DW7/GELU and three worker joins",
                                "pw_ms": "PW1/GELU and three worker joins"},
        "packed_parameters": {"path": params_path.name, "bytes": len(payload),
                              "sha256": sha256_bytes(payload), "sections": sections},
        "dw_fp32_channels": dw_fp32, "pw_fp32_channels": pw_fp32,
        "arithmetic": {
            "integer_path": "signed W8[-127,127] x symmetric A16[-32767,32767], signed Acc32; host proof and runtime Acc32 range check",
            "sensitive_path": "FP32 weights x A16 dequantized input with ordered FP32 accumulation; bypasses W8/Acc32",
            "weight_quantization": "per-output-channel max(abs(weight))/127 scale; binary64 divide and nearest ties-to-even; clamp W8 to [-127,127]",
            "activation_requantization": "binary64 divide followed by nearest ties-to-even; symmetric A16 clamp [-32767,32767]",
            "gelu": "FP32 exact erf GELU: float32(0.5*x) * float32(1 + float32(erf(float64(x)/sqrt(2)))); compile without fast-math",
            "accumulator_proofs": proofs,
            "observed_accumulator_ranges": native.get("observed_accumulator_ranges"),
        },
        "engineering_gate": {"cosine_min": 0.999, "relative_l2_max": 0.05,
                              "metrics": native["metrics"],
                              "per_case_gate": native["per_case_gate"],
                              "fallback_semantics": native["fallback_semantics"]},
        "native_abi": {"version": 1, "symbol": "cnn_v10_n1_infer_int16_hcw",
                       "scalar_symbol": "cnn_v10_n1_infer_int16_hcw_scalar",
                       "profile_symbol": "cnn_v10_n1_infer_int16_hcw_profile",
                       "threads": 3, "link_flags": ["-pthread"],
                       "library_sha256": None, "library_path": None},
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-scale", type=float, required=True,
                        help="profile 0 input A16 scale, captured from its frozen calibration")
    args = parser.parse_args()
    print(json.dumps(pack(args.model, args.oracle, args.output, args.output_scale), indent=2))


if __name__ == "__main__":
    main()
