"""Host-only N1 W8/W16 integer oracle for the frozen signed-80 PL contract.

This is an executable arithmetic/packing candidate, not a target kernel. It
uses symmetric A16 tensors, W8 except for seven PW output lanes stored W16,
per-channel Q31 requantization, and explicit 65536-entry GELU tables.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from cnn_v10_mixed_int import (A16_MAX, INT32_MAX, W8_MAX, _conv_accumulate,
                               _gelu_fp32, error_metrics, load_n1_contract,
                               quantize_a16, quantize_w8_per_output,
                               sha256_file)
from cnn_v10_mixed_n1_w16 import (FROZEN_PW_W16_CHANNELS,
                                  quantize_w16_per_output)

SIN = 8.370727368858105e-05
SMID = 0.0005223256885074079
SOUT = 9.687628574169352e-05
Q31_SCALE = 1 << 31
S48_MIN, S48_MAX = -(1 << 47), (1 << 47) - 1
S80_MIN, S80_MAX = -(1 << 79), (1 << 79) - 1
S16_MIN, S16_MAX = -32768, 32767


def _round_even_ratio(numerator: int, denominator: int) -> int:
    """Integer nearest-even division, including signed numerators."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    q, r = divmod(abs(int(numerator)), int(denominator))
    twice = 2 * r
    if twice > denominator or (twice == denominator and (q & 1)):
        q += 1
    return sign * q


def _q31_params(real_ratio: float) -> tuple[int, int]:
    if not np.isfinite(real_ratio) or real_ratio <= 0:
        raise ValueError("requantization ratio must be finite and positive")
    shift = 31
    multiplier = int(np.rint(real_ratio * (1 << shift)))
    while multiplier > INT32_MAX and shift > 0:
        shift -= 1
        multiplier = int(np.rint(real_ratio * (1 << shift)))
    if multiplier <= 0 or multiplier > INT32_MAX or not 0 <= shift <= 62:
        raise OverflowError("ratio cannot be represented by signed Q31 contract")
    return multiplier, shift


def _gelu_lut(input_scale: float, output_scale: float) -> np.ndarray:
    codes = np.arange(S16_MIN, S16_MAX + 1, dtype=np.int16)
    real = codes.astype(np.float64) * float(input_scale)
    erf = np.frompyfunc(__import__("math").erf, 1, 1)(real / np.sqrt(2.0)).astype(np.float64)
    gelu = 0.5 * real * (1.0 + erf)
    return np.clip(np.rint(gelu / output_scale), S16_MIN, A16_MAX).astype("<i2")


def _qparams(conv, input_scale: float, output_scale: float, w_q: np.ndarray,
             weight_scales: np.ndarray) -> dict:
    bias_q = np.asarray([int(np.rint(float(b) / (input_scale * float(ws))))
                         for b, ws in zip(conv.bias, weight_scales)], dtype=object)
    if any(int(v) < S48_MIN or int(v) > S48_MAX for v in bias_q):
        raise OverflowError("quantized bias does not fit signed48")
    multipliers, shifts = zip(*[_q31_params(input_scale * float(ws) / output_scale)
                                for ws in weight_scales])
    return {"bias_q": np.asarray(bias_q, dtype=np.int64),
            "multipliers": np.asarray(multipliers, dtype=np.int64),
            "shifts": np.asarray(shifts, dtype=np.int64)}


