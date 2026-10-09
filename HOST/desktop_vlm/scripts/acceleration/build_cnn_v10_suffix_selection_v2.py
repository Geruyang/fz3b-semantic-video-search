#!/usr/bin/env python3
"""Freeze the suffix candidate with target ORT kernel-class evidence."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib
import shutil


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy(source, destination):
    shutil.copyfile(str(source), str(destination))
    return {"path": destination.name, "bytes": destination.stat().st_size,
            "sha256": _sha(destination)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-package", required=True)
    parser.add_argument("--target-profile", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    old = pathlib.Path(args.v1_package).resolve()
    profile = pathlib.Path(args.target_profile).resolve()
    output = pathlib.Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    output.mkdir(parents=True)
    old_manifest_path = old / "selection-manifest.json"
    old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    if (old_manifest.get("schema") != "cnn-v10.1-suffix-w8a8-selection-v1" or
            old_manifest.get("status") != "PASS"):
        raise ValueError("source selection manifest mismatch")
    candidate = _copy(old / old_manifest["candidate"]["path"],
                      output / "suffix-w8a8-qdq-candidate.onnx")
    candidate["precision"] = old_manifest["candidate"]["precision"]
    evidence = {}
    for name, record in old_manifest["evidence"].items():
        source = old / record["path"]
        if source.stat().st_size != record["bytes"] or _sha(source) != record["sha256"]:
            raise ValueError("v1 evidence identity mismatch: %s" % name)
        evidence[name] = _copy(source, output / ("v1-" + source.name))
    profile_files = {
        "target_profile_receipt": "profile-receipt.json",
        "target_profile_wrapper_receipt": "wrapper-receipt.json",
        "target_profile_analysis": "analysis.json",
        "target_kernel_classification": "kernel-classification.json",
        "target_optimized_model": "suffix-candidate-optimized.onnx",
    }
    for name, filename in profile_files.items():
        evidence[name] = _copy(profile / filename, output / filename)
    profile_receipt = json.loads(
        (profile / "profile-receipt.json").read_text(encoding="utf-8"))
    classification = json.loads(
        (profile / "kernel-classification.json").read_text(encoding="utf-8"))
    if (profile_receipt.get("status") !=
            "PASS_CANDIDATE_PROFILE_AND_ENGINEERING_ERROR_GATE" or
            profile_receipt.get("candidate_sha256") != candidate["sha256"] or
            classification.get("status") !=
            "PASS_TARGET_ORT_INTEGER_KERNELS_CONFIRMED" or
            classification.get("candidate_sha256") != candidate["sha256"] or
            classification.get("integer_kernel_count") != 13 or
            classification.get("qlinear_conv_count") != 7 or
            classification.get("qlinear_matmul_count") != 6):
        raise ValueError("target ORT profile/kernel evidence mismatch")
    manifest = {
        "schema": "cnn-v10.1-suffix-w8a8-selection-v2",
        "status": "PASS",
        "source_model_sha256": old_manifest["source_model_sha256"],
        "candidate": candidate,
        "evidence": evidence,
        "target_runtime": "onnxruntime-1.16.3-aarch64-cpu",
        "target_integer_kernel_contract": {
            "provider": "CPUExecutionProvider", "kernel_count": 13,
            "qlinear_conv_count": 7, "qlinear_matmul_count": 6,
        },
        "engineering_gate": old_manifest["engineering_gate"],
        "target_timing": old_manifest["target_timing"],
    }
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    destination = output / "selection-manifest.json"
    destination.write_bytes(raw)
    print(json.dumps({"status": "PASS", "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                      "candidate_sha256": candidate["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
