#!/usr/bin/env python3
"""Freeze a suffix candidate and its target ORT 1.16.3 evidence."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib
import shutil


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def copy_record(source, destination):
    shutil.copyfile(str(source), str(destination))
    return {"path": destination.name, "bytes": destination.stat().st_size,
            "sha256": sha(destination)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--host-receipt", required=True)
    parser.add_argument("--target-evidence", required=True)
    parser.add_argument("--precision", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = pathlib.Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    output.mkdir(parents=True)
    candidate = pathlib.Path(args.candidate).resolve()
    target = pathlib.Path(args.target_evidence).resolve()
    source_receipt = pathlib.Path(args.host_receipt).resolve()
    candidate_record = copy_record(candidate, output / "suffix-w8a8-qdq-candidate.onnx")
    candidate_record["precision"] = args.precision
    evidence = {
        "host_receipt": copy_record(source_receipt, output / "host-receipt.json"),
        "target_result": copy_record(target / "target-result.json", output / "target-result.json"),
        "target_wrapper_receipt": copy_record(target / "wrapper-receipt.json", output / "target-wrapper-receipt.json"),
        "target_profile_receipt": copy_record(target / "profile-receipt.json", output / "profile-receipt.json"),
        "target_profile_wrapper_receipt": copy_record(target / "wrapper-receipt.json", output / "profile-wrapper-receipt.json"),
        "target_profile_analysis": copy_record(target / "analysis.json", output / "analysis.json"),
        "target_kernel_classification": copy_record(target / "kernel-classification.json", output / "kernel-classification.json"),
        "target_optimized_model": copy_record(target / "suffix-candidate-optimized.onnx", output / "suffix-candidate-optimized.onnx"),
        "host_profile": copy_record(source_receipt, output / "host-profile-evidence.json"),
    }
    host = json.loads(source_receipt.read_text(encoding="utf-8"))
    result = json.loads((target / "target-result.json").read_text(encoding="utf-8"))
    profile = json.loads((target / "profile-receipt.json").read_text(encoding="utf-8"))
    classification = json.loads((target / "kernel-classification.json").read_text(encoding="utf-8"))
    candidate_sha = candidate_record["sha256"]
    if ("PASS" not in str(host.get("status", "")) or
            result.get("status") != "PASS_TARGET_ORT116_ENGINEERING_GATE" or
            result.get("candidate_gate") is not True or
            result.get("candidate_sha256") != candidate_sha or
            profile.get("status") != "PASS_CANDIDATE_PROFILE_AND_ENGINEERING_ERROR_GATE" or
            profile.get("candidate_sha256") != candidate_sha or
            classification.get("status") != "PASS_TARGET_ORT_INTEGER_KERNELS_CONFIRMED" or
            classification.get("candidate_sha256") != candidate_sha):
        raise ValueError("host/target evidence mismatch")
    quality = host.get("quality_gate", {})
    if quality.get("pass") is not True:
        raise ValueError("host quality gate failed")
    manifest = {
        "schema": "cnn-v10.1-suffix-w8a8-selection-v2", "status": "PASS",
        "source_model_sha256": result["source_model_sha256"],
        "candidate": candidate_record, "evidence": evidence,
        "target_runtime": "onnxruntime-1.16.3-aarch64-cpu",
        "target_integer_kernel_contract": {
            "provider": "CPUExecutionProvider",
            "kernel_count": classification["integer_kernel_count"],
            "qlinear_conv_count": classification["qlinear_conv_count"],
            "qlinear_matmul_count": classification["qlinear_matmul_count"],
        },
        "engineering_gate": {
            "fixture_count": quality.get("fixture_count"),
            "min_cosine": 0.999, "max_relative_l2": 0.05, "pass": True,
            "original_domain_min_cosine": quality.get("min_cosine"),
            "original_domain_max_relative_l2": quality.get("max_relative_l2"),
        },
        "target_timing": {
            "threads": result["threads"], "warmup_rounds": result["warmup_rounds"],
            "measured_rounds": result["measured_rounds"],
            "fp32_run_mean_ms": result["results"]["fp32"]["run_ms"]["mean"],
            "candidate_run_mean_ms": result["results"]["candidate"]["run_ms"]["mean"],
        },
        "domain_status": {"original_domain": "PASS", "p3_domain": "UNTESTED_REAL_CAPTURE_REQUIRED"},
    }
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output / "selection-manifest.json").write_bytes(raw)
    print(json.dumps({"status": "PASS", "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                      "candidate_sha256": candidate_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
