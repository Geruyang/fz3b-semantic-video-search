"""004 normalized-Q31 and folded-GELU host oracle receipt for N1."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import numpy as np

import cnn_v10_mixed_n1_w16_pl_integer as oracle
from cnn_v10_mixed_n1_w16_pl_integer import (A16_MAX, FROZEN_PW_W16_CHANNELS,
    INT32_MAX, S16_MAX, S16_MIN, SIN, SMID, SOUT, _read_f32, error_metrics,
    load_n1_contract, sha256_file)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRODUCT_ACCEL = _REPO_ROOT / "desktop_vlm" / "scripts" / "acceleration"
import sys
sys.path.insert(0, str(_PRODUCT_ACCEL))
from integer_postops import multiplier_shift as _frozen_multiplier_shift
from cnn_w16_contract import q31_round_even_wide as _frozen_q31_round_even_wide
_ORIGINAL_GELU_LUT = oracle._gelu_lut


def normalized_q31(ratio: float, shift_range: tuple[int, int]) -> tuple[int, int]:
    """Frozen normalized Q31: signed multiplier from frexp, explicit shift."""
    if not np.isfinite(ratio) or ratio <= 0:
        raise ValueError("requant ratio must be finite and positive")
    multiplier, shift = _frozen_multiplier_shift(float(ratio))
    multiplier, shift = int(multiplier), int(shift)
    lo, hi = shift_range
    if not (0 < multiplier <= INT32_MAX and lo <= shift <= hi and 0 <= shift <= 62):
        raise OverflowError(f"normalized Q31 outside frozen range: multiplier={multiplier}, shift={shift}, allowed={shift_range}")
    return multiplier, shift


def canonical_q31_from_fixed31(multiplier0: int, shift0: int, shift_range: tuple[int, int]) -> tuple[int, int]:
    multiplier, shift = int(multiplier0), int(shift0)
    target_shift = shift_range[0]
    if target_shift < shift:
        raise OverflowError("canonical target shift cannot preserve fixed31 ratio by left scaling")
    multiplier <<= target_shift - shift
    if not 0 < multiplier <= INT32_MAX:
        raise OverflowError(f"canonical fixed31 rescale exceeds i32: {multiplier}")
    return multiplier, target_shift


def _stage_q31_callback(mode: str, fixed_coefficients):
    call = {"index": 0}
    def coefficient(ratio):
        lane = call["index"] % 128
        stage = "dw" if call["index"] % 256 < 128 else "pw"
        call["index"] += 1
        limits = (35, 42) if stage == "dw" else (36, 44)
        if mode == "direct_real_ratio":
            return normalized_q31(ratio, limits)
        if mode != "canonical_fixed31":
            raise ValueError(f"unknown Q31 mode {mode}")
        stem = "dw" if stage == "dw" else "pw"
        multiplier0 = fixed_coefficients[stem + "_q31_multiplier"][lane]
        shift0 = fixed_coefficients[stem + "_q31_shift"][lane]
        if int(shift0) != 31:
            raise ValueError("003 baseline coefficients are not fixed31")
        return canonical_q31_from_fixed31(multiplier0, shift0, limits)
    return coefficient


def _normalized_params(conv, input_scale, output_scale, w_scales, shift_range):
    bias = np.asarray([int(np.rint(float(b) / (input_scale * float(ws))))
                       for b, ws in zip(conv.bias, w_scales)], dtype=np.int64)
    if np.any(bias < -(1 << 47)) or np.any(bias >= (1 << 47)):
        raise OverflowError("bias exceeds signed48")
    pairs = [normalized_q31(input_scale * float(ws) / output_scale, shift_range)
             for ws in w_scales]
    mult = np.asarray([p[0] for p in pairs], dtype="<i4")
    shift = np.asarray([p[1] for p in pairs], dtype=np.uint8)
    return {"bias_q": bias, "multipliers": mult.astype(np.int64),
            "shifts": shift.astype(np.int64)}


def _requant_lut_frozen(accum, params, lut):
    """Requantize using the product source's q31_round_even_wide helper."""
    out = np.empty(accum.shape, dtype=np.int16)
    observed = {"acc_min": int(accum.min()), "acc_max": int(accum.max()),
        "biased_acc_min": (1 << 47) - 1, "biased_acc_max": -(1 << 47), "product_abs_max": 0}
    for c in range(accum.shape[1]):
        for index in np.ndindex(accum[:, c].shape):
            full_index = (index[0], c, index[1], index[2])
            value = int(accum[full_index]) + int(params["bias_q"][c])
            if not -(1 << 47) <= value < (1 << 47):
                raise OverflowError("biased accumulator exceeds signed48")
            m, shift = int(params["multipliers"][c]), int(params["shifts"][c])
            product = value * m
            observed["product_abs_max"] = max(observed["product_abs_max"], abs(product))
            if not -(1 << 79) <= product < (1 << 79):
                raise OverflowError("requant product exceeds signed80")
            rounded = _frozen_q31_round_even_wide(value, m, shift)
            clipped = min(A16_MAX, max(-A16_MAX, rounded))
            out[full_index] = lut[clipped - S16_MIN]
            observed["biased_acc_min"] = min(observed["biased_acc_min"], value)
            observed["biased_acc_max"] = max(observed["biased_acc_max"], value)
    observed.update({"bias_signed48": True, "product_signed80": True,
        "q31_shift_min": int(params["shifts"].min()), "q31_shift_max": int(params["shifts"].max())})
    return out, observed


