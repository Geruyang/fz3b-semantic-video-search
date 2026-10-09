"""Build and validate the combined ABI10.2 P3-chain parameter identity.

The manifest SHA256 is the eight-word big-endian driver guard identity. The
frozen ABI10.1 profile 0..2 blobs remain supplied by the release bundle; this
manifest binds their hashes together with the P3 profile-3 raw parameter blob.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import pathlib
import shutil

try:
    from cnn_pipeline_v10_bundle import load_v10_release_bundle
except ImportError:
    from .cnn_pipeline_v10_bundle import load_v10_release_bundle


P3_MANIFEST_SHA256 = "47cb1bc9c4232fb9dee6a0b46fd29f96859bac253ae7bd6ec1fbdd37c1a5533a"
P3_PARAMS_SHA256 = "f6ece07c73678835a6d25dd13b5ecafa7f106f03d279eea7b2b51a1898cc09ce"
BASE_RELEASE_MANIFEST_SHA256 = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
BASE_PARAMETER_IDENTITY_SHA256 = "83df8803b7a8eb08795c6c19d89538637f850df9044c407b90814d725f0079c4"
CHAIN_CONTRACT = {
    "profiles": [2, 3, 0], "arena_words": 69632, "word_bits": 128,
    "p3": {"profile": 3, "blocks": 1, "flags": 0, "params_words": 11280,
           "input_offset_words": 0, "input_words": 32768,
           "intermediate_offset_words": 32768, "intermediate_words": 16384,
           "output_offset_words": 0, "output_words": 16384,
           "slot_words": 32768},
    "p0_base_offset_words": 0,
}
P3_ACTIVATION_SCALES = {
    "input": 8.370727368858105e-05,
    "output": 9.687628574169352e-05,
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(c not in "0123456789abcdef" for c in value)):
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


def _record(root, record, label):
    if not isinstance(record, dict):
        raise ValueError("%s record is missing" % label)
    path = _safe_child(root, record.get("path"), label)
    raw = path.read_bytes()
    if (isinstance(record.get("bytes"), bool) or record.get("bytes") != len(raw) or
            _checked_sha(record.get("sha256"), label + " SHA") != _sha(raw)):
        raise ValueError("%s extent or SHA mismatch" % label)
    return path, raw


def build_combined_manifest(base_bundle_root, base_manifest_sha256,
                            p3_manifest_path, p3_manifest_sha256, output_root):
    """Bind old profiles 0..2 and P3 bytes, then write a self-contained package."""
    base = load_v10_release_bundle(base_bundle_root, base_manifest_sha256)
    if (base_manifest_sha256 != BASE_RELEASE_MANIFEST_SHA256 or
            base["manifest"].get("parameter_identity", {}).get("sha256") !=
            BASE_PARAMETER_IDENTITY_SHA256):
        raise ValueError("base ABI10.1 old3 parameter identity is not the frozen release")
    p3_path = pathlib.Path(p3_manifest_path).resolve()
    p3_raw = p3_path.read_bytes()
    if _sha(p3_raw) != _checked_sha(p3_manifest_sha256, "P3 manifest"):
        raise ValueError("P3 manifest SHA mismatch")
    if p3_manifest_sha256 != P3_MANIFEST_SHA256:
        raise ValueError("P3 manifest is not the frozen corrected 002 artifact")
    p3 = json.loads(p3_raw.decode("utf-8"))
    p3_identity = p3.get("runtime_identity", {})
    if (p3.get("status") != "PASS" or
            p3_identity.get("profile") != 3 or p3_identity.get("blocks") != 1 or
            p3_identity.get("parameter_words") != 11280 or
            p3_identity.get("slot_words") != 32768 or
            p3_identity.get("slot_bytes") != 524288 or
            p3_identity.get("arena_words") != 69632 or
            p3_identity.get("arena_bytes") != 1114112 or
            p3_identity.get("dw_intermediate", {}).get("output_valid_words") != 16384 or
            p3_identity.get("dw_intermediate", {}).get("output_valid_bytes") != 262144 or
            p3_identity.get("final_output", {}).get("slot") != 0 or
            p3_identity.get("final_output", {}).get("output_valid_words") != 16384 or
            p3_identity.get("final_output", {}).get("output_valid_bytes") != 262144 or
            p3.get("gates", {}).get("three_image_full_model_pass") is not True or
            p3.get("gates", {}).get("exact_code_match_to_prior_full_w16_oracle") is not True):
        raise ValueError("P3 candidate manifest status or profile mismatch")
    p3_params_path, p3_params_raw = _record(
        p3_path.parent, p3.get("parameters"), "P3 raw parameters")
    if (len(p3_params_raw) != 11280 * 16 or
            _sha(p3_params_raw) != P3_PARAMS_SHA256):
        raise ValueError("P3 raw parameter identity mismatch")

    output_root = pathlib.Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    parameter_path = output_root / "p3-params.bin"
    shutil.copyfile(str(p3_params_path), str(parameter_path))
    profiles = {}
    for profile in (0, 1, 2):
        value = base["parameter_contract"]["profiles"][profile]
        profiles[str(profile)] = {
            "blocks": (12, 20, 4)[profile],
            "params_bytes": len(value["params"]),
            "params_sha256": value["params_sha256"],
            "input_scale": value["input_scale"],
            "output_scale": value["output_scale"],
        }
    if (profiles["2"]["output_scale"] != P3_ACTIVATION_SCALES["input"] or
            profiles["0"]["input_scale"] != P3_ACTIVATION_SCALES["output"]):
        raise ValueError("P2/P3/P0 A16 scale boundaries are not continuous")
    manifest = {
        "schema": "cnn-pipeline-v10.1-p3-combined-parameter-manifest-v1",
        "status": "PASS",
        "identity_role": "combined-manifest-sha256-as-eight-big-endian-u32-words",
        "base_release_manifest_sha256": base["manifest_sha256"],
        "base_parameter_manifest_sha256": base["manifest"]["parameter_identity"]["sha256"],
        "base_profiles": profiles,
        "p3_manifest_sha256": p3_manifest_sha256,
        "p3_candidate": p3.get("candidate"),
        "p3_parameter_file": {"path": "p3-params.bin", "bytes": len(p3_params_raw),
                               "sha256": _sha(p3_params_raw)},
        "p3_runtime_identity": p3["runtime_identity"],
        "chain_contract": CHAIN_CONTRACT,
        "evidence": {"p3_full_model_three_image_gate": p3["gates"]["three_image_full_model_pass"],
                     "p3_exact_code_match_to_independent_oracle": p3["gates"]["exact_code_match_to_prior_full_w16_oracle"],
                     "target_execution": False},
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                             encoding="utf-8")
    manifest_raw = manifest_path.read_bytes()
    receipt = {"schema": "cnn-pipeline-v10.1-p3-combined-parameter-receipt-v1",
               "manifest_sha256": _sha(manifest_raw),
               "manifest_words_be32": [int(_sha(manifest_raw)[i:i+8], 16)
                                        for i in range(0, 64, 8)],
               "files": {"manifest.json": {"bytes": len(manifest_raw), "sha256": _sha(manifest_raw)},
                         "p3-params.bin": {"bytes": len(p3_params_raw), "sha256": _sha(p3_params_raw)}}}
    (output_root / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                                                encoding="utf-8")
    return manifest


def load_v10_p3_parameters(path, expected_sha256, base_contract):
    """Fail-closed combined manifest loader; base profiles stay in base_contract."""
    manifest_path = pathlib.Path(path).resolve()
    raw = manifest_path.read_bytes()
    combined_sha = _checked_sha(expected_sha256, "combined manifest")
    if _sha(raw) != combined_sha:
        raise ValueError("combined P3 parameter manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    try:
        from cnn_pipeline_v10_chain_deployment import CHAIN_CONTRACT as DEPLOYMENT_CHAIN_CONTRACT
    except ImportError:
        from .cnn_pipeline_v10_chain_deployment import CHAIN_CONTRACT as DEPLOYMENT_CHAIN_CONTRACT
    if (manifest.get("schema") != "cnn-pipeline-v10.1-p3-combined-parameter-manifest-v1" or
            manifest.get("status") != "PASS" or
            manifest.get("identity_role") != "combined-manifest-sha256-as-eight-big-endian-u32-words" or
            manifest.get("chain_contract") != CHAIN_CONTRACT or
            manifest.get("chain_contract") != DEPLOYMENT_CHAIN_CONTRACT):
        raise ValueError("combined P3 parameter manifest contract mismatch")
    if (not isinstance(base_contract, dict) or
            manifest.get("base_release_manifest_sha256") != BASE_RELEASE_MANIFEST_SHA256 or
            manifest.get("base_parameter_manifest_sha256") != BASE_PARAMETER_IDENTITY_SHA256 or
            base_contract.get("manifest_sha256") != manifest.get("base_release_manifest_sha256") or
            set(base_contract.get("profiles", {})) != {0, 1, 2}):
        raise ValueError("frozen ABI10.1 base profile contract mismatch")
    for profile in (0, 1, 2):
        item = manifest["base_profiles"][str(profile)]
        record = base_contract["profiles"][profile]
        payload = bytes(record["params"])
        if (len(payload) != item["params_bytes"] or _sha(payload) != item["params_sha256"] or
                record.get("params_sha256") != item["params_sha256"] or
                float(record.get("input_scale")) != item["input_scale"] or
                float(record.get("output_scale")) != item["output_scale"]):
            raise ValueError("frozen base profile %d differs from combined identity" % profile)
    if (base_contract["profiles"][2]["output_scale"] != P3_ACTIVATION_SCALES["input"] or
            base_contract["profiles"][0]["input_scale"] != P3_ACTIVATION_SCALES["output"]):
        raise ValueError("P2/P3/P0 A16 scale boundaries are not continuous")
    params_path, params = _record(manifest_path.parent, manifest.get("p3_parameter_file"),
                                  "combined P3 parameters")
    if len(params) != 11280 * 16:
        raise ValueError("combined P3 parameter extent mismatch")
    p3_sha = _checked_sha(manifest.get("p3_manifest_sha256"), "P3 source manifest")
    if (p3_sha != P3_MANIFEST_SHA256 or _sha(params) != P3_PARAMS_SHA256 or
            manifest.get("p3_parameter_file", {}).get("sha256") != P3_PARAMS_SHA256):
        raise ValueError("combined P3 parameter source identity mismatch")
    words = tuple(int(combined_sha[i:i+8], 16) for i in range(0, 64, 8))
    return {"manifest_sha256": combined_sha,
            "chain_manifest_sha256": combined_sha,
            "parameter_manifest_words": words,
            "p3_manifest_sha256": p3_sha,
            "params": params,
            "params_path": str(params_path),
            "contract": CHAIN_CONTRACT,
            "evidence": manifest.get("evidence", {})}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-bundle-root", required=True)
    parser.add_argument("--base-manifest-sha256", required=True)
    parser.add_argument("--p3-manifest", required=True)
    parser.add_argument("--p3-manifest-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    manifest = build_combined_manifest(args.base_bundle_root,
        args.base_manifest_sha256, args.p3_manifest, args.p3_manifest_sha256,
        args.output)
    raw = (pathlib.Path(args.output) / "manifest.json").read_bytes()
    print(json.dumps({"status": manifest["status"], "manifest_sha256": _sha(raw),
                      "parameter_manifest_words_be32": [int(_sha(raw)[i:i+8], 16)
                                                         for i in range(0, 64, 8)]}, indent=2))


if __name__ == "__main__":
    main()


__all__ = ["CHAIN_CONTRACT", "build_combined_manifest", "load_v10_p3_parameters"]