def _requant_lut(accum: np.ndarray, params: dict, lut: np.ndarray):
    if accum.dtype != np.int64:
        accum = accum.astype(np.int64)
    out = np.empty(accum.shape, dtype=np.int16)
    observed = {"acc_min": int(accum.min()), "acc_max": int(accum.max()),
                "biased_acc_min": S48_MAX, "biased_acc_max": S48_MIN,
                "product_abs_max": 0}
    for c in range(accum.shape[1]):
        biased = accum[:, c].astype(object) + int(params["bias_q"][c])
        bmin, bmax = int(min(biased.flat)), int(max(biased.flat))
        observed["biased_acc_min"] = min(observed["biased_acc_min"], bmin)
        observed["biased_acc_max"] = max(observed["biased_acc_max"], bmax)
        if bmin < S48_MIN or bmax > S48_MAX:
            raise OverflowError(f"biased accumulator exceeds signed48 at output channel {c}")
        m, shift = int(params["multipliers"][c]), int(params["shifts"][c])
        for index in np.ndindex(biased.shape):
            product = int(biased[index]) * m
            observed["product_abs_max"] = max(observed["product_abs_max"], abs(product))
            if product < S80_MIN or product > S80_MAX:
                raise OverflowError(f"requant product exceeds signed80 at output channel {c}")
            rounded = _round_even_ratio(product, 1 << shift)
            clipped = min(A16_MAX, max(-A16_MAX, rounded))
            # Compact GELU lookup uses the signed16 code as a bias-32768 index.
            out[index[0], c, index[1], index[2]] = lut[clipped - S16_MIN]
    observed.update({"bias_signed48": True, "product_signed80": True,
                     "q31_shift_min": int(params["shifts"].min()),
                     "q31_shift_max": int(params["shifts"].max())})
    return out, observed


def _depthwise_acc(q_input, conv):
    w8, scales = quantize_w8_per_output(conv.weight)
    accum = _conv_accumulate(q_input, conv, w8.astype(np.int8))
    return accum, w8, scales


def run_integer_candidate(convs, x: np.ndarray):
    q0 = np.clip(np.rint(x.astype(np.float64) / SIN), -A16_MAX, A16_MAX).astype(np.int16)
    dw_acc, dw_w8, dw_ws = _depthwise_acc(q0, convs[0])
    dw_params = _qparams(convs[0], SIN, SMID, dw_w8, dw_ws)
    dw_lut = _gelu_lut(SMID, SMID)
    mid_q, dw_observed = _requant_lut(dw_acc, dw_params, dw_lut)

    pw_w8, pw_w8_scales = quantize_w8_per_output(convs[1].weight)
    pw_w16, pw_w16_scales = quantize_w16_per_output(convs[1].weight)
    merged_w = pw_w8.astype(np.int16)
    merged_scales = pw_w8_scales.copy()
    for channel in FROZEN_PW_W16_CHANNELS:
        merged_w[channel] = pw_w16[channel]
        merged_scales[channel] = pw_w16_scales[channel]
    # The generic Acc32 helper is not valid for W16. Compute all ordinary W8
    # channels with its normal proof, and selected W16 channels in 2-term
    # signed32 partials followed by signed64 accumulation.
    pw_acc = _conv_accumulate(mid_q, convs[1], pw_w8.astype(np.int8))
    selected_acc = np.zeros_like(pw_acc)
    pw_partial_observed = {}
    for c in FROZEN_PW_W16_CHANNELS:
        total = np.zeros((1, 32, 32), dtype=np.int64)
        chunks_min, chunks_max = 0, 0
        for k in range(0, 128, 2):
            part = np.einsum("c,ncyx->nyx", pw_w16[c, k:k + 2, 0, 0].astype(np.int64),
                             mid_q[:, k:k + 2].astype(np.int64), dtype=np.int64, optimize=True)
            chunks_min, chunks_max = min(chunks_min, int(part.min())), max(chunks_max, int(part.max()))
            if chunks_min < -(1 << 31) or chunks_max > INT32_MAX:
                raise OverflowError(f"PW W16 partial Acc32 overflow in channel {c}")
            total += part
        selected_acc[:, c] = total
        if int(total.min()) < S48_MIN or int(total.max()) > S48_MAX:
            raise OverflowError(f"PW W16 full accumulator exceeds signed48 in channel {c}")
        pw_partial_observed[str(c)] = {"partial_acc32_min": chunks_min, "partial_acc32_max": chunks_max,
                                      "full_acc48_min": int(total.min()), "full_acc48_max": int(total.max())}
    for c in FROZEN_PW_W16_CHANNELS:
        pw_acc[:, c] = selected_acc[:, c]
    # W8 accumulators are signed32 safe; W16 outputs are signed48 safe by
    # complete-domain proof and signed64 is used by this host oracle.
    pw_params = _qparams(convs[1], SMID, SOUT, merged_w, merged_scales)
    pw_lut = _gelu_lut(SOUT, SOUT)
    out_q, pw_observed = _requant_lut(pw_acc, pw_params, pw_lut)
    output = out_q.astype(np.float32) * np.float32(SOUT)
    proof = {"dw": dw_observed, "pw": pw_observed,
             "pw_w16_channels": pw_partial_observed,
             "dw_acc32_domain_abs_bound": 49 * 32768 * 127,
             "pw_w8_acc32_domain_abs_bound": 128 * 32768 * 127,
             "pw_w16_acc48_domain_abs_bound": 128 * 32768 * 32767,
             "pw_w16_two_term_acc32_partial_abs_bound": 2 * 32768 * 32767}
    packed = {"dw_w8": dw_w8.astype(np.int8), "dw_w8_scale": dw_ws,
              "pw_w8": pw_w8.astype(np.int8), "pw_w8_scale": pw_w8_scales,
              "pw_w16_channels": np.asarray(FROZEN_PW_W16_CHANNELS, dtype=np.int16),
              "pw_w16": pw_w16[FROZEN_PW_W16_CHANNELS].astype(np.int16),
              "pw_w16_scale": pw_w16_scales[FROZEN_PW_W16_CHANNELS],
              "dw_bias_q48": dw_params["bias_q"], "dw_q31_multiplier": dw_params["multipliers"],
              "dw_q31_shift": dw_params["shifts"], "pw_bias_q48": pw_params["bias_q"],
              "pw_q31_multiplier": pw_params["multipliers"], "pw_q31_shift": pw_params["shifts"],
              "dw_gelu_lut_i16": dw_lut, "pw_gelu_lut_i16": pw_lut}
    return output, out_q, proof, packed


