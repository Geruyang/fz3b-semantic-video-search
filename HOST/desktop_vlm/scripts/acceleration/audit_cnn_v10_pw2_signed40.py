"""Audit frozen V10 PW2 parameters for exact signed40 storage safety."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib
import struct
import sys


ROOT = pathlib.Path(__file__).resolve().parents[3]
BOARD = ROOT / "desktop_vlm" / "board"
if str(BOARD) not in sys.path:
    sys.path.insert(0, str(BOARD))

from cnn_v10_pw2_signed40_contract import (  # noqa: E402
    ADMISSION_SCHEMA, CONTRACT_KIND, INPUT_ABS_BOUND, LAYOUT_VERSION, MAX_ABS_BOUND,
    PENDING_IDENTITY, SCHEMA, STORAGE_SIGNED_BITS, canonical_json_bytes,
    sha256_bytes, sha256_file, validate_contract_object)


WORD_BYTES = 16
PROFILES = {
    0: {"channels": 128, "blocks": 12, "stride_words": 21081,
        "bias_offset_words": 928, "pw2_weight_offset_words": 14937,
        "tile_order": "normal_pw2_r_group_v1"},
    1: {"channels": 256, "blocks": 20, "stride_words": 59705,
        "bias_offset_words": 1856, "pw2_weight_offset_words": 35129,
        "tile_order": "normal_pw2_r_group_v1"},
    2: {"channels": 64, "blocks": 4, "stride_words": 10985,
        "bias_offset_words": 464, "pw2_weight_offset_words": 9449,
        "tile_order": "normal_pw2_r_group_v1"},
    3: {"channels": 128, "blocks": 1, "stride_words": 11280,
        "bias_offset_words": 7056, "pw2_weight_offset_words": 5008,
        "tile_order": "p3_pw_group_r_v1"},
}


def _sha_file_record(path):
    path = pathlib.Path(path)
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": sha256_file(path)}


def _read_i64(raw, offset):
    if offset < 0 or offset + 8 > len(raw):
        raise ValueError("i64 parameter read exceeds blob")
    return struct.unpack_from("<q", raw, offset)[0]


def _read_i16(raw, offset):
    if offset < 0 or offset + 2 > len(raw):
        raise ValueError("i16 parameter read exceeds blob")
    return struct.unpack_from("<h", raw, offset)[0]


def _read_i32(raw, offset):
    if offset < 0 or offset + 4 > len(raw):
        raise ValueError("i32 parameter read exceeds blob")
    return struct.unpack_from("<i", raw, offset)[0]


def _pw2_biases(raw, block_base_words, spec):
    c = spec["channels"]
    start = (block_base_words + spec["bias_offset_words"]) * WORD_BYTES
    if spec["tile_order"] == "normal_pw2_r_group_v1":
        start += 5 * c * 8
    values = [_read_i64(raw, start + channel * 8) for channel in range(c)]
    if any(value < -(1 << 47) or value > (1 << 47) - 1 for value in values):
        raise ValueError("PW2 bias does not fit signed48")
    return values


def _pw2_sumabs(raw, block_base_words, spec):
    c = spec["channels"]
    reductions = 3 * c // 16 if spec["tile_order"] == "normal_pw2_r_group_v1" else 8
    groups = c // 4
    start = (block_base_words + spec["pw2_weight_offset_words"]) * WORD_BYTES
    tile_bytes = 4 * 16 * 2
    expected_tiles = reductions * groups
    if start + expected_tiles * tile_bytes > len(raw):
        raise ValueError("PW2 weight extent exceeds blob")
    sums = [0] * c
    for outer in range(reductions if spec["tile_order"] == "normal_pw2_r_group_v1" else groups):
        inner_count = groups if spec["tile_order"] == "normal_pw2_r_group_v1" else reductions
        for inner in range(inner_count):
            reduction = outer if spec["tile_order"] == "normal_pw2_r_group_v1" else inner
            group = inner if spec["tile_order"] == "normal_pw2_r_group_v1" else outer
            tile = reduction * groups + group if spec["tile_order"] == "normal_pw2_r_group_v1" else group * reductions + reduction
            at = start + tile * tile_bytes
            for lane in range(4):
                channel = group * 4 + lane
                lane_at = at + lane * 16 * 2
                sums[channel] += sum(abs(_read_i16(raw, lane_at + k * 2))
                                     for k in range(16))
    return sums


def _pw2_shifts(raw, block_base_words, spec):
    c = spec["channels"]
    if spec["tile_order"] == "normal_pw2_r_group_v1":
        # bias_offset is the beginning of 6*C i64 biases.  It is followed by
        # 6*C i32 multipliers and then 6*C i32 shifts.  PW2 is logical
        # coefficient range [5*C, 6*C).
        start_words = (block_base_words + spec["bias_offset_words"] +
                       3 * c + (6 * c // 4))
        start = start_words * WORD_BYTES + 5 * c * 4
    else:
        start = (block_base_words + 7152) * WORD_BYTES
    values = [_read_i32(raw, start + channel * 4) for channel in range(c)]
    if any(value < 0 or value > 62 for value in values):
        raise ValueError("PW2 shift is outside 0..62")
    return values


def audit_blob(profile, raw, expected_sha256=None):
    if profile not in PROFILES:
        raise ValueError("profile must be 0..3")
    spec = PROFILES[profile]
    expected_bytes = spec["blocks"] * spec["stride_words"] * WORD_BYTES
    if len(raw) != expected_bytes:
        raise ValueError("profile %d parameter byte extent mismatch" % profile)
    identity = sha256_bytes(raw)
    if expected_sha256 is not None and identity != expected_sha256:
        raise ValueError("profile %d parameter SHA mismatch" % profile)
    blocks = []
    profile_max = 0
    for block in range(spec["blocks"]):
        base = block * spec["stride_words"]
        biases = _pw2_biases(raw, base, spec)
        sums = _pw2_sumabs(raw, base, spec)
        shifts = _pw2_shifts(raw, base, spec)
        bounds = [abs(biases[ch]) + INPUT_ABS_BOUND * sums[ch]
                  for ch in range(spec["channels"])]
        block_max = max(bounds)
        profile_max = max(profile_max, block_max)
        blocks.append({
            "block": block,
            "channel_bounds": bounds,
            "max_abs_bound": block_max,
            "max_channel": bounds.index(block_max),
            "shift_min": min(shifts),
            "shift_max": max(shifts),
            "all_pw2_shifts_in_range": True,
            "all_channels_fit_signed40": block_max <= MAX_ABS_BOUND,
        })
    return {
        "profile": profile, "channels": spec["channels"],
        "blocks": spec["blocks"], "stride_words": spec["stride_words"],
        "parameter_bytes": len(raw), "parameter_sha256": identity,
        "pw2_bias_index": ("5c_to_6c" if profile < 3 else
                            "p3_word7056_i64x128"),
        "pw2_weight_tile_order": spec["tile_order"],
        "pw2_weight_signed_bits": 16,
        "signed40_storage_applies": profile in (0, 1, 2),
        "max_abs_bound": profile_max,
        "max_block": next(item["block"] for item in blocks
                          if item["max_abs_bound"] == profile_max),
        "max_channel": next(item["max_channel"] for item in blocks
                            if item["max_abs_bound"] == profile_max),
        "all_prefixes_fit_signed40": profile_max <= MAX_ABS_BOUND,
        "blocks_detail": blocks,
    }


def _case_by_profile(fixtures):
    cases = fixtures.get("cases")
    if not isinstance(cases, list):
        raise ValueError("fixture manifest cases are missing")
    result = {}
    for case in cases:
        profile = case.get("profile")
        if profile in result or profile not in PROFILES:
            raise ValueError("fixture profiles must be unique 0..3")
        result[profile] = case
    if set(result) != set(PROFILES):
        raise ValueError("fixture manifest must cover profiles 0..3")
    return result


def build_report(fixture_manifest_path, combined_manifest_path):
    fixture_manifest_path = pathlib.Path(fixture_manifest_path).resolve()
    combined_manifest_path = pathlib.Path(combined_manifest_path).resolve()
    fixtures = json.loads(fixture_manifest_path.read_text(encoding="utf-8"))
    combined = json.loads(combined_manifest_path.read_text(encoding="utf-8"))
    if fixtures.get("core_abi") != "0x000A0004":
        raise ValueError("source fixture ABI must be A0004")
    combined_sha = sha256_file(combined_manifest_path)
    if fixtures.get("combined_parameter_manifest_sha256") != combined_sha:
        raise ValueError("fixture and combined manifest identities differ")
    by_profile = _case_by_profile(fixtures)
    results = []
    approved = {}
    for profile in sorted(PROFILES):
        case = by_profile[profile]
        param = case.get("files", {}).get("params", {})
        path = (fixture_manifest_path.parent / param.get("path", "")).resolve()
        expected_sha = param.get("sha256")
        raw = path.read_bytes()
        if len(raw) != param.get("bytes"):
            raise ValueError("profile %d fixture parameter bytes mismatch" % profile)
        result = audit_blob(profile, raw, expected_sha)
        result["path"] = str(path)
        results.append(result)
        approved[str(profile)] = result["parameter_sha256"]
    passed = all(item["all_prefixes_fit_signed40"] for item in results)
    return {
        "schema": SCHEMA,
        "status": "PASS" if passed else "FAIL",
        "pass": passed,
        "hardware_execution": False,
        "formula": "abs(bias)+32768*sumabs(weight)",
        "proof_scope": "every block, output channel, and therefore every MAC prefix for any signed16 activation code",
        "storage_signed_bits": STORAGE_SIGNED_BITS,
        "input_code_abs_bound": INPUT_ABS_BOUND,
        "max_abs_bound_inclusive": MAX_ABS_BOUND,
        "layout_version": LAYOUT_VERSION,
        "layout_orders": {
            "profiles_0_1_2": "normal_pw2_r_group_v1",
            "profile_3": "p3_pw_group_r_v1",
        },
        "hardware_scope": {
            "signed40_profiles": [0, 1, 2],
            "signed40_objects": ["normal_pw2_accum_all", "normal_pw2_result_fifo"],
            "profile3": "identity/layout audited but P3 remains signed48 and is not narrowed",
        },
        "fixture_manifest": _sha_file_record(fixture_manifest_path),
        "source_combined_manifest": _sha_file_record(combined_manifest_path),
        "approved_raw_parameter_sha256_by_profile": approved,
        "profiles": results,
        "global_max_abs_bound": max(item["max_abs_bound"] for item in results),
        "global_max_profile": max(results, key=lambda item: item["max_abs_bound"])["profile"],
        "signed40_applied_max_abs_bound": max(
            item["max_abs_bound"] for item in results
            if item["signed40_storage_applies"]),
        "boundary": "This proves the frozen raw parameter set only; arbitrary legacy parameters are not compatible with signed40 storage.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-manifest", type=pathlib.Path, required=True)
    parser.add_argument("--combined-manifest", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)
    report = build_report(args.fixture_manifest, args.combined_manifest)
    proof_path = args.output_dir / "proof.json"
    proof_path.write_bytes(canonical_json_bytes(report))
    proof_sha = sha256_file(proof_path)
    contract = {
        "kind": CONTRACT_KIND,
        "storage_signed_bits": STORAGE_SIGNED_BITS,
        "input_code_abs_bound": INPUT_ABS_BOUND,
        "max_abs_bound_inclusive": MAX_ABS_BOUND,
        "bound_formula": "abs(bias)+32768*sumabs(weight)",
        "proof_layout_version": LAYOUT_VERSION,
        "proof_receipt_sha256": proof_sha,
        "approved_raw_parameter_sha256_by_profile":
            report["approved_raw_parameter_sha256_by_profile"],
        "required_core_abi": 0x000A0005,
        "required_guard_cap_bit": 0x00000800,
        "required_guard_caps": 0x00000fff,
        "required_combined_manifest_sha256": PENDING_IDENTITY,
    }
    validate_contract_object(contract, require_final_identity=False)
    template = {
        "schema": ADMISSION_SCHEMA,
        "status": "PENDING_COMBINED_MANIFEST_FREEZE",
        "pass": False,
        "deployment_ready": False,
        "proof_receipt_sha256": proof_sha,
        "contract": contract,
        "fail_closed_reason": "A0005 combined manifest and eight guard words are not frozen",
    }
    template_path = args.output_dir / "admission-template.json"
    template_path.write_bytes(canonical_json_bytes(template))
    receipt = {
        "schema": "cnn-v10-pw2-signed40-audit-receipt-v1",
        "status": "PASS_RANGE_PROOF_PENDING_HARDWARE_IDENTITY" if report["pass"] else "FAIL",
        "pass": report["pass"],
        "deployment_ready": False,
        "hardware_execution": False,
        "proof": _sha_file_record(proof_path),
        "admission_template": _sha_file_record(template_path),
        "global_max_abs_bound": report["global_max_abs_bound"],
        "signed40_max_inclusive": MAX_ABS_BOUND,
    }
    (args.output_dir / "receipt.json").write_bytes(canonical_json_bytes(receipt))
    print(json.dumps(receipt, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
