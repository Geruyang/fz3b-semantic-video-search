"""Host-only N1 PW W16 mask sweep against DW8/full-PW-FP32 error floor."""
from __future__ import annotations

import json
from pathlib import Path
import time

import numpy as np

import cnn_v10_mixed_n1_w16_pl_integer as integer_oracle
from cnn_v10_mixed_n1_w16_pl_integer import (FROZEN_PW_W16_CHANNELS,
    A16_MAX, INT32_MAX, SIN, SMID, SOUT, _gelu_lut,
    error_metrics, load_n1_contract, quantize_a16, sha256_file)
from cnn_v10_mixed_int import run_n1_w8a16
from cnn_v10_mixed_n1_w16_pl_integer_004 import (_normalized_params, _requant_lut_frozen,
    _tables, canonical_q31_from_fixed31)
from cnn_v10_mixed_n1_w16 import quantize_w16_per_output


def _dw_w16_accumulate(q_input: np.ndarray, conv):
    w16, scales = quantize_w16_per_output(conv.weight)
    n, cin, height, width = q_input.shape
    sh, sw = conv.stride
    pt, pl, pb, pr = conv.pads
    padded = np.pad(q_input.astype(np.int64), ((0, 0), (0, 0), (pt, pb), (pl, pr)))
    oh = (padded.shape[2] - 7) // sh + 1
    ow = (padded.shape[3] - 7) // sw + 1
    accum = np.zeros((n, 128, oh, ow), dtype=np.int64)
    observed_partial = 0
    for oc in range(128):
        group = oc // (128 // conv.group)
        ic = group * (cin // conv.group)
        terms = []
        for ky in range(7):
            ys = slice(ky, ky + oh * sh, sh)
            for kx in range(7):
                xs = slice(kx, kx + ow * sw, sw)
                terms.append((padded[:, ic, ys, xs], int(w16[oc, 0, ky, kx])))
        for begin in range(0, len(terms), 2):
            part = np.zeros((n, oh, ow), dtype=np.int64)
            for x_view, w in terms[begin:begin + 2]:
                part += x_view * w
            pmin, pmax = int(part.min()), int(part.max())
            observed_partial = max(observed_partial, abs(pmin), abs(pmax))
            if pmin < -(1 << 31) or pmax > INT32_MAX:
                raise OverflowError("full-W16 DW Acc32 partial overflow")
            accum[:, oc] += part
    if int(accum.min()) < -(1 << 47) or int(accum.max()) >= (1 << 47):
        raise OverflowError("full-W16 DW accumulator exceeds signed48")
    return accum, w16, scales, observed_partial


def run_full_w16a16(convs, x):
    q0 = np.clip(np.rint(x.astype(np.float64) / SIN), -A16_MAX, A16_MAX).astype(np.int16)
    dw_acc, dw_w16, dw_ws, dw_partial = _dw_w16_accumulate(q0, convs[0])
    dw_params = _normalized_params(convs[0], SIN, SMID, dw_ws, (0, 62))
    dw_lut = _tables(SMID, SMID)[0]
    mid, dw_proof = _requant_lut_frozen(dw_acc, dw_params, dw_lut)
    pw_w16, pw_ws = quantize_w16_per_output(convs[1].weight)
    pw_acc = np.zeros((1, 128, 32, 32), dtype=np.int64)
    pw_partial = 0
    for c in range(128):
        for k in range(0, 128, 2):
            part = np.einsum("c,ncyx->nyx", pw_w16[c, k:k + 2, 0, 0].astype(np.int64),
                mid[:, k:k + 2].astype(np.int64), dtype=np.int64, optimize=True)
            pmin, pmax = int(part.min()), int(part.max())
            pw_partial = max(pw_partial, abs(pmin), abs(pmax))
            if pmin < -(1 << 31) or pmax > INT32_MAX:
                raise OverflowError("full-W16 PW Acc32 partial overflow")
            pw_acc[:, c] += part
    if int(pw_acc.min()) < -(1 << 47) or int(pw_acc.max()) >= (1 << 47):
        raise OverflowError("full-W16 PW accumulator exceeds signed48")
    pw_params = _normalized_params(convs[1], SMID, SOUT, pw_ws, (0, 62))
    out_codes, pw_proof = _requant_lut_frozen(pw_acc, pw_params, _tables(SOUT, SOUT)[0])
    return out_codes.astype(np.float32) * np.float32(SOUT), out_codes, {
        "dw_acc48_bound": 49 * 32768 * 32767, "dw_partial_acc32_bound": 2 * 32768 * 32767,
        "pw_acc48_bound": 128 * 32768 * 32767, "pw_partial_acc32_bound": 2 * 32768 * 32767,
        "dw_observed_partial_abs": dw_partial, "pw_observed_partial_abs": pw_partial,
        "dw_observed_acc48_min": int(dw_acc.min()), "dw_observed_acc48_max": int(dw_acc.max()),
        "pw_observed_acc48_min": int(pw_acc.min()), "pw_observed_acc48_max": int(pw_acc.max()),
        "dw_requant": dw_proof, "pw_requant": pw_proof}


def expanded_masks(scores: np.ndarray, frozen: list[int], sizes=(16, 32, 64)) -> dict:
    if scores.shape != (128,) or len(set(frozen)) != len(frozen):
        raise ValueError("expected 128 output scores and unique frozen channels")
    ranked = sorted((c for c in range(128) if c not in frozen), key=lambda c: (-float(scores[c]), c))
    return {int(size): sorted(frozen + ranked[:size - len(frozen)]) for size in sizes}


def _read_f32(path: Path, shape):
    raw = path.read_bytes()
    if len(raw) != int(np.prod(shape)) * 4:
        raise ValueError(f"fixture length mismatch: {path}")
    return np.frombuffer(raw, dtype="<f4").reshape(shape).copy()


def _case_paths(fixture_root, fallback_root, idx):
    board = fixture_root / f"image-{idx:02d}" / "board"
    return (board / "network1-bridge-input.f32", board / "network1-bridge-output.f32",
        fallback_root / f"image-{idx:02d}-mixed-fp32-fallback.f32")


def _canonical_q31_callback(fixed31_fn):
    state = {"index": 0}
    def convert(ratio):
        stage = "dw" if state["index"] % 256 < 128 else "pw"
        state["index"] += 1
        limits = (35, 42) if stage == "dw" else (36, 44)
        m, shift = fixed31_fn(float(ratio))
        return canonical_q31_from_fixed31(m, shift, limits)
    return convert


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--calibration-report", type=Path, default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-fallback-002/n1-w8a16-oracle.json"))
    p.add_argument("--fixture-root", type=Path, default=Path("artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001"))
    p.add_argument("--fallback-root", type=Path, default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-fallback-002"))
    p.add_argument("--v003-root", type=Path, default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-w16-pl-integer-003"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--min-cosine", type=float, default=0.99975)
    p.add_argument("--max-relative-l2", type=float, default=0.022)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    convs = load_n1_contract(args.model)[:2]
    calibration = json.loads(args.calibration_report.read_text(encoding="utf-8"))
    scales = calibration["calibration"]
    with np.load(args.v003_root / "n1-w8w16-pl-integer-params.npz", allow_pickle=False) as npz:
        coeffs = {k: npz[k].copy() for k in ("dw_q31_multiplier", "dw_q31_shift", "pw_q31_multiplier", "pw_q31_shift")}
    original_mask = integer_oracle.FROZEN_PW_W16_CHANNELS
    original_q31, original_gelu = integer_oracle._q31_params, integer_oracle._gelu_lut
    inputs, expected, fallbacks, dw8_fullpw, full_w16_outputs = [], [], [], [], []
    try:
        for i in range(3):
            x_path, expected_path, fallback_path = _case_paths(args.fixture_root, args.fallback_root, i)
            x = _read_f32(x_path, (1, 64, 64, 64))
            ref = _read_f32(expected_path, (1, 128, 32, 32))
            fallback = _read_f32(fallback_path, (1, 128, 32, 32))
            # DW uses native A16->W8 Acc32; all PW output channels use the
            # same A16-dequantized input and FP32 weights for the error floor.
            floor, _, _ = run_n1_w8a16(convs, x, scales, pw_fp32_channels=list(range(128)))
            full_w16, full_w16_codes, full_w16_proof = run_full_w16a16(convs, x)
            full_w16_outputs.append((full_w16, full_w16_codes, full_w16_proof))
            inputs.append((x, x_path))
            expected.append((ref, expected_path))
            fallbacks.append((fallback, fallback_path))
            dw8_fullpw.append(floor)
        floor_metrics = [error_metrics(ref, floor) for (ref, _), floor in zip(expected, dw8_fullpw)]
        full_w16_rows = []
        for idx, ((ref, ref_path), (full_w16, full_codes, proof)) in enumerate(zip(expected, full_w16_outputs)):
            out_path = args.output / f"full-dw-pw-w16-image-{idx:02d}.f32"
            code_path = args.output / f"full-dw-pw-w16-image-{idx:02d}.i16"
            full_w16.astype("<f4").tofile(out_path)
            full_codes.astype("<i2").tofile(code_path)
            m = error_metrics(ref, full_w16)
            full_w16_rows.append({"case_id": f"image-{idx:02d}", "full_fp32_sha256": sha256_file(ref_path),
                "output_sha256": sha256_file(out_path), "codes_sha256": sha256_file(code_path),
                "vs_full_fp32": m, "fp32_gate_pass": m["cosine"] >= 0.999 and m["relative_l2"] <= 0.05,
                "arithmetic_proof": proof})

        # Rank output channels by measured three-image contribution of PW W8
        # quantization against the DW8/full-PW-FP32 floor.
        integer_oracle.FROZEN_PW_W16_CHANNELS = []
        integer_oracle._gelu_lut = original_gelu
        all_w8_outputs = []
        for x, _ in inputs:
            # Ranking baseline preserves the 003 fixed31 arithmetic; the
            # canonical 35..44 rescale is a gate for proposed mixed masks.
            integer_oracle._q31_params = original_q31
            out, _, _, _ = integer_oracle.run_integer_candidate(convs, x)
            all_w8_outputs.append(out)
        scores_sq = np.zeros(128, dtype=np.float64)
        for w8, floor in zip(all_w8_outputs, dw8_fullpw):
            delta = w8.astype(np.float64) - floor.astype(np.float64)
            scores_sq += np.sum(delta * delta, axis=(0, 2, 3))
        channel_scores = np.sqrt(scores_sq)
        masks = expanded_masks(channel_scores, FROZEN_PW_W16_CHANNELS)

        all_results = []
        for size, selected in masks.items():
            integer_oracle.FROZEN_PW_W16_CHANNELS = selected
            cases = []
            candidate_outputs = []
            for idx, ((x, x_path), (ref, ref_path), (fallback, fallback_path)) in enumerate(zip(inputs, expected, fallbacks)):
                integer_oracle._q31_params = _canonical_q31_callback(original_q31)
                t0 = time.perf_counter()
                output, codes, proof, packed = integer_oracle.run_integer_candidate(convs, x)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                output_path = args.output / f"mask{size:02d}-image-{idx:02d}.f32"
                code_path = args.output / f"mask{size:02d}-image-{idx:02d}.i16"
                output.astype("<f4").tofile(output_path)
                codes.astype("<i2").tofile(code_path)
                metrics = error_metrics(ref, output)
                full_w16_reference = full_w16_outputs[idx][0]
                cases.append({"case_id": f"image-{idx:02d}", "input_sha256": sha256_file(x_path),
                    "full_fp32_sha256": sha256_file(ref_path), "fallback_sha256": sha256_file(fallback_path),
                    "output_sha256": sha256_file(output_path), "codes_sha256": sha256_file(code_path),
                    "vs_full_fp32": metrics, "vs_current_fallback": error_metrics(fallback, output),
                    "vs_full_w16a16_oracle": error_metrics(full_w16_reference, output),
                    "local_gate_pass": metrics["cosine"] >= args.min_cosine and metrics["relative_l2"] <= args.max_relative_l2,
                    "oracle_ms": elapsed_ms, "proof": proof})
                candidate_outputs.append(output)
            aggregate = error_metrics(np.concatenate([r[0].ravel() for r in expected]),
                                      np.concatenate([o.ravel() for o in candidate_outputs]))
            all_results.append({"sensitive_count": size, "sensitive_channels": selected,
                "sensitive_fraction": size / 128, "weight_bytes_extra_vs_w8": size * 128,
                "cases": cases, "aggregate_vs_full_fp32": aggregate,
                "three_image_local_gate_pass": all(c["local_gate_pass"] for c in cases)})

        contribution = [{"channel": int(c), "l2_error_contribution": float(channel_scores[c]),
                         "relative_to_total": float(channel_scores[c] / max(np.linalg.norm(channel_scores), np.finfo(np.float64).tiny))}
                        for c in np.argsort(-channel_scores, kind="stable")]
        floor_rows = [{"case_id": f"image-{i:02d}", "input_sha256": sha256_file(inputs[i][1]),
            "full_fp32_sha256": sha256_file(expected[i][1]), "output_sha256": __import__("hashlib").sha256(dw8_fullpw[i].astype("<f4").tobytes()).hexdigest(),
            "metrics_vs_full_fp32": floor_metrics[i],
            "local_gate_pass": floor_metrics[i]["cosine"] >= args.min_cosine and floor_metrics[i]["relative_l2"] <= args.max_relative_l2}
            for i in range(3)]
        manifest = {"schema_version": 1, "candidate": "n1-pw-sensitive-mask-search-host-only",
            "status": "PASS" if any(r["three_image_local_gate_pass"] for r in all_results) else "NO_MASK_MET_TARGET_LOCAL_GATE",
            "execution": "host-only; no PL compilation, target timing, or runtime changes",
            "source_model": {"path": str(args.model), "sha256": sha256_file(args.model)},
            "baseline": {"meaning": "DW7 W8/A16/Acc32 + GELU/A16, then all 128 PW output channels native-A16-dequant-input FP32 weights/accumulation, final FP32 GELU",
                "purpose": "measured DW8 error floor before PW weight quantization",
                "cases": floor_rows, "three_image_local_gate_pass": all(r["local_gate_pass"] for r in floor_rows)},
            "full_w16a16_reference": {"meaning": "all DW and PW weights symmetric per-output W16; A16 activations; Acc32 two-term partials combined in signed48; exact integer Q31/GELU oracle",
                "backend": "PL-oriented full-W16 integer oracle; separate execution backend from PS W8/A16 plus sensitive FP32 fallback",
                "cases": full_w16_rows, "three_image_full_model_gate_pass": all(r["fp32_gate_pass"] for r in full_w16_rows)},
            "ranking": {"method": "per-output-channel L2 contribution across three engineering images: all-PW-W8 integer candidate minus DW8/full-PW-FP32 baseline output",
                "scores_descending": contribution},
            "q31": {"mixed_mask_candidates": "for each actual per-channel W8/W16 scale, run the existing fixed31 multiplier_shift quantizer, then exact power-of-two canonical rescale to DW shift35 and PW shift36; signed-i32 range checked",
                "full_w16_reference": "direct real-ratio normalized Q31 with permitted shift 0..62; this is a separate high-precision PL-oriented oracle, not the mixed-mask coefficient source"},
            "mask_search": all_results,
            "local_gate": {"min_cosine": args.min_cosine, "max_relative_l2": args.max_relative_l2,
                "full_model_gate_unchanged": {"cosine_min": 0.999, "relative_l2_max": 0.05}},
            "selected_candidate": next((r["sensitive_count"] for r in all_results if r["three_image_local_gate_pass"]), None),
            "runtime_contract": {"P3_blocks": 1, "slot_bytes": 32768, "input_bytes": 32768,
                "output_valid_bytes": 16384, "arena_bytes": 69632, "output_slot": 1},
            "pl_cost_comparison": {"physical_weight_storage": "uniform signed i16 per MAC lane for both mixed and all-W16 candidates",
                "dsp_and_mac_count": "same for mixed W8/W16 and full W16; W8 coefficients are sign-extended to i16",
                "full_w16_vs_mixed_cost_delta": "zero coefficient width/DSP/MAC savings; only arithmetic values/quality differ",
                "ps_fallback_backend": "W8/A16 PL path plus selected PW FP32 weights on PS is a separate backend, not the same PL implementation"}}
        mpath = args.output / "manifest.json"
        mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        receipt = {"status": manifest["status"], "manifest_sha256": sha256_file(mpath),
            "files": {f.name: {"bytes": f.stat().st_size, "sha256": sha256_file(f)}
                      for f in sorted(args.output.iterdir()) if f.is_file()}}
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps({"status": manifest["status"], "manifest": str(mpath),
            "dw8_fullpw_floor_cosines": [r["metrics_vs_full_fp32"]["cosine"] for r in floor_rows],
            "dw8_fullpw_floor_rel_l2": [r["metrics_vs_full_fp32"]["relative_l2"] for r in floor_rows],
            "mask_gates": {str(r["sensitive_count"]): r["three_image_local_gate_pass"] for r in all_results},
            "full_w16_gate": [r["fp32_gate_pass"] for r in full_w16_rows],
            "selected_candidate": manifest["selected_candidate"]}, indent=2))
    finally:
        integer_oracle.FROZEN_PW_W16_CHANNELS = original_mask
        integer_oracle._q31_params, integer_oracle._gelu_lut = original_q31, original_gelu
    if manifest["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
