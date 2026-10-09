"""Build and load the isolated A0005 signed40 parameter identity.

The combined manifest embeds the independently generated range-proof
metadata, but never embeds its own SHA.  The external admission manifest is
created only after the combined bytes are frozen and binds that final SHA.
"""
from __future__ import print_function

import argparse
import copy
import hashlib
import json
import os
import pathlib
import shutil

import cnn_pipeline_v10_p3_dma_parameters as a0004
from cnn_v10_pw2_signed40_contract import (
    ADMISSION_SCHEMA, CONTRACT_KIND, INPUT_ABS_BOUND, LAYOUT_VERSION,
    MAX_ABS_BOUND, SCHEMA as PROOF_SCHEMA, STORAGE_SIGNED_BITS,
    Signed40ParameterAdmission, canonical_json_bytes, load_admission_manifest,
    sha256_file, validate_contract_object)


CORE_ABI = 0x000A0005
SOFTWARE_IDENTITY = "sw10.5"
SOFTWARE_UAPI = 10
GUARD_CAPS = 0x00000fff
PW2_SIGNED40_CAP_BIT = 0x00000800
SOURCE_A0004_COMBINED_SHA256 = \
    "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9"
P3_PARAMS_SHA256 = a0004.P3_PARAMS_SHA256


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


CHAIN_CONTRACT = copy.deepcopy(a0004.CHAIN_CONTRACT)
CHAIN_CONTRACT["core_abi"] = CORE_ABI
CHAIN_CONTRACT["software_identity"] = SOFTWARE_IDENTITY


def compatibility_from_proof(proof, proof_sha256):
    proof_sha256 = _checked_sha(proof_sha256, "range proof")
    if (not isinstance(proof, dict) or proof.get("schema") != PROOF_SCHEMA or
            proof.get("status") != "PASS" or proof.get("pass") is not True or
            proof.get("storage_signed_bits") != STORAGE_SIGNED_BITS or
            proof.get("input_code_abs_bound") != INPUT_ABS_BOUND or
            proof.get("max_abs_bound_inclusive") != MAX_ABS_BOUND or
            proof.get("formula") != "abs(bias)+32768*sumabs(weight)" or
            proof.get("layout_version") != LAYOUT_VERSION):
        raise ValueError("PW2 signed40 range proof contract mismatch")
    profiles = proof.get("profiles")
    if (not isinstance(profiles, list) or len(profiles) != 4 or
            [item.get("profile") for item in profiles] != [0, 1, 2, 3] or
            any(item.get("all_prefixes_fit_signed40") is not True
                for item in profiles) or
            [item.get("signed40_storage_applies") for item in profiles] !=
            [True, True, True, False]):
        raise ValueError("PW2 signed40 proof profile scope mismatch")
    approved = proof.get("approved_raw_parameter_sha256_by_profile")
    if not isinstance(approved, dict) or set(approved) != set(("0", "1", "2", "3")):
        raise ValueError("PW2 signed40 approved parameter set is incomplete")
    for profile, identity in approved.items():
        _checked_sha(identity, "profile %s parameters" % profile)
    return {
        "kind": CONTRACT_KIND,
        "storage_signed_bits": STORAGE_SIGNED_BITS,
        "input_code_abs_bound": INPUT_ABS_BOUND,
        "max_abs_bound_inclusive": MAX_ABS_BOUND,
        "bound_formula": "abs(bias)+32768*sumabs(weight)",
        "proof_layout_version": LAYOUT_VERSION,
        "proof_receipt_sha256": proof_sha256,
        "approved_raw_parameter_sha256_by_profile": dict(approved),
        "required_guard_cap_bit": PW2_SIGNED40_CAP_BIT,
        "required_guard_caps": GUARD_CAPS,
        "signed40_profiles": [0, 1, 2],
        "signed40_objects": ["normal_pw2_accum_all", "normal_pw2_result_fifo"],
        "profile3_signed40_storage_applies": False,
        "normal_pw2_weight_layout": "normal_pw2_r_group_v1",
        "p3_pw_weight_layout": "p3_pw_group_r_v1",
        "global_max_abs_bound": proof["global_max_abs_bound"],
        "signed40_applied_max_abs_bound": proof["signed40_applied_max_abs_bound"],
    }


