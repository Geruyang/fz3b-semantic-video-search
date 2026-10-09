"""Build the host-only full-W16 P3 candidate image and slot0 final receipt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from cnn_v10_mixed_n1_w16_pl_integer import (SIN, SMID, SOUT,
    error_metrics, load_n1_contract, sha256_file)
from cnn_v10_mixed_n1_w16_pl_integer_004 import (_normalized_params, _tables,
    verify_candidate_packed)
from cnn_v10_mixed_n1_mask_search import run_full_w16a16
from cnn_v10_mixed_n1_w16 import quantize_w16_per_output


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pack_full_w16(dw_w16, dw_bias, dw_mult, dw_shift, dw_lut_negative,
                  pw_w16, pw_bias, pw_mult, pw_shift, pw_lut_negative):
    dw_matrix = np.asarray(dw_w16, dtype="<i2").reshape(128, 49)
    pw_matrix = np.asarray(pw_w16, dtype="<i2").reshape(128, 128)
    # Frozen PL order: group(oc/4), reduction tile(ic/16), output lane,
    # input lane. The tile is [32,8,4,16] in packed word order.
    pw_tiled = pw_matrix.reshape(32, 4, 8, 16).transpose(0, 2, 1, 3).copy()
    fields = [
        ("dw_weights_i16", 0, 784, dw_matrix.tobytes()),
        ("dw_bias_i48_container_i64", 784, 64, np.asarray(dw_bias, dtype="<i8").tobytes()),
        ("dw_multiplier_i32", 848, 32, np.asarray(dw_mult, dtype="<i4").tobytes()),
        ("dw_shift_i32", 880, 32, np.asarray(dw_shift, dtype="<i4").tobytes()),
        ("dw_gelu_negative_half_i16", 912, 4096, np.asarray(dw_lut_negative, dtype="<i2").reshape(32768).tobytes()),
        ("pw_weights_i16_tiled_goc4_k16", 5008, 2048, pw_tiled.tobytes()),
        ("pw_bias_i48_container_i64", 7056, 64, np.asarray(pw_bias, dtype="<i8").tobytes()),
        ("pw_multiplier_i32", 7120, 32, np.asarray(pw_mult, dtype="<i4").tobytes()),
        ("pw_shift_i32", 7152, 32, np.asarray(pw_shift, dtype="<i4").tobytes()),
        ("pw_gelu_negative_half_i16", 7184, 4096, np.asarray(pw_lut_negative, dtype="<i2").reshape(32768).tobytes()),
    ]
    image = bytearray(11280 * 16)
    layout = {}
    for name, word_offset, word_length, payload in fields:
        start, length = word_offset * 16, word_length * 16
        if len(payload) != length:
            raise ValueError(f"{name}: expected {length} bytes, got {len(payload)}")
        image[start:start + length] = payload
        layout[name] = {"word_offset": word_offset, "word_length": word_length,
            "byte_offset": start, "byte_length": length, "sha256": _sha(payload)}
    return bytes(image), layout


def slot_contract() -> dict:
    # All offsets/counts in words use 128-bit (16-byte) words.
    return {"profile": 3, "blocks": 1, "parameter_words": 11280,
        "parameter_bytes": 180480, "word_bytes": 16,
        "slot_words": 32768, "slot_bytes": 524288,
        "arena_words": 69632, "arena_bytes": 1114112, "flags": 0,
        "input": {"slot": 0, "offset_words": 0, "offset_bytes": 0,
            "input_words": 32768, "input_bytes": 524288,
            "word_range": "slot0[0,32768)", "byte_range": "slot0[0,524288)"},
        "dw_intermediate": {"slot": 1, "offset_words": 32768, "offset_bytes": 524288,
            "output_valid_words": 16384, "output_valid_bytes": 262144,
            "word_range": "slot1[32768,49152)", "byte_range": "slot1[524288,786432)",
            "gelu_ram_action": "reload same GELU RAM for PW after DW"},
        "final_output": {"slot": 0, "offset_words": 0, "offset_bytes": 0,
            "output_valid_words": 16384, "output_valid_bytes": 262144,
            "word_range": "slot0[0,16384)", "byte_range": "slot0[0,262144)",
            "overwrites_input_after_consumption": True, "only_valid_region": True},
        "completion": {"valid_slot": 0, "output_valid_words": 16384,
            "output_valid_bytes": 262144, "consumer": "P0 base0"},
        "candidate_identity": "A0002/sw10.2"}


def validate_slot_contract(contract: dict) -> bool:
    return (contract["profile"] == 3 and contract["blocks"] == 1 and
        contract["parameter_words"] == 11280 and contract["parameter_bytes"] == 180480 and
        contract["word_bytes"] == 16 and contract["slot_words"] == 32768 and
        contract["slot_bytes"] == 524288 and contract["arena_words"] == 69632 and
        contract["arena_bytes"] == 1114112 and contract["flags"] == 0 and
        contract["input"]["word_range"] == "slot0[0,32768)" and
        contract["input"]["byte_range"] == "slot0[0,524288)" and
        contract["input"]["input_words"] * 16 == contract["input"]["input_bytes"] and
        contract["dw_intermediate"]["word_range"] == "slot1[32768,49152)" and
        contract["dw_intermediate"]["byte_range"] == "slot1[524288,786432)" and
        contract["dw_intermediate"]["output_valid_words"] * 16 == contract["dw_intermediate"]["output_valid_bytes"] and
        contract["final_output"]["word_range"] == "slot0[0,16384)" and
        contract["final_output"]["byte_range"] == "slot0[0,262144)" and
        contract["final_output"]["output_valid_words"] * 16 == contract["final_output"]["output_valid_bytes"] and
        contract["final_output"]["slot"] == 0 and contract["final_output"]["only_valid_region"] is True and
        contract["completion"]["consumer"] == "P0 base0")


def unpack_pw_w16_tiled(payload: bytes) -> np.ndarray:
    expected = 128 * 128 * 2
    if len(payload) != expected:
        raise ValueError("PW W16 packed tile has wrong byte length")
    packed = np.frombuffer(payload, dtype="<i2").reshape(32, 8, 4, 16)
    return packed.transpose(0, 2, 1, 3).reshape(128, 128).copy()


def _read_f32(path: Path, shape):
    raw = path.read_bytes()
    if len(raw) != int(np.prod(shape)) * 4:
        raise ValueError(f"fixture byte count mismatch: {path}")
    return np.frombuffer(raw, dtype="<f4").reshape(shape).copy()


def to_hcw_a16_bytes(x_nchw: np.ndarray) -> bytes:
    """Convert bridge NCHW float32 input to native HCW symmetric A16 codes."""
    x = np.asarray(x_nchw, dtype=np.float32)
    if x.shape != (1, 64, 64, 64):
        raise ValueError(f"expected NCHW (1,64,64,64), got {x.shape}")
    codes = np.clip(np.rint(x.astype(np.float64) / SIN), -32767, 32767).astype("<i2")
    return np.ascontiguousarray(codes[0].transpose(1, 0, 2)).tobytes()


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--fixture-root", type=Path, default=Path("artifacts/board-debug-20261005/acceleration/host/network-w16-same-board-golden-001"))
    p.add_argument("--fallback-root", type=Path, default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-fallback-002"))
    p.add_argument("--mixed-root", type=Path, default=Path("artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-masksearch-001"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    convs = load_n1_contract(args.model)[:2]
    dw_w16, dw_ws = quantize_w16_per_output(convs[0].weight)
    pw_w16, pw_ws = quantize_w16_per_output(convs[1].weight)
    dw_params = _normalized_params(convs[0], SIN, SMID, dw_ws, (0, 62))
    pw_params = _normalized_params(convs[1], SMID, SOUT, pw_ws, (0, 62))
    dw_full, dw_negative, dw_reconstructed, dw_bad = _tables(SMID, SMID)
    pw_full, pw_negative, pw_reconstructed, pw_bad = _tables(SOUT, SOUT)
    if len(dw_bad) or len(pw_bad) or not np.array_equal(dw_full, dw_reconstructed) or not np.array_equal(pw_full, pw_reconstructed):
        raise AssertionError("full-W16 GELU folded table must reconstruct byte-exactly")
    image, layout = pack_full_w16(dw_w16, dw_params["bias_q"], dw_params["multipliers"],
        dw_params["shifts"], dw_negative, pw_w16, pw_params["bias_q"],
        pw_params["multipliers"], pw_params["shifts"], pw_negative)
    pack_path = args.output / "candidate-p3-full-w16-params.bin"
    pack_path.write_bytes(image)
    pack_check = verify_candidate_packed(image, layout)
    pw_start = layout["pw_weights_i16_tiled_goc4_k16"]["byte_offset"]
    pw_len = layout["pw_weights_i16_tiled_goc4_k16"]["byte_length"]
    pw_roundtrip = unpack_pw_w16_tiled(image[pw_start:pw_start + pw_len])
    if not np.array_equal(pw_roundtrip, pw_w16.reshape(128, 128)):
        raise AssertionError("PW W16 tile unpack did not recover every original weight")

    npz_path = args.output / "p3-full-w16-params.npz"
    np.savez(npz_path, dw_w16=dw_w16.astype("<i2"), dw_weight_scale=dw_ws,
        dw_bias_q48=dw_params["bias_q"], dw_q31_multiplier=np.asarray(dw_params["multipliers"], dtype="<i4"),
        dw_q31_shift=np.asarray(dw_params["shifts"], dtype="<i4"), pw_w16=pw_w16.astype("<i2"),
        pw_weight_scale=pw_ws, pw_bias_q48=pw_params["bias_q"],
        pw_q31_multiplier=np.asarray(pw_params["multipliers"], dtype="<i4"),
        pw_q31_shift=np.asarray(pw_params["shifts"], dtype="<i4"),
        dw_gelu_full=dw_full, dw_gelu_negative=dw_negative,
        pw_gelu_full=pw_full, pw_gelu_negative=pw_negative)

    cases = []
    dw_bounds = {"k": 49, "full_acc48_abs_bound": 49 * 32768 * 32767,
        "two_term_partial_acc32_abs_bound": 2 * 32768 * 32767,
        "full_fits_signed48": 49 * 32768 * 32767 < (1 << 47),
        "partial_fits_signed32": 2 * 32768 * 32767 <= (1 << 31) - 1}
    pw_bounds = {"k": 128, "full_acc48_abs_bound": 128 * 32768 * 32767,
        "two_term_partial_acc32_abs_bound": 2 * 32768 * 32767,
        "full_fits_signed48": 128 * 32768 * 32767 < (1 << 47),
        "partial_fits_signed32": 2 * 32768 * 32767 <= (1 << 31) - 1}
    all_codes_exact = True
    for i in range(3):
        board = args.fixture_root / f"image-{i:02d}" / "board"
        input_path = board / "network1-bridge-input.f32"
        fp_path = board / "network1-bridge-output.f32"
        fallback_path = args.fallback_root / f"image-{i:02d}-mixed-fp32-fallback.f32"
        prior_code_path = args.mixed_root / f"full-dw-pw-w16-image-{i:02d}.i16"
        x = _read_f32(input_path, (1, 64, 64, 64))
        ref = _read_f32(fp_path, (1, 128, 32, 32))
        fallback = _read_f32(fallback_path, (1, 128, 32, 32))
        output, codes, proof = run_full_w16a16(convs, x)
        prior_codes = np.fromfile(prior_code_path, dtype="<i2").reshape(codes.shape)
        mismatch = int(np.count_nonzero(codes != prior_codes))
        all_codes_exact &= mismatch == 0
        out_path = args.output / f"image-{i:02d}-p3-full-w16-output.f32"
        code_path = args.output / f"image-{i:02d}-p3-full-w16-output.i16"
        output.astype("<f4").tofile(out_path)
        np.ascontiguousarray(codes[0].transpose(1, 0, 2)).astype("<i2").tofile(code_path)
        input_hcw_path = args.output / f"image-{i:02d}-p3-input-hcw-a16.i16"
        input_hcw = to_hcw_a16_bytes(x)
        input_hcw_path.write_bytes(input_hcw)
        mixed_output = _read_f32(args.mixed_root / f"mask16-image-{i:02d}.f32", (1, 128, 32, 32))
        cases.append({"case_id": f"image-{i:02d}", "input_sha256": sha256_file(input_path),
            "input_hcw_a16": {"path": input_hcw_path.name, "bytes": len(input_hcw),
                "sha256": sha256_file(input_hcw_path), "layout": "HCW contiguous",
                "shape": [64, 64, 64], "conversion": "symmetric A16; clip[-32767,32767]; numpy rint ties-even; divide by frozen Sin"},
            "fp32_output_sha256": sha256_file(fp_path), "fallback_output_sha256": sha256_file(fallback_path),
            "prior_full_w16_code_sha256": sha256_file(prior_code_path),
            "output_sha256": sha256_file(out_path), "codes_sha256": sha256_file(code_path),
            "output_i16": {"path": code_path.name, "bytes": code_path.stat().st_size,
                "sha256": sha256_file(code_path), "layout": "HCW contiguous",
                "shape": [128, 32, 32]},
            "independent_oracle_code_comparison": {"mismatch_count": mismatch,
                "total_codes": int(codes.size), "exact": mismatch == 0},
            "vs_full_fp32": error_metrics(ref, output),
            "vs_current_fallback": error_metrics(fallback, output),
            "vs_mask16_mixed": error_metrics(mixed_output, output),
            "full_model_gate_pass": error_metrics(ref, output)["cosine"] >= 0.999 and error_metrics(ref, output)["relative_l2"] <= 0.05,
            "arithmetic_observed": proof})

    slots = slot_contract()
    manifest = {"schema_version": 1, "candidate": "A0002-sw10.2-p3-full-dw-pw-w16a16",
        "status": "PASS" if validate_slot_contract(slots) and pack_check["pass"] and all_codes_exact and all(c["full_model_gate_pass"] for c in cases) else "FAIL",
        "execution": "host-only full-W16 integer oracle and candidate packer; no PL build or target execution",
        "source_model": {"path": str(args.model), "sha256": sha256_file(args.model)},
        "backend": "PL full DW/PW W16A16 candidate; distinct from PS W8/A16 plus sensitive-channel FP32 fallback",
        "runtime_identity": slots,
        "parameters": {"path": pack_path.name, "bytes": len(image), "words128": len(image) // 16,
            "sha256": sha256_file(pack_path), "layout": layout, "unpack_roundtrip": pack_check,
            "pw_weight_tile_order": "group(oc/4) -> reduction_tile(ic/16) -> output_lane4 -> input_lane16",
            "pw_weight_unpack_roundtrip": {"exact": True, "weight_count": int(pw_w16.size),
                "sha256_reconstructed_oik": _sha(pw_roundtrip.astype("<i2").tobytes())},
            "npz_path": npz_path.name, "npz_bytes": npz_path.stat().st_size, "npz_sha256": sha256_file(npz_path)},
        "quantization": {"weight": "all DW/PW output channels symmetric W16; max(abs(w))/32767; ties-even",
            "dw_multiplier2_source_channel": "source_ch = output_channel >> 1",
            "dw_weight_order": "[oc128][ky7][kx7] C-order",
            "activation": "symmetric A16 using Sin/Smid/Sout",
            "bias": "ties-even(bias/(A_scale*W_scale)); checked signed48",
            "q31": "integer_postops.multiplier_shift from each real ratio; signed i32 multiplier, shifts 0..62; exact signed48 x signed32 -> signed80 ties-even via q31_round_even_wide",
            "q31_shift_ranges": {"dw": [int(dw_params["shifts"].min()), int(dw_params["shifts"].max())],
                "pw": [int(pw_params["shifts"].min()), int(pw_params["shifts"].max())]},
            "gelu": {"full_table_entries": 65536, "negative_half_entries": 32768,
                "dw_full_sha256": _sha(dw_full.tobytes()), "dw_negative_half_sha256": _sha(dw_negative.tobytes()),
                "pw_full_sha256": _sha(pw_full.tobytes()), "pw_negative_half_sha256": _sha(pw_negative.tobytes()),
                "fold_identity_bad_count": int(len(dw_bad) + len(pw_bad)), "zero_code": 0,
                "negative_half_table_bytes_per_stage": 65536}},
        "accumulator_proofs": {"dw": dw_bounds, "pw": pw_bounds,
            "bias_signed48": True, "requant_product_signed80": True,
            "full_acc48_bound_max": max(dw_bounds["full_acc48_abs_bound"], pw_bounds["full_acc48_abs_bound"]),
            "partial_acc32_bound": pw_bounds["two_term_partial_acc32_abs_bound"]},
        "cases": cases,
        "gates": {"full_model_cosine_min": 0.999, "full_model_relative_l2_max": 0.05,
            "three_image_full_model_pass": all(c["full_model_gate_pass"] for c in cases),
            "exact_code_match_to_prior_full_w16_oracle": all_codes_exact},
        "hardware_accounting": {"weight_storage": "all physical MAC weights signed i16",
            "same_dsp_mac_count_as_mixed_candidate": True,
            "P3_input_slot0": "[0,32768)", "P3_dw_intermediate_slot1": "[32768,49152)",
            "P3_final_output_slot0": "[0,16384)", "P0_consumer_base": 0}}
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    receipt = {"schema_version": 1, "status": manifest["status"],
        "manifest_sha256": sha256_file(manifest_path),
        "files": {f.name: {"bytes": f.stat().st_size, "sha256": sha256_file(f)}
            for f in sorted(args.output.iterdir()) if f.is_file()}}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "manifest": str(manifest_path),
        "parameter_sha256": sha256_file(pack_path), "min_cosine": min(c["vs_full_fp32"]["cosine"] for c in cases),
        "max_relative_l2": max(c["vs_full_fp32"]["relative_l2"] for c in cases),
        "exact_code_match": all_codes_exact}, indent=2))
    if manifest["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
