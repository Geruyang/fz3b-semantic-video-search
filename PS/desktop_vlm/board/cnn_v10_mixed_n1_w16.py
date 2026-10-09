"""Native-contract W8/W16 N1 mixed-precision oracle and parameter manifest.

Only the seven already identified PW1 output channels use W16 weights. Their
input is still the exact native A16 tensor; all other N1 work remains W8/A16.
The W16 dot products use signed32 two-term partials accumulated in signed64.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from cnn_v10_mixed_int import (INT32_MAX, A16_MAX, W8_MAX, _gelu_fp32,
                               _run_conv, accumulator_bound, error_metrics,
                               load_n1_contract, quantize_a16,
                               quantize_w8_per_output, run_n1_w8a16,
                               sha256_file)


FROZEN_PW_W16_CHANNELS = [101, 125, 122, 81, 40, 78, 124]
INT64_MAX = (1 << 63) - 1


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def quantize_w16_per_output(weight: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows = weight.reshape(weight.shape[0], -1).astype(np.float64)
    scales = np.max(np.abs(rows), axis=1) / A16_MAX
    scales[scales == 0] = 1.0
    q = np.clip(np.rint(rows / scales[:, None]), -A16_MAX, A16_MAX).astype(np.int16)
    return q.reshape(weight.shape), scales.astype(np.float32)


def w16_accumulator_contract(reduction_terms: int, *, chunk_terms: int = 2) -> dict:
    if reduction_terms <= 0 or chunk_terms <= 0:
        raise ValueError("reduction_terms and chunk_terms must be positive")
    # Native A16 may carry -32768; symmetric W16 quantization emits [-32767,32767].
    partial_abs = chunk_terms * (1 << 15) * A16_MAX
    full_abs = reduction_terms * (1 << 15) * A16_MAX
    return {"reduction_terms": reduction_terms, "chunk_terms": chunk_terms,
            "activation_domain": "full signed A16 [-32768,32767]",
            "quantized_weight_domain": "symmetric W16 [-32767,32767]",
            "partial_abs_bound": partial_abs, "signed32_max": INT32_MAX,
            "partial_fits_signed32": partial_abs <= INT32_MAX,
            "full_abs_bound": full_abs, "signed64_max": INT64_MAX,
            "full_fits_signed64": full_abs <= INT64_MAX,
            "accumulation": "signed32 partial sum per consecutive K chunk, signed64 sum of partials"}


def _w16_pw_output(q_a16: np.ndarray, activation_scale: float, conv,
                   selected_channels: list[int]) -> tuple[np.ndarray, dict]:
    if q_a16.dtype != np.int16 or q_a16.shape != (1, 128, 32, 32):
        raise ValueError("PW W16 oracle expects native A16 [1,128,32,32]")
    q_weights, scales = quantize_w16_per_output(conv.weight)
    n, cin, height, width = q_a16.shape
    if conv.weight.shape != (128, 128, 1, 1) or conv.group != 1:
        raise ValueError("N1 PW W16 oracle only supports frozen 128x128 pointwise Conv")
    output = np.zeros((n, 128, height, width), dtype=np.float32)
    extrema = {}
    for channel in selected_channels:
        w = q_weights[channel, :, 0, 0].astype(np.int64)
        total = np.zeros((n, height, width), dtype=np.int64)
        actual_partial_min, actual_partial_max = 0, 0
        for begin in range(0, cin, 2):
            end = min(begin + 2, cin)
            # einsum performs exact integer products and sums into int64; each
            # chunk is checked before being committed to the int64 accumulator.
            partial = np.einsum("c,ncyx->nyx", w[begin:end],
                                q_a16[:, begin:end].astype(np.int64), dtype=np.int64,
                                optimize=True)
            pmin, pmax = int(partial.min()), int(partial.max())
            if pmin < -(1 << 31) or pmax > INT32_MAX:
                raise OverflowError(f"W16 Acc32 partial overflow at channel {channel}: [{pmin},{pmax}]")
            actual_partial_min = min(actual_partial_min, pmin)
            actual_partial_max = max(actual_partial_max, pmax)
            total += partial
        tmin, tmax = int(total.min()), int(total.max())
        if tmin < -(1 << 63) or tmax > INT64_MAX:
            raise OverflowError(f"W16 Acc64 full accumulator overflow at channel {channel}")
        value = total.astype(np.float32) * (np.float32(activation_scale) * scales[channel])
        value += np.float32(conv.bias[channel])
        output[:, channel] = value
        extrema[str(channel)] = {"partial_acc32_observed_min": actual_partial_min,
                                 "partial_acc32_observed_max": actual_partial_max,
                                 "full_acc64_observed_min": tmin,
                                 "full_acc64_observed_max": tmax}
    return output, {"channel_extrema": extrema, "weight_scale_min": float(scales[selected_channels].min()),
                    "weight_scale_max": float(scales[selected_channels].max())}


def run_n1_mixed_w8w16(convs, x: np.ndarray, scales: dict,
                       selected_channels: list[int] = FROZEN_PW_W16_CHANNELS):
    if sorted(selected_channels) != sorted(set(selected_channels)):
        raise ValueError("W16 output channel IDs must be unique")
    if any(c < 0 or c >= 128 for c in selected_channels):
        raise ValueError("W16 output channel ID outside 0..127")
    q0 = quantize_a16(x, float(scales["input_a16_scale"]))
    dw, dw_proof = _run_conv(q0, float(scales["input_a16_scale"]), convs[0])
    stage = _gelu_fp32(dw)
    q1 = quantize_a16(stage, float(scales["pw_input_a16_scale"]))
    # Generate the regular W8 pointwise result, then replace only the selected
    # output channels using the W16/A16 split-accumulator path.
    pw_w8, pw_proof = _run_conv(q1, float(scales["pw_input_a16_scale"]), convs[1])
    pw_w16, w16_details = _w16_pw_output(q1, float(scales["pw_input_a16_scale"]),
                                         convs[1], list(selected_channels))
    pw_w8[:, selected_channels] = pw_w16[:, selected_channels]
    return _gelu_fp32(pw_w8), {"dw": dw_proof, "pw_w8": pw_proof,
                              "pw_w16": w16_details}, {"dw_post_gelu": stage, "pw_input_a16": q1}


def read_f32(path: Path, shape: tuple[int, ...]) -> np.ndarray:
    expected_bytes = int(np.prod(shape)) * 4
    if path.stat().st_size != expected_bytes:
        raise ValueError(f"bad fixture byte count at {path}")
    data = np.fromfile(path, dtype="<f4").reshape(shape).astype(np.float32, copy=False)
    if not np.isfinite(data).all():
        raise ValueError(f"nonfinite fixture data at {path}")
    return data


def _parameter_summary(conv0, conv1, channels):
    dw8, dw_scale = quantize_w8_per_output(conv0.weight)
    pw8, pw8_scale = quantize_w8_per_output(conv1.weight)
    pw16, pw16_scale = quantize_w16_per_output(conv1.weight)
    packed = {"dw_w8": dw8.astype(np.int8), "dw_w8_scale": dw_scale,
              "pw_w8": pw8.astype(np.int8), "pw_w8_scale": pw8_scale,
              "pw_w16_channels": np.asarray(channels, dtype=np.int16),
              "pw_w16": pw16[np.asarray(channels)].astype(np.int16),
              "pw_w16_scale": pw16_scale[np.asarray(channels)]}
    parameters = {}
    for key, array in (("dw_weight", conv0.weight), ("dw_bias", conv0.bias),
                       ("pw_weight", conv1.weight), ("pw_bias", conv1.bias)):
        raw = np.asarray(array, dtype="<f4").tobytes(order="C")
        parameters[key] = {"shape": list(array.shape), "bytes": len(raw), "sha256": _hash_bytes(raw)}
    for key, value in packed.items():
        arr = np.ascontiguousarray(value)
        parameters["quantized_" + key] = {"shape": list(arr.shape), "dtype": str(arr.dtype),
                                           "bytes": arr.nbytes,
                                           "sha256": _hash_bytes(arr.tobytes(order="C"))}
    return packed, parameters


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--calibration-report", type=Path,
                        default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-fallback-002/n1-w8a16-oracle.json"))
    parser.add_argument("--fixture-root", type=Path,
                        default=Path("artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001"))
    parser.add_argument("--fallback-root", type=Path,
                        default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-fallback-002"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-cosine", type=float, default=0.999)
    parser.add_argument("--max-relative-l2", type=float, default=0.05)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output directory {args.output}")
    args.output.mkdir(parents=True)
    conv0, conv1, contract = load_n1_contract(args.model)
    calibration_report = json.loads(args.calibration_report.read_text(encoding="utf-8"))
    if calibration_report.get("mixed_execution_contract", {}).get("pw1", {}).get("fallback_channels") != FROZEN_PW_W16_CHANNELS:
        raise ValueError("W16 channel list differs from frozen native-A16 mixed fallback")
    scales = calibration_report["calibration"]
    if calibration_report["contract"]["model_sha256"] != contract["model_sha256"]:
        raise ValueError("calibration report is bound to another N1 ONNX model")
    golden_manifest_path = args.fixture_root / "manifest.json"
    golden_manifest = json.loads(golden_manifest_path.read_text(encoding="utf-8"))
    cases, outputs = [], []
    run_rows = []
    proofs = []
    for index in range(3):
        board = args.fixture_root / f"image-{index:02d}" / "board"
        x_path, expected_path = board / "network1-bridge-input.f32", board / "network1-bridge-output.f32"
        fallback_path = args.fallback_root / f"image-{index:02d}-mixed-fp32-fallback.f32"
        x = read_f32(x_path, (1, 64, 64, 64))
        expected = read_f32(expected_path, (1, 128, 32, 32))
        fallback = read_f32(fallback_path, (1, 128, 32, 32))
        start = time.perf_counter()
        actual, proof, _ = run_n1_mixed_w8w16((conv0, conv1), x, scales)
        elapsed_ms = (time.perf_counter() - start) * 1000
        candidate_path = args.output / f"image-{index:02d}-w8w16-output.f32"
        actual.astype("<f4").tofile(candidate_path)
        full_fp32_error = error_metrics(expected, actual)
        fallback_error = error_metrics(fallback, actual)
        row = {"case_id": f"image-{index:02d}",
               "input_sha256": sha256_file(x_path), "full_fp32_output_sha256": sha256_file(expected_path),
               "current_fp32_fallback_sha256": sha256_file(fallback_path),
               "w8w16_output_sha256": sha256_file(candidate_path), "w8w16_output_bytes": candidate_path.stat().st_size,
               "w8w16_vs_full_fp32": full_fp32_error,
               "w8w16_vs_current_fp32_fallback": fallback_error,
               "host_oracle_ms": elapsed_ms,
               "full_fp32_gate": {"min_cosine": args.min_cosine, "max_relative_l2": args.max_relative_l2,
                                  "pass": full_fp32_error["cosine"] >= args.min_cosine
                                  and full_fp32_error["relative_l2"] <= args.max_relative_l2},
               "fallback_equivalence_gate": {"max_abs_limit": 1e-3,
                                             "pass": fallback_error["max_abs"] <= 1e-3}}
        run_rows.append(row)
        outputs.append(actual)
        cases.append((x, expected, fallback))
        proofs.append(proof)

    packed, parameter_summary = _parameter_summary(conv0, conv1, FROZEN_PW_W16_CHANNELS)
    params_path = args.output / "n1-w8w16-params.npz"
    np.savez(params_path, **packed)
    dw_bound = accumulator_bound(49)
    pw_w8_bound = accumulator_bound(128)
    pw_w16_bound = w16_accumulator_contract(128, chunk_terms=2)
    gates = [r["full_fp32_gate"]["pass"] for r in run_rows]
    fallback_equiv = [r["fallback_equivalence_gate"]["pass"] for r in run_rows]
    manifest = {
        "schema_version": 1,
        "candidate_id": "n1-dw-w8a16-pw-w8a16-with-7-w16-output-channels",
        "status": "PASS" if all(gates) and all(fallback_equiv) else "FAIL",
        "source_model": {"path": str(args.model), "sha256": contract["model_sha256"],
                         "input_shape": contract["input_shape"], "output_shape": contract["output_shape"]},
        "frozen_three_image_fixture_manifest": {"path": str(golden_manifest_path),
                                                  "sha256": sha256_file(golden_manifest_path),
                                                  "same_board_capture": golden_manifest.get("execution", {}).get("board_capture"),
                                                  "pl_execution": golden_manifest.get("execution", {}).get("pl_execution")},
        "reference_mixed_fallback_report": {"path": str(args.calibration_report),
                                             "sha256": sha256_file(args.calibration_report)},
        "calibration_scales": scales,
        "arithmetic": {
            "dw7": "all output channels W8/A16/Acc32; float32 GELU",
            "pw1_default": "121 output channels use symmetric per-output-channel W8, signed A16 activation and signed32 accumulation",
            "pw1_sensitive": {"output_channels": FROZEN_PW_W16_CHANNELS,
                               "count": len(FROZEN_PW_W16_CHANNELS), "fraction": len(FROZEN_PW_W16_CHANNELS) / 128,
                               "weight": "symmetric per-output-channel W16 in [-32767,32767]",
                               "input": "native signed A16 tensor; same calibrated scale as W8 PW channels",
                               "accumulator": "Acc32 partial sums over consecutive 2-term chunks, then Acc64 sum of partials",
                               "proof": pw_w16_bound},
            "activation_rounding": "ties-to-even; calibrated symmetric A16",
            "post_pw": "float32 GELU; output float32",
            "overflow_proofs": {"dw_w8": dw_bound, "pw_w8": pw_w8_bound},
        },
        "parameter_file": {"path": params_path.name, "bytes": params_path.stat().st_size,
                            "sha256": sha256_file(params_path),
                            "format": "NumPy NPZ; arrays contain W8 weights/scales, selected channel IDs, W16 weights/scales"},
        "parameters": parameter_summary,
        "hardware_cost": {
            "w16_channels": len(FROZEN_PW_W16_CHANNELS),
            "accumulator_width": 64,
            "partial_chunk_terms": 2,
            "extra_full_acc64_values_per_image": len(FROZEN_PW_W16_CHANNELS) * 32 * 32,
            "extra_full_acc64_bytes_per_image": len(FROZEN_PW_W16_CHANNELS) * 32 * 32 * 8,
            "tradeoff": "seven PW1 output lanes require W16 coefficient storage and signed64 accumulation across 64 partial chunks; the remaining 121 lanes retain the W8/Acc32 path. This is an arithmetic/parameter contract, not an RTL or target accelerator implementation.",
        },
        "gate": {"min_cosine": args.min_cosine, "max_relative_l2": args.max_relative_l2,
                 "three_engineering_images_pass": all(gates),
                 "fallback_equivalence_abs_limit": 1e-3,
                 "fp32_fallback_equivalence_pass": all(fallback_equiv)},
        "cases": run_rows,
        "measured_environment": {"kind": "local host oracle", "threads": args.threads,
                                 "timing_claim": "host Python/NumPy wall time only; not target or PL acceleration"},
    }
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    receipt_files = {p.name: {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
                     for p in sorted(args.output.iterdir()) if p.is_file()}
    receipt = {"schema_version": 1, "status": manifest["status"], "files": receipt_files,
               "source_model_sha256": contract["model_sha256"], "board_execution": False}
    receipt_path = args.output / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    result = {"status": manifest["status"], "manifest": str(manifest_path),
              "min_cosine": min(r["w8w16_vs_full_fp32"]["cosine"] for r in run_rows),
              "max_relative_l2": max(r["w8w16_vs_full_fp32"]["relative_l2"] for r in run_rows),
              "max_fallback_abs": max(r["w8w16_vs_current_fp32_fallback"]["max_abs"] for r in run_rows),
              "w16_fraction": len(FROZEN_PW_W16_CHANNELS) / 128,
              "w16_acc32_partial_bound": pw_w16_bound["partial_abs_bound"],
              "w16_acc64_full_bound": pw_w16_bound["full_abs_bound"]}
    print(json.dumps(result, indent=2))
    if manifest["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