def build_a0005_combined(source_manifest_path, source_manifest_sha256,
                         p3_params_path, proof_path, proof_sha256, output_root):
    source_path = pathlib.Path(source_manifest_path).resolve()
    source_raw = source_path.read_bytes()
    if (_sha(source_raw) != _checked_sha(source_manifest_sha256, "A0004 combined") or
            source_manifest_sha256 != SOURCE_A0004_COMBINED_SHA256):
        raise ValueError("source A0004 combined identity mismatch")
    source = json.loads(source_raw.decode("utf-8"))
    if (source.get("schema") !=
            "cnn-pipeline-v10.4-p3-dma-combined-parameter-manifest-v1" or
            source.get("status") != "PASS_OFFLINE_IDENTITY_ONLY" or
            source.get("core_abi") != a0004.CORE_ABI or
            source.get("software_identity") != a0004.SOFTWARE_IDENTITY or
            source.get("software_uapi") != a0004.SOFTWARE_UAPI or
            source.get("chain_contract") != a0004.CHAIN_CONTRACT or
            source.get("raw_parameter_bytes_changed") is not False):
        raise ValueError("source A0004 combined contract mismatch")
    proof_path = pathlib.Path(proof_path).resolve()
    if sha256_file(proof_path) != _checked_sha(proof_sha256, "range proof"):
        raise ValueError("PW2 signed40 proof SHA mismatch")
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    compatibility = compatibility_from_proof(proof, proof_sha256)
    p3_record = source["p3_parameter_file"]
    p3_path = pathlib.Path(p3_params_path).resolve()
    p3_raw = p3_path.read_bytes()
    if (len(p3_raw) != p3_record.get("bytes") or
            _sha(p3_raw) != p3_record.get("sha256") or
            _sha(p3_raw) != P3_PARAMS_SHA256):
        raise ValueError("P3 raw parameters differ from the approved bytes")

    output = pathlib.Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(str(p3_path), str(output / "p3-params.bin"))
    manifest = {
        "schema": "cnn-pipeline-v10.5-signed40-combined-parameter-manifest-v1",
        "status": "PASS_OFFLINE_IDENTITY_ONLY",
        "deployment_ready": False,
        "hardware_execution": False,
        "identity_role": "manifest-sha256-as-eight-big-endian-u32-guard-words",
        "core_abi": CORE_ABI,
        "software_identity": SOFTWARE_IDENTITY,
        "software_uapi": SOFTWARE_UAPI,
        "guard_caps": GUARD_CAPS,
        "required_guard_cap_bit": PW2_SIGNED40_CAP_BIT,
        "source_a0004_combined_manifest_sha256": SOURCE_A0004_COMBINED_SHA256,
        "base_release_manifest_sha256": source["base_release_manifest_sha256"],
        "base_parameter_manifest_sha256": source["base_parameter_manifest_sha256"],
        "base_profiles": source["base_profiles"],
        "p3_source_manifest_sha256": source["p3_source_manifest_sha256"],
        "p3_parameter_file": {"path": "p3-params.bin", "bytes": len(p3_raw),
                              "sha256": _sha(p3_raw)},
        "raw_parameter_bytes_changed": False,
        "chain_contract": CHAIN_CONTRACT,
        "parameter_compatibility": {CONTRACT_KIND: compatibility},
        "gates": {
            "pw2_signed40_range_proof_pass": True,
            "approved_raw_parameter_identity_pass": True,
            "candidate_runtime_admission_host_pass": True,
            "hardware_candidate_source_freeze": False,
            "rtl_simulation": False,
            "synthesis": False,
            "hardware_validation": False,
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    manifest_sha = sha256_file(manifest_path)
    contract = dict(compatibility)
    contract.update({
        "required_core_abi": CORE_ABI,
        "required_combined_manifest_sha256": manifest_sha,
    })
    validate_contract_object(contract, require_final_identity=True)
    admission = {
        "schema": ADMISSION_SCHEMA,
        "status": "PASS",
        "pass": True,
        "deployment_ready": False,
        "hardware_execution": False,
        "proof_receipt_sha256": proof_sha256,
        "contract": contract,
        "boundary": "Parameter admission is final; hardware and deployment gates remain pending.",
    }
    admission_path = output / "admission.json"
    admission_path.write_bytes(canonical_json_bytes(admission))
    admission_sha = sha256_file(admission_path)
    receipt = {
        "schema": "cnn-pipeline-v10.5-signed40-combined-parameter-receipt-v1",
        "status": "PASS_OFFLINE_PARAMETER_ADMISSION",
        "pass": True,
        "deployment_ready": False,
        "hardware_execution": False,
        "manifest_sha256": manifest_sha,
        "manifest_words_be32": [int(manifest_sha[index:index + 8], 16)
                                for index in range(0, 64, 8)],
        "admission_sha256": admission_sha,
        "proof_sha256": proof_sha256,
        "files": {
            "manifest.json": {"bytes": manifest_path.stat().st_size,
                              "sha256": manifest_sha},
            "admission.json": {"bytes": admission_path.stat().st_size,
                               "sha256": admission_sha},
            "p3-params.bin": {"bytes": len(p3_raw), "sha256": _sha(p3_raw)},
        },
    }
    (output / "receipt.json").write_bytes(canonical_json_bytes(receipt))
    return receipt


def load_v10_signed40_parameters(manifest_path, expected_manifest_sha256,
                                 admission_path, expected_admission_sha256,
                                 proof_path, expected_proof_sha256):
    manifest_path = pathlib.Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    digest = _checked_sha(expected_manifest_sha256, "A0005 combined manifest")
    if _sha(raw) != digest:
        raise ValueError("A0005 combined manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") !=
            "cnn-pipeline-v10.5-signed40-combined-parameter-manifest-v1" or
            manifest.get("status") != "PASS_OFFLINE_IDENTITY_ONLY" or
            manifest.get("deployment_ready") is not False or
            manifest.get("hardware_execution") is not False or
            manifest.get("core_abi") != CORE_ABI or
            manifest.get("software_identity") != SOFTWARE_IDENTITY or
            manifest.get("software_uapi") != SOFTWARE_UAPI or
            manifest.get("guard_caps") != GUARD_CAPS or
            manifest.get("chain_contract") != CHAIN_CONTRACT or
            manifest.get("raw_parameter_bytes_changed") is not False):
        raise ValueError("A0005 combined manifest contract mismatch")
    proof_path = pathlib.Path(proof_path).resolve()
    if sha256_file(proof_path) != _checked_sha(expected_proof_sha256, "range proof"):
        raise ValueError("PW2 signed40 proof SHA mismatch")
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    compatibility = compatibility_from_proof(proof, expected_proof_sha256)
    if manifest.get("parameter_compatibility") != {CONTRACT_KIND: compatibility}:
        raise ValueError("A0005 combined parameter compatibility mismatch")
    params_path = _safe_child(
        manifest_path.parent, manifest.get("p3_parameter_file", {}).get("path"),
        "P3 parameters")
    params = params_path.read_bytes()
    record = manifest["p3_parameter_file"]
    if (record.get("bytes") != len(params) or record.get("sha256") != _sha(params) or
            _sha(params) != P3_PARAMS_SHA256):
        raise ValueError("A0005 P3 parameter payload mismatch")
    candidate_identity = {
        "core_abi": CORE_ABI,
        "guard_caps": GUARD_CAPS,
        "combined_manifest_sha256": digest,
        "pw2_storage_contract": CONTRACT_KIND,
    }
    admission = load_admission_manifest(
        admission_path, expected_admission_sha256, proof_path,
        expected_proof_sha256, candidate_identity)
    return {
        "manifest_sha256": digest,
        "chain_manifest_sha256": digest,
        "parameter_manifest_words": tuple(
            int(digest[index:index + 8], 16) for index in range(0, 64, 8)),
        "p3_manifest_sha256": manifest["p3_source_manifest_sha256"],
        "params": params,
        "params_path": str(params_path),
        "contract": CHAIN_CONTRACT,
        "pw2_signed40_admission": admission,
        "evidence": manifest["gates"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--source-manifest-sha256", required=True)
    parser.add_argument("--p3-params", required=True)
    parser.add_argument("--proof", required=True)
    parser.add_argument("--proof-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_a0005_combined(
        args.source_manifest, args.source_manifest_sha256,
        args.p3_params, args.proof, args.proof_sha256, args.output),
        sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "CHAIN_CONTRACT", "CORE_ABI", "GUARD_CAPS", "PW2_SIGNED40_CAP_BIT",
    "SOFTWARE_IDENTITY", "build_a0005_combined", "compatibility_from_proof",
    "load_v10_signed40_parameters",
]
