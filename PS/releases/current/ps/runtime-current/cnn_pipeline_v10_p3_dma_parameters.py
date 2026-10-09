"""Build/load the isolated A0004 P3/internal-FIFO parameter identity."""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import pathlib
import shutil


OLD_COMBINED_SHA256 = "c62b9f49b1118916168a2ca7a4a63c56d51bba66a0921523af35d46495bbab99"
P3_PARAMS_SHA256 = "f6ece07c73678835a6d25dd13b5ecafa7f106f03d279eea7b2b51a1898cc09ce"
CORE_ABI = 0x000A0004
SOFTWARE_IDENTITY = "sw10.4"
SOFTWARE_UAPI = 10
PROFILE_SLOTS = (16384, 8192, 32768, 32768)
PROFILE_ARENAS = (36864, 20480, 69632, 69632)
PROFILE_INPUT_WORDS = (16384, 8192, 32768, 32768)
PROFILE_OUTPUT_WORDS = (16384, 8192, 32768, 16384)
PROFILE_BLOCKS = (12, 20, 4, 1)
PROFILE_STRIDES = (21081, 59705, 10985, 11280)
RESIDUAL_WORDS = 4096
EXTERNAL_STAGE_RING_WORDS = 0


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(character not in "0123456789abcdef" for character in value)):
        raise ValueError("%s must be lowercase SHA256" % label)
    return value


def _safe_child(root, relative, label):
    if not isinstance(relative, str) or not relative:
        raise ValueError("%s path is missing" % label)
    normalized = relative.replace("\\", "/")
    if (normalized.startswith("/") or ":" in normalized.split("/")[0] or
            any(part in ("", ".", "..") for part in normalized.split("/"))):
        raise ValueError("%s path is unsafe" % label)
    path = (root / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(root.resolve()), str(path))) != str(root.resolve()):
        raise ValueError("%s path escapes package" % label)
    return path


def profile_contract(profile):
    if isinstance(profile, bool) or not isinstance(profile, int) or not 0 <= profile < 4:
        raise ValueError("profile must be 0..3")
    slot = PROFILE_SLOTS[profile]
    if 2 * slot + RESIDUAL_WORDS != PROFILE_ARENAS[profile]:
        raise AssertionError("internal-FIFO arena does not match exact A0004 extent")
    if profile == 3:
        output_rule = {"kind": "fixed_slot0", "offset_words": 0}
    else:
        output_rule = {
            "kind": "ping_pong_block_parity",
            "expression": "(block_count & 1) * slot_words",
            "even_block_count_offset_words": 0,
            "odd_block_count_offset_words": slot,
        }
    return {
        "profile": profile, "max_blocks": PROFILE_BLOCKS[profile],
        "block_stride_words": PROFILE_STRIDES[profile],
        "slot_words": slot, "arena_words": PROFILE_ARENAS[profile],
        "input_offset_words": 0, "input_valid_words": PROFILE_INPUT_WORDS[profile],
        "output_offset_rule": output_rule,
        # The frozen full-model counts are 12/20/4 and therefore end in slot0.
        # P3 is a single two-stage invocation whose final output is also slot0.
        "full_count_output_offset_words": 0,
        "output_valid_words": PROFILE_OUTPUT_WORDS[profile],
        "residual_offset_words": 2 * slot, "residual_words": RESIDUAL_WORDS,
        "external_stage_ring_words": EXTERNAL_STAGE_RING_WORDS,
    }


CHAIN_CONTRACT = {
    "core_abi": CORE_ABI, "software_identity": SOFTWARE_IDENTITY,
    "software_uapi": SOFTWARE_UAPI,
    "topology": {
        "stage_storage": "internal_fifo_v1",
        "external_stage_ring_words": EXTERNAL_STAGE_RING_WORDS,
        "activation_broker_clients_per_core": {"read": 2, "write": 2},
        "residual_scratch_words_per_arena": RESIDUAL_WORDS,
    },
    "profiles": [2, 3, 0], "profile_block_counts": [4, 1, 12],
    "profile_output_offsets_words": [0, 0, 0], "word_bits": 128,
    "profile_contracts": [profile_contract(index) for index in range(4)],
    "p3": {"profile": 3, "blocks": 1, "flags": 0,
           "params_words": 11280, "input_offset_words": 0,
           "input_words": 32768, "intermediate_offset_words": 32768,
           "intermediate_words": 16384, "output_offset_words": 0,
           "output_words": 16384, "slot_words": 32768,
           "arena_words": 69632},
    "p0_base_offset_words": 0,
}