def _tables(input_scale, output_scale):
    full = _ORIGINAL_GELU_LUT(input_scale, output_scale).astype("<i2", copy=True)
    negative = full[:32768].astype("<i2", copy=True)
    reconstructed = np.empty(65536, dtype="<i2")
    reconstructed[:32768] = negative
    reconstructed[32768] = 0
    for q in range(1, 32768):
        # Perform the specified signed 17-bit addition before int16 casting.
        acc17 = int(q) + int(negative[32768 - q])
        if not -(1 << 16) <= acc17 < (1 << 16):
            raise OverflowError("folded GELU reconstruction exceeds signed17")
        reconstructed[32768 + q] = np.asarray(acc17).astype(np.int16)
    if int(reconstructed[32768]) != 0:
        raise AssertionError("folded GELU zero code is not exactly zero")
    mismatches = np.flatnonzero(reconstructed != full)
    return full, negative, reconstructed, mismatches


def _sha(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _write(path: Path, arr: np.ndarray):
    np.ascontiguousarray(arr).tofile(path)
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def build_candidate_packed(packed: dict, dw_negative: np.ndarray,
                          pw_negative: np.ndarray) -> tuple[bytes, dict]:
    """Serialize the proposed, unbound candidate layout in 128-bit words."""
    dw_w = np.asarray(packed["dw_w8"], dtype=np.int8).reshape(128, 49).astype("<i2")
    pw_w = np.asarray(packed["pw_w8"], dtype=np.int8).reshape(128, 128).astype(np.int16)
    ch = np.asarray(packed["pw_w16_channels"], dtype=np.int64)
    pw_w16 = np.asarray(packed["pw_w16"], dtype=np.int16)
    pw_w[ch] = pw_w16.reshape(len(ch), 128)
    fields = [
        ("dw_weights_i16", 0, 784, dw_w.tobytes()),
        ("dw_bias_i48_container_i64", 784, 64, np.asarray(packed["dw_bias_q48"], dtype="<i8").tobytes()),
        ("dw_multiplier_i32", 848, 32, np.asarray(packed["dw_q31_multiplier"], dtype="<i4").tobytes()),
        ("dw_shift_i32", 880, 32, np.asarray(packed["dw_q31_shift"], dtype="<i4").tobytes()),
        ("dw_gelu_negative_half_i16", 912, 4096, np.asarray(dw_negative, dtype="<i2").tobytes()),
        ("pw_weights_i16", 5008, 2048, np.asarray(pw_w, dtype="<i2").tobytes()),
        ("pw_bias_i48_container_i64", 7056, 64, np.asarray(packed["pw_bias_q48"], dtype="<i8").tobytes()),
        ("pw_multiplier_i32", 7120, 32, np.asarray(packed["pw_q31_multiplier"], dtype="<i4").tobytes()),
        ("pw_shift_i32", 7152, 32, np.asarray(packed["pw_q31_shift"], dtype="<i4").tobytes()),
        ("pw_gelu_negative_half_i16", 7184, 4096, np.asarray(pw_negative, dtype="<i2").tobytes()),
    ]
    image = bytearray(11280 * 16)
    layout = {}
    for name, word_offset, word_length, payload in fields:
        begin = word_offset * 16
        expected = word_length * 16
        if len(payload) != expected:
            raise ValueError(f"{name} payload length {len(payload)} != {expected}")
        image[begin:begin + expected] = payload
        layout[name] = {"word_offset": word_offset, "word_length": word_length,
                        "byte_offset": begin, "byte_length": expected,
                        "sha256": hashlib.sha256(payload).hexdigest()}
    return bytes(image), layout


def verify_candidate_packed(image: bytes, layout: dict) -> dict:
    if len(image) != 180480:
        raise ValueError("candidate pack must be exactly 180480 bytes")
    checked = {}
    for name, field in layout.items():
        begin, length = field["byte_offset"], field["byte_length"]
        payload = image[begin:begin + length]
        digest = hashlib.sha256(payload).hexdigest()
        if digest != field["sha256"]:
            raise AssertionError(f"candidate pack field roundtrip mismatch: {name}")
        checked[name] = digest
    return {"pass": len(checked) == len(layout), "field_count": len(checked),
            "total_bytes": len(image), "sha256": hashlib.sha256(image).hexdigest(),
            "field_sha256": checked}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--fixture-root", type=Path, default=Path("artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001"))
    p.add_argument("--fallback-root", type=Path, default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-fallback-002"))
    p.add_argument("--v003-root", type=Path, default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-w16-pl-integer-003"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    convs = load_n1_contract(args.model)[:2]
    frozen_path = args.v003_root / "n1-w8w16-pl-integer-params.npz"
    with np.load(frozen_path, allow_pickle=False) as frozen_npz:
        frozen_coefficients = {key: frozen_npz[key].copy() for key in frozen_npz.files
            if key in ("dw_q31_multiplier", "dw_q31_shift", "pw_q31_multiplier", "pw_q31_shift")}
    if set(frozen_coefficients) != {"dw_q31_multiplier", "dw_q31_shift", "pw_q31_multiplier", "pw_q31_shift"}:
        raise ValueError("003 baseline is missing serialized Q31 arrays")
    old_params, old_lut, old_requant = oracle._q31_params, oracle._gelu_lut, oracle._requant_lut
    dw_full, dw_negative, dw_rebuilt, dw_bad = _tables(SMID, SMID)
    pw_full, pw_negative, pw_rebuilt, pw_bad = _tables(SOUT, SOUT)
    if len(dw_bad) or len(pw_bad):
        raise AssertionError("folded GELU is not byte-identical to full table")
    oracle._gelu_lut = lambda in_s, out_s: _tables(in_s, out_s)[2]
    oracle._requant_lut = _requant_lut_frozen
    # The base runner calls this function once for each Conv; select the
    # prescribed per-stage shift window using the exact frozen scale ratio.
    q31_callback = _stage_q31_callback("canonical_fixed31", frozen_coefficients)
    oracle._q31_params = q31_callback
    try:
        rows, direct_rows, all_packed = [], [], None
        for i in range(3):
            q31_callback = _stage_q31_callback("canonical_fixed31", frozen_coefficients)
            oracle._q31_params = q31_callback
            board = args.fixture_root / f"image-{i:02d}" / "board"
            x_path = board / "network1-bridge-input.f32"
            fp_path = board / "network1-bridge-output.f32"
            fallback_path = args.fallback_root / f"image-{i:02d}-mixed-fp32-fallback.f32"
            old_code_path = args.v003_root / f"image-{i:02d}-n1-w8w16-pl-oracle.i16"
            x = _read_f32(x_path, (1, 64, 64, 64))
            expected = _read_f32(fp_path, (1, 128, 32, 32))
            fallback = _read_f32(fallback_path, (1, 128, 32, 32))
            t0 = time.perf_counter()
            output, codes, proof, packed = oracle.run_integer_candidate(convs, x)
            elapsed = (time.perf_counter() - t0) * 1000
            all_packed = packed
            old_codes = np.fromfile(old_code_path, dtype="<i2").reshape(codes.shape)
            delta = codes.astype(np.int32) - old_codes.astype(np.int32)
            out_path = args.output / f"image-{i:02d}-n1-w8w16-pl-oracle.f32"
            code_path = args.output / f"image-{i:02d}-n1-w8w16-pl-oracle.i16"
            output.astype("<f4").tofile(out_path)
            codes.astype("<i2").tofile(code_path)
            oracle._q31_params = _stage_q31_callback("direct_real_ratio", frozen_coefficients)
            t1 = time.perf_counter()
            direct_output, direct_codes, direct_proof, direct_packed = oracle.run_integer_candidate(convs, x)
            direct_elapsed = (time.perf_counter() - t1) * 1000
            direct_out_path = args.output / f"image-{i:02d}-direct-ratio-output.f32"
            direct_code_path = args.output / f"image-{i:02d}-direct-ratio-output.i16"
            direct_output.astype("<f4").tofile(direct_out_path)
            direct_codes.astype("<i2").tofile(direct_code_path)
            direct_delta = direct_codes.astype(np.int32) - codes.astype(np.int32)
            direct_rows.append({"case_id": f"image-{i:02d}",
                "direct_ratio_output_sha256": sha256_file(direct_out_path),
                "direct_ratio_codes_sha256": sha256_file(direct_code_path),
                "vs_canonical_fixed31": {"mismatch_count": int(np.count_nonzero(direct_delta)),
                    "total_codes": int(direct_delta.size), "max_abs_code_delta": int(np.max(np.abs(direct_delta))),
                    "exact": bool(np.count_nonzero(direct_delta) == 0)},
                "vs_full_fp32": error_metrics(expected, direct_output),
                "vs_current_fp32_fallback": error_metrics(fallback, direct_output),
                "oracle_ms": direct_elapsed,
                "dw_shift_range": [int(direct_packed["dw_q31_shift"].min()), int(direct_packed["dw_q31_shift"].max())],
                "pw_shift_range": [int(direct_packed["pw_q31_shift"].min()), int(direct_packed["pw_q31_shift"].max())]})
            direct_rows[-1]["fp32_gate_pass"] = (direct_rows[-1]["vs_full_fp32"]["cosine"] >= 0.999 and
                direct_rows[-1]["vs_full_fp32"]["relative_l2"] <= 0.05)
            oracle._q31_params = _stage_q31_callback("canonical_fixed31", frozen_coefficients)
            rows.append({"case_id": f"image-{i:02d}", "input_sha256": sha256_file(x_path),
                "full_fp32_output_sha256": sha256_file(fp_path),
                "fallback_output_sha256": sha256_file(fallback_path),
                "v003_code_sha256": sha256_file(old_code_path),
                "integer_output_sha256": sha256_file(out_path),
                "integer_codes_sha256": sha256_file(code_path),
                "vs_full_fp32": error_metrics(expected, output),
                "vs_current_fp32_fallback": error_metrics(fallback, output),
                "vs_v003_codes": {"mismatch_count": int(np.count_nonzero(delta)),
                    "total_codes": int(delta.size), "max_abs_code_delta": int(np.max(np.abs(delta))),
                    "exact": bool(np.count_nonzero(delta) == 0)},
                "oracle_ms": elapsed, "arithmetic_proof": proof,
                "fp32_gate_pass": error_metrics(expected, output)["cosine"] >= 0.999 and error_metrics(expected, output)["relative_l2"] <= 0.05})
    finally:
        oracle._q31_params, oracle._gelu_lut, oracle._requant_lut = old_params, old_lut, old_requant

    # Produce explicit fixed-width serialized Q31 arrays and table artifacts.
    dw_mult = np.asarray(all_packed["dw_q31_multiplier"], dtype="<i4")
    dw_shift = np.asarray(all_packed["dw_q31_shift"], dtype="<i4")
    pw_mult = np.asarray(all_packed["pw_q31_multiplier"], dtype="<i4")
    pw_shift = np.asarray(all_packed["pw_q31_shift"], dtype="<i4")
    for name, values, lo, hi in (("dw", dw_shift, 35, 42), ("pw", pw_shift, 36, 44)):
        if int(values.min()) < lo or int(values.max()) > hi or int(values.max()) > 62:
            raise AssertionError(f"{name} shifts outside frozen contract")
    q31_files = {}
    for name, arr in (("dw-q31-multiplier.i32", dw_mult), ("dw-q31-shift.i32", dw_shift),
                      ("pw-q31-multiplier.i32", pw_mult), ("pw-q31-shift.i32", pw_shift)):
        q31_files[name] = _write(args.output / name, arr)
    table_files = {}
    reference_prefix = {"dw": {"full": "b027881b", "negative": "accbd595"},
                        "pw": {"full": "13a847f7", "negative": "5dfa7acc"}}
    for stage, full, negative, rebuilt in (("dw", dw_full, dw_negative, dw_rebuilt),
                                            ("pw", pw_full, pw_negative, pw_rebuilt)):
        table_files[stage] = {
            "full_i16le": _write(args.output / f"{stage}-gelu-full65536.i16", full),
            "negative_half_i16le": _write(args.output / f"{stage}-gelu-negative-half32768.i16", negative),
            "reconstructed_i16le": _write(args.output / f"{stage}-gelu-reconstructed65536.i16", rebuilt),
            "full_sha256": _sha(full), "negative_half_sha256": _sha(negative),
            "reconstructed_sha256": _sha(rebuilt), "byte_exact_full_vs_reconstructed": bool(np.array_equal(full, rebuilt)),
            "fold_identity_bad_count": int(np.count_nonzero(full != rebuilt)),
            "zero_code": int(rebuilt[32768]), "zero_code_is_zero": int(rebuilt[32768]) == 0,
            "jtag_reference_prefix": reference_prefix[stage],
            "jtag_prefix_match": _sha(full).startswith(reference_prefix[stage]["full"]) and
                                  _sha(negative).startswith(reference_prefix[stage]["negative"]),
            "length_entries": {"full": int(full.size), "negative_half": int(negative.size), "reconstructed": int(rebuilt.size)},
            "external_storage_bytes": int(negative.nbytes)}
    np.savez(args.output / "n1-w8w16-pl-integer-params.npz", **all_packed)
    param_path = args.output / "n1-w8w16-pl-integer-params.npz"
    candidate_pack, pack_layout = build_candidate_packed(all_packed, dw_negative, pw_negative)
    pack_path = args.output / "candidate-n1-w8w16-param-pack.bin"
    pack_path.write_bytes(candidate_pack)
    pack_roundtrip = verify_candidate_packed(candidate_pack, pack_layout)
    manifest = {"schema_version": 1, "candidate": "n1-w8w16-pl-integer-004-normalized-q31-folded-gelu",
        "status": "PASS" if all(r["fp32_gate_pass"] and r["vs_v003_codes"]["exact"] for r in rows)
            and all(r["fp32_gate_pass"] for r in direct_rows)
            and all(t["fold_identity_bad_count"] == 0 and t["zero_code_is_zero"] and t["jtag_prefix_match"] for t in table_files.values())
            and pack_roundtrip["pass"] else "FAIL",
        "execution": "host-only exact integer oracle; no target execution or timing claim",
        "source_model": {"path": str(args.model), "sha256": sha256_file(args.model)},
        "scales": {"Sin": SIN, "Smid": SMID, "Sout": SOUT},
        "q31_contract": {"canonical_candidate": "take 003 serialized fixed31 multiplier/2^31, then exact power-of-two rescale to DW shift 35 and PW shift 36; ratio remains exact, multiplier is signed i32",
            "direct_ratio_candidate": "separate comparison uses product-source integer_postops.multiplier_shift directly on original real ratio; may be more accurate and may differ in codes",
            "dw_shift_range": [35, 42], "pw_shift_range": [36, 44],
            "serialized_multiplier": "little-endian signed i32 per output channel",
            "serialized_shift": "little-endian signed i32 per output channel, constrained to 0..62 (u6 semantic field)",
            "canonical_source_npz": {"path": str(frozen_path), "sha256": sha256_file(frozen_path)},
            "rounding": "signed48 x signed32 -> signed80 product; nearest ties-even division by 2^shift",
            "parameter_files": q31_files},
        "gelu_tables": {"construction": "full signed-int16 domain from exact erf GELU; folded table stores negative half",
            "lookup": "q<0:T[q+32768]; q=0:0; q>0:q+T[32768-q], signed17 addition then i16 cast",
            "crop": {"zero_prefix": 0, "tail": 65536, "compact_crop_applied": False},
            "tables": table_files,
            "external_storage": "one 32768-entry i16 negative-half table per stage (65536 bytes each); DW/PW sequentially reuse one on-chip table RAM"},
        "channels": {"dw_w8": 128, "pw_w8": 121, "pw_w16": FROZEN_PW_W16_CHANNELS},
        "parameter_file": {"path": param_path.name, "bytes": param_path.stat().st_size, "sha256": sha256_file(param_path)},
        "candidate_packer": {"format": "unbound candidate 128-bit-word image; does not change current ABI or PL",
            "path": pack_path.name, "bytes": pack_path.stat().st_size, "sha256": sha256_file(pack_path),
            "layout": pack_layout, "unpack_roundtrip": pack_roundtrip},
        "candidate_runtime_profile": {"profile": "P3", "blocks": 1, "slot_bytes": 32768,
            "input_bytes": 32768, "output_valid_bytes": 16384, "arena_bytes": 69632,
            "output_slot": 1},
        "cases": rows, "direct_ratio_comparison": direct_rows,
        "gate": {"cosine_min": 0.999, "relative_l2_max": 0.05,
            "three_engineering_images_pass": all(r["fp32_gate_pass"] for r in rows),
            "vs_v003_code_mismatch_total": sum(r["vs_v003_codes"]["mismatch_count"] for r in rows),
            "vs_v003_exact": all(r["vs_v003_codes"]["exact"] for r in rows)},
        "hardware_cost": {"w16_full_accumulator": "signed48; bounded by 137434759168 < 2^47",
            "w16_partial_accumulator": "signed32, two terms; bounded by 2147418112 < 2^31",
            "external_gelu_bytes_per_stage": 65536, "external_gelu_bytes_both_stages": 131072,
            "on_chip_gelu_ram_reuse": "single table RAM, DW then PW"}}
    mpath = args.output / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    files = {f.name: {"bytes": f.stat().st_size, "sha256": sha256_file(f)}
             for f in sorted(args.output.iterdir()) if f.is_file()}
    (args.output / "receipt.json").write_text(json.dumps({"schema_version": 1,
        "status": manifest["status"], "manifest_sha256": sha256_file(mpath), "files": files}, indent=2), encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "manifest": str(mpath),
        "dw_shift_range": [int(dw_shift.min()), int(dw_shift.max())],
        "pw_shift_range": [int(pw_shift.min()), int(pw_shift.max())],
        "v003_mismatches": manifest["gate"]["vs_v003_code_mismatch_total"],
        "min_cosine": min(r["vs_full_fp32"]["cosine"] for r in rows),
        "max_relative_l2": max(r["vs_full_fp32"]["relative_l2"] for r in rows)}, indent=2))
    if manifest["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