def _read_f32(path: Path, shape):
    raw = path.read_bytes()
    if len(raw) != int(np.prod(shape)) * 4:
        raise ValueError(f"bad f32 fixture size: {path}")
    return np.frombuffer(raw, dtype="<f4").reshape(shape).copy()


def _weight_error(reference: np.ndarray, quantized: np.ndarray, scales: np.ndarray) -> dict:
    ref = np.asarray(reference, dtype=np.float64).reshape(np.asarray(reference).shape[0], -1)
    q = np.asarray(quantized, dtype=np.float64).reshape(ref.shape)
    sc = np.asarray(scales, dtype=np.float64).reshape(-1, 1)
    delta = q * sc - ref
    ref_norm = float(np.linalg.norm(ref))
    return {"max_abs": float(np.max(np.abs(delta))),
            "relative_l2": float(np.linalg.norm(delta) / max(ref_norm, np.finfo(np.float64).tiny)),
            "rmse": float(np.sqrt(np.mean(delta * delta))),
            "weight_elements": int(ref.size)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--fixture-root", type=Path, default=Path("artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001"))
    p.add_argument("--fallback-root", type=Path, default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-fallback-002"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    convs = load_n1_contract(args.model)[:2]
    rows = []
    all_outputs = []
    for i in range(3):
        board = args.fixture_root / f"image-{i:02d}" / "board"
        x_path, fp_path = board / "network1-bridge-input.f32", board / "network1-bridge-output.f32"
        fallback_path = args.fallback_root / f"image-{i:02d}-mixed-fp32-fallback.f32"
        x = _read_f32(x_path, (1, 64, 64, 64))
        expected = _read_f32(fp_path, (1, 128, 32, 32))
        fallback = _read_f32(fallback_path, (1, 128, 32, 32))
        t0 = time.perf_counter()
        out, out_q, proof, packed = run_integer_candidate(convs, x)
        elapsed = (time.perf_counter() - t0) * 1000
        out_path = args.output / f"image-{i:02d}-n1-w8w16-pl-oracle.f32"
        code_path = args.output / f"image-{i:02d}-n1-w8w16-pl-oracle.i16"
        out.astype("<f4").tofile(out_path)
        out_q.astype("<i2").tofile(code_path)
        row = {"case_id": f"image-{i:02d}", "input_sha256": sha256_file(x_path),
               "fp32_output_sha256": sha256_file(fp_path), "fallback_output_sha256": sha256_file(fallback_path),
               "integer_output_sha256": sha256_file(out_path), "integer_codes_sha256": sha256_file(code_path),
               "vs_full_fp32": error_metrics(expected, out), "vs_current_fp32_fallback": error_metrics(fallback, out),
               "oracle_ms": elapsed, "arithmetic_proof": proof}
        row["fp32_gate_pass"] = row["vs_full_fp32"]["cosine"] >= 0.999 and row["vs_full_fp32"]["relative_l2"] <= 0.05
        rows.append(row)
        all_outputs.append((out, out_q))
    _, _, _, packed = run_integer_candidate(convs, _read_f32(args.fixture_root / "image-00" / "board" / "network1-bridge-input.f32", (1, 64, 64, 64)))
    np.savez(args.output / "n1-w8w16-pl-integer-params.npz", **packed)
    param_file = args.output / "n1-w8w16-pl-integer-params.npz"
    manifest = {"schema_version": 1, "candidate": "n1-dw-w8-a16-pw-w8-a16-plus-seven-w16-pl-integer-oracle",
                "status": "PASS" if all(r["fp32_gate_pass"] for r in rows) else "FAIL",
                "execution": "host-only Python/NumPy integer arithmetic oracle; not ORT production model and no target timing claim",
                "source_model": {"path": str(args.model), "sha256": sha256_file(args.model)},
                "scales": {"Sin": SIN, "Smid": SMID, "Sout": SOUT},
                "channels": {"dw_w8": 128, "pw_w8": 121, "pw_w16": FROZEN_PW_W16_CHANNELS,
                             "pw_w16_fraction": len(FROZEN_PW_W16_CHANNELS) / 128},
                "weight_quantization_error": {
                    "dw_w8": _weight_error(convs[0].weight, packed["dw_w8"], packed["dw_w8_scale"]),
                    "pw_w8_all_channels": _weight_error(convs[1].weight, packed["pw_w8"], packed["pw_w8_scale"]),
                    "pw_w16_sensitive_channels": _weight_error(convs[1].weight[FROZEN_PW_W16_CHANNELS],
                        packed["pw_w16"], packed["pw_w16_scale"])},
                "arithmetic_contract": {"weight_rounding": "max(abs(weight))/127 or /32767; nearest ties-even; clamp [-127,127] or [-32767,32767]",
                    "bias": "ties-even(bias/(Sin*Sw)) per output; signed48 range check",
                    "requant": "signed Q31 multiplier and per-channel shift; ties-even integer right shift; signed16 symmetric clip",
                    "product": "signed80 range checked", "accumulator": "DW and ordinary PW W8 Acc32; PW W16 two-term Acc32 partials combined in signed48 (held in int64 by host oracle)",
                    "gelu": "explicit 65536-entry LUT from exact erf formula, quantized ties-even to stage scale; generated locally and must be byte-compared with target compact-GELU table before deployment",
                    "domain_bounds": {"dw_acc32_abs": 49 * 32768 * 127, "pw_w8_acc32_abs": 128 * 32768 * 127,
                        "pw_w16_acc48_full_abs": 128 * 32768 * 32767, "pw_w16_partial_abs": 2 * 32768 * 32767,
                        "pw_w16_full_fits_signed48": 128 * 32768 * 32767 < (1 << 47),
                        "pw_w16_partial_fits_signed32": 2 * 32768 * 32767 < INT32_MAX}},
                "parameter_file": {"path": param_file.name, "bytes": param_file.stat().st_size, "sha256": sha256_file(param_file)},
                "cases": rows, "gate": {"cosine_min": 0.999, "relative_l2_max": 0.05,
                    "three_engineering_images_pass": all(r["fp32_gate_pass"] for r in rows)},
                "hardware_cost": {"extra_w16_weight_bytes_vs_w8": 7 * 128, "w16_partial_chunks_per_output": 64,
                    "w16_acc48_output_values_per_image": 7 * 32 * 32,
                    "w16_acc48_full_channels": 7,
                    "integer_operation_count_is_not_a_timing_measurement": True}}
    mpath = args.output / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    receipt = {"status": manifest["status"], "manifest_sha256": sha256_file(mpath),
               "files": {f.name: {"bytes": f.stat().st_size, "sha256": sha256_file(f)}
                         for f in sorted(args.output.iterdir()) if f.is_file()}}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "manifest": str(mpath),
                      "min_cosine": min(r["vs_full_fp32"]["cosine"] for r in rows),
                      "max_relative_l2": max(r["vs_full_fp32"]["relative_l2"] for r in rows)}, indent=2))
    if manifest["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