def build_a0004_combined(old_manifest_path, old_manifest_sha256, output_root):
    old_path = pathlib.Path(old_manifest_path).resolve()
    old_raw = old_path.read_bytes()
    if (_sha(old_raw) != _checked_sha(old_manifest_sha256, "old combined manifest") or
            old_manifest_sha256 != OLD_COMBINED_SHA256):
        raise ValueError("old A0002 combined identity mismatch")
    old = json.loads(old_raw.decode("utf-8"))
    if (old.get("status") != "PASS" or
            old.get("schema") != "cnn-pipeline-v10.1-p3-combined-parameter-manifest-v1"):
        raise ValueError("old A0002 combined manifest contract mismatch")
    record = old.get("p3_parameter_file", {})
    p3_path = _safe_child(old_path.parent, record.get("path"), "P3 parameters")
    p3_raw = p3_path.read_bytes()
    if (record.get("bytes") != len(p3_raw) or record.get("sha256") != _sha(p3_raw) or
            _sha(p3_raw) != P3_PARAMS_SHA256 or len(p3_raw) != 11280 * 16):
        raise ValueError("P3 raw parameters differ from the frozen bytes")
    output = pathlib.Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(str(p3_path), str(output / "p3-params.bin"))
    manifest = {
        "schema": "cnn-pipeline-v10.4-p3-dma-combined-parameter-manifest-v1",
        "status": "PASS_OFFLINE_IDENTITY_ONLY",
        "deployment_ready": False,
        "hardware_execution": False,
        "identity_role": "manifest-sha256-as-eight-big-endian-u32-guard-words",
        "core_abi": CORE_ABI, "software_identity": SOFTWARE_IDENTITY,
        "software_uapi": SOFTWARE_UAPI,
        "source_a0002_combined_manifest_sha256": OLD_COMBINED_SHA256,
        "base_release_manifest_sha256": old["base_release_manifest_sha256"],
        "base_parameter_manifest_sha256": old["base_parameter_manifest_sha256"],
        "base_profiles": old["base_profiles"],
        "p3_source_manifest_sha256": old["p3_manifest_sha256"],
        "p3_parameter_file": {"path": "p3-params.bin", "bytes": len(p3_raw),
                              "sha256": _sha(p3_raw)},
        "raw_parameter_bytes_changed": False,
        "chain_contract": CHAIN_CONTRACT,
        "gates": {"a0004_internal_fifo_layout_contract_host_pass": True,
                  "raw_parameter_identity_unchanged": True,
                  "target_kernel_compile": False,
                  "rtl_simulation": False,
                  "hardware_validation": False},
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                             encoding="utf-8")
    digest = _sha(manifest_path.read_bytes())
    receipt = {
        "schema": "cnn-pipeline-v10.4-p3-dma-combined-parameter-receipt-v1",
        "status": "PASS_OFFLINE_IDENTITY_ONLY",
        "deployment_ready": False,
        "manifest_sha256": digest,
        "manifest_words_be32": [int(digest[index:index + 8], 16)
                                for index in range(0, 64, 8)],
        "files": {
            "manifest.json": {"bytes": manifest_path.stat().st_size,
                              "sha256": digest},
            "p3-params.bin": {"bytes": len(p3_raw), "sha256": _sha(p3_raw)}},
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def load_v10_p3_dma_parameters(path, expected_sha256):
    manifest_path = pathlib.Path(path).resolve()
    raw = manifest_path.read_bytes()
    digest = _checked_sha(expected_sha256, "A0004 combined manifest")
    if _sha(raw) != digest:
        raise ValueError("A0004 combined manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") !=
            "cnn-pipeline-v10.4-p3-dma-combined-parameter-manifest-v1" or
            manifest.get("status") != "PASS_OFFLINE_IDENTITY_ONLY" or
            manifest.get("deployment_ready") is not False or
            manifest.get("hardware_execution") is not False or
            manifest.get("core_abi") != CORE_ABI or
            manifest.get("software_identity") != SOFTWARE_IDENTITY or
            manifest.get("software_uapi") != SOFTWARE_UAPI or
            manifest.get("chain_contract") != CHAIN_CONTRACT or
            manifest.get("raw_parameter_bytes_changed") is not False):
        raise ValueError("A0004 combined manifest contract mismatch")
    params_path = _safe_child(
        manifest_path.parent, manifest.get("p3_parameter_file", {}).get("path"),
        "P3 parameters")
    params = params_path.read_bytes()
    record = manifest["p3_parameter_file"]
    if (record.get("bytes") != len(params) or record.get("sha256") != _sha(params) or
            _sha(params) != P3_PARAMS_SHA256):
        raise ValueError("A0004 P3 parameter payload mismatch")
    return {"manifest_sha256": digest,
            "chain_manifest_sha256": digest,
            "parameter_manifest_words": tuple(
                int(digest[index:index + 8], 16) for index in range(0, 64, 8)),
            "p3_manifest_sha256": manifest["p3_source_manifest_sha256"],
            "params": params, "params_path": str(params_path),
            "contract": CHAIN_CONTRACT,
            "evidence": manifest["gates"]}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-manifest", required=True)
    parser.add_argument("--old-manifest-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_a0004_combined(
        args.old_manifest, args.old_manifest_sha256, args.output), indent=2))


if __name__ == "__main__":
    main()


__all__ = ["CHAIN_CONTRACT", "profile_contract", "build_a0004_combined",
           "load_v10_p3_dma_parameters"]
