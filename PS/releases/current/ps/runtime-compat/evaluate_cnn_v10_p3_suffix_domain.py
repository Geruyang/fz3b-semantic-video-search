#!/usr/bin/env python3
"""Evaluate P3-domain suffix candidates on captured real chain boundaries.

This is a numerical engineering gate.  It does not measure full-model FPS and
does not operate PL or a kernel driver.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import math
import os
import pathlib
import statistics

import numpy as np

try:
    from cnn_v10_ps_shm_clients import ShmOrtPartitionClient
except ImportError:
    from .cnn_v10_ps_shm_clients import ShmOrtPartitionClient


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("%s must be lowercase SHA256" % label)
    return value


def _child(root, record, label):
    if not isinstance(record, dict):
        raise ValueError("%s record missing" % label)
    relative = record.get("path")
    normalized = relative.replace("\\", "/") if isinstance(relative, str) else ""
    parts = normalized.split("/")
    if (not isinstance(relative, str) or not relative or "\\" in relative or
            pathlib.PurePosixPath(normalized).is_absolute() or
            ":" in parts[0] or any(part in ("", ".", "..") for part in parts)):
        raise ValueError("%s path invalid" % label)
    root = root.resolve()
    path = (root / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(root), str(path))) != str(root):
        raise ValueError("%s path escapes package" % label)
    raw = path.read_bytes()
    if (record.get("bytes") != len(raw) or
            _checked_sha(record.get("sha256"), label + " SHA") != _sha(raw)):
        raise ValueError("%s extent/SHA mismatch" % label)
    return path, raw


def _metrics(value, reference):
    lhs = np.asarray(value, dtype=np.float64).reshape(-1)
    rhs = np.asarray(reference, dtype=np.float64).reshape(-1)
    delta = lhs - rhs
    lhs_norm, rhs_norm = float(np.linalg.norm(lhs)), float(np.linalg.norm(rhs))
    return {
        "cosine": float(np.dot(lhs, rhs) / (lhs_norm * rhs_norm))
        if lhs_norm and rhs_norm else 0.0,
        "relative_l2": float(np.linalg.norm(delta) / max(rhs_norm, np.finfo(np.float64).tiny)),
        "max_abs": float(np.max(np.abs(delta))),
    }


def _load_capture(path, expected_sha):
    path = pathlib.Path(path)
    raw = path.read_bytes()
    if _sha(raw) != _checked_sha(expected_sha, "capture manifest"):
        raise ValueError("capture manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") != "cnn-v10.2-p3-suffix-input-capture-v1" or
            manifest.get("status") != "CAPTURE_COMPLETE" or
            manifest.get("performance_valid") is not False or
            manifest.get("first_occurrence_order_preserved") is not True or
            manifest.get("distinct_count") != 2 or len(manifest.get("records", [])) != 2):
        raise ValueError("capture manifest contract mismatch")
    values = []
    for index, record in enumerate(manifest["records"]):
        child, data = _child(path.parent, record, "captured input")
        if (record.get("capture_index") != index or
                record.get("first_infer_call") != index or
                record.get("shape") != [1, 256, 16, 16] or
                record.get("dtype") != "<f4" or len(data) != 262144):
            raise ValueError("captured input order/shape mismatch")
        value = np.frombuffer(data, dtype="<f4").copy().reshape(1, 256, 16, 16)
        if not np.isfinite(value).all():
            raise ValueError("captured input contains non-finite values")
        values.append((child, value, record["sha256"]))
    if values[0][2] == values[1][2]:
        raise ValueError("captured inputs are not distinct")
    return manifest, values


def _load_candidate(spec, expected_spec, source_sha):
    if "=" not in spec or "=" not in expected_spec:
        raise ValueError("candidate specifications must be label=value")
    label, path_value = spec.split("=", 1)
    expected_label, expected_sha = expected_spec.split("=", 1)
    if not label or label != expected_label:
        raise ValueError("candidate label/SHA labels differ")
    path = pathlib.Path(path_value)
    raw = path.read_bytes()
    if _sha(raw) != _checked_sha(expected_sha, label + " manifest"):
        raise ValueError("%s selection manifest SHA mismatch" % label)
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") != "cnn-v10.1-suffix-w8a8-selection-v2" or
            manifest.get("status") != "PASS" or
            manifest.get("source_model_sha256") != source_sha or
            manifest.get("engineering_gate", {}).get("pass") is not True):
        raise ValueError("%s selection contract mismatch" % label)
    model, unused_raw = _child(path.parent, manifest.get("candidate"), label + " candidate")
    return label, path, manifest, model


def _load_capture_benchmark_result(path, expected_sha, capture_manifest_sha,
                                   image_shas, reference_shas, runner_sha):
    path = pathlib.Path(path)
    raw = path.read_bytes()
    if _sha(raw) != _checked_sha(expected_sha, "capture benchmark result"):
        raise ValueError("capture benchmark result SHA mismatch")
    result = json.loads(raw.decode("utf-8"))
    summary = result.get("suffix_input_capture")
    if (result.get("status") != "ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN" or
            result.get("active_quantized_partitions") != ["n1_pl"] or
            result.get("performance_valid") is not False or
            not isinstance(summary, dict) or
            summary.get("manifest_sha256") != capture_manifest_sha or
            result.get("input_tensor_sha256") != image_shas or
            result.get("expected_feature_sha256") != reference_shas or
            result.get("runner_sha256") != runner_sha or
            result.get("runner_sha256_after") != runner_sha):
        raise ValueError("capture benchmark/result/domain identity mismatch")
    return result, raw


def _run_model(runner, model, inputs, references, iterations, threads,
               min_cosine, max_relative_l2):
    contract = {
        "inputs": [{"name": "/image_encoder/model/network.4/network.4.19/Add_output_0",
                    "shape": [1, 256, 16, 16], "dtype": "<f4", "bytes": 262144}],
        "outputs": [{"name": "features", "shape": [1, 512],
                     "dtype": "<f4", "bytes": 2048}],
    }
    client = ShmOrtPartitionClient([runner, str(model), str(threads)], contract,
                                   threads=threads, request_timeout=120.0)
    header = dict(client.header)
    if (header.get("kind") != "ready" or header.get("protocol") != 3 or
            header.get("ort_version") != "1.16.3" or
            header.get("threads") != threads or header.get("api_version") != 16):
        client.close()
        raise ValueError("target runner header/runtime contract mismatch")
    rows = []
    try:
        for iteration in range(iterations):
            for case, unused_path, value, input_sha in (
                    (0, inputs[0][0], inputs[0][1], inputs[0][2]),
                    (1, inputs[1][0], inputs[1][1], inputs[1][2])):
                outputs, run_ms = client.infer([value])
                feature = np.asarray(outputs["features"], dtype="<f4").reshape(512)
                metric = _metrics(feature, references[case])
                rows.append({"iteration": iteration, "case": case,
                             "captured_input_sha256": input_sha,
                             "output_sha256": _sha(feature.tobytes()),
                             "run_ms": float(run_ms), "metrics": metric})
    finally:
        client.close()
    deterministic = all(len(set(row["output_sha256"] for row in rows
                                if row["case"] == case)) == 1 for case in (0, 1))
    passed = deterministic and all(
        row["metrics"]["cosine"] >= min_cosine and
        row["metrics"]["relative_l2"] <= max_relative_l2 for row in rows)
    return {"pass": passed, "deterministic": deterministic,
            "client_header": header, "rows": rows,
            "min_cosine": min(row["metrics"]["cosine"] for row in rows),
            "max_relative_l2": max(row["metrics"]["relative_l2"] for row in rows),
            "run_mean_ms": statistics.mean(row["run_ms"] for row in rows)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", required=True)
    parser.add_argument("--source-model", required=True)
    parser.add_argument("--capture-manifest", required=True)
    parser.add_argument("--expected-capture-manifest-sha256", required=True)
    parser.add_argument("--capture-benchmark-result", required=True)
    parser.add_argument("--expected-capture-benchmark-result-sha256", required=True)
    parser.add_argument("--source-image-sha256", action="append", required=True)
    parser.add_argument("--reference-feature", action="append", required=True)
    parser.add_argument("--reference-feature-sha256", action="append", required=True)
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--expected-candidate-manifest-sha256", action="append", default=[])
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--min-cosine", type=float, default=.999)
    parser.add_argument("--max-relative-l2", type=float, default=.05)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if (len(args.source_image_sha256) != 2 or len(args.reference_feature) != 2 or
            len(args.reference_feature_sha256) != 2 or
            len(args.candidate) != len(args.expected_candidate_manifest_sha256)):
        parser.error("two image/reference identities and paired candidate specs required")
    if args.threads != 3 or args.iterations < 1:
        parser.error("target gate requires threads=3 and positive iterations")
    if (not math.isfinite(args.min_cosine) or not math.isfinite(args.max_relative_l2) or
            args.max_relative_l2 < 0):
        parser.error("invalid engineering thresholds")
    runner = pathlib.Path(args.runner)
    runner_sha_before = _sha(runner.read_bytes())
    source_model = pathlib.Path(args.source_model)
    source_raw = source_model.read_bytes()
    source_sha = _sha(source_raw)
    capture, inputs = _load_capture(args.capture_manifest,
                                    args.expected_capture_manifest_sha256)
    image_shas = [_checked_sha(value, "source image") for value in args.source_image_sha256]
    if image_shas[0] == image_shas[1]:
        raise ValueError("source images must be distinct")
    references = []
    for path_value, expected in zip(args.reference_feature,
                                    args.reference_feature_sha256):
        data = pathlib.Path(path_value).read_bytes()
        if _sha(data) != _checked_sha(expected, "reference feature") or len(data) != 2048:
            raise ValueError("reference feature identity/extent mismatch")
        value = np.frombuffer(data, dtype="<f4").copy().reshape(512)
        if not np.isfinite(value).all():
            raise ValueError("reference feature contains non-finite values")
        references.append(value)
    capture_result, capture_result_raw = _load_capture_benchmark_result(
        args.capture_benchmark_result,
        args.expected_capture_benchmark_result_sha256,
        args.expected_capture_manifest_sha256,
        image_shas, args.reference_feature_sha256, runner_sha_before)
    candidates = [_load_candidate(spec, expected, source_sha)
                  for spec, expected in zip(args.candidate,
                                            args.expected_candidate_manifest_sha256)]
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    results = {"p3_only_fp32_suffix": _run_model(
        args.runner, source_model, inputs, references, args.iterations,
        args.threads, args.min_cosine, args.max_relative_l2)}
    candidate_identity = {}
    for label, manifest_path, manifest, model in candidates:
        if label in results:
            raise ValueError("duplicate candidate label")
        results[label] = _run_model(args.runner, model, inputs, references,
                                    args.iterations, args.threads,
                                    args.min_cosine, args.max_relative_l2)
        candidate_identity[label] = {
            "selection_manifest_path": str(manifest_path),
            "selection_manifest_sha256": _sha(manifest_path.read_bytes()),
            "candidate_sha256": manifest["candidate"]["sha256"],
            "target_integer_kernel_contract": manifest["target_integer_kernel_contract"],
        }
    report = {
        "schema": "cnn-v10.2-p3-domain-suffix-candidate-gate-v1",
        "status": ("PASS_P3_ONLY_AND_ALL_SUFFIX_CANDIDATES" if
                   all(value["pass"] for value in results.values()) else
                   "COMPLETE_WITH_ENGINEERING_GATE_FAILURES"),
        "performance_valid": False,
        "runtime": "derived from validated client headers", "threads": args.threads,
        "iterations": args.iterations,
        "thresholds": {"min_cosine": args.min_cosine,
                       "max_relative_l2": args.max_relative_l2},
        "source_model_sha256": source_sha,
        "capture_manifest_sha256": _sha(pathlib.Path(args.capture_manifest).read_bytes()),
        "capture_benchmark_result_sha256": _sha(capture_result_raw),
        "capture_infer_calls": capture["infer_calls"],
        "runner_sha256_before": runner_sha_before,
        "ordered_domain_bindings": [{
            "capture_index": index,
            "source_image_sha256": image_shas[index],
            "captured_suffix_input_sha256": inputs[index][2],
            "reference_feature_sha256": args.reference_feature_sha256[index],
        } for index in range(2)],
        "candidate_identity": candidate_identity,
        "results": results,
        "scope": "P3-domain full-feature engineering gate only; not FPS, accuracy, or hardware timing evidence",
    }
    runner_sha_after = _sha(runner.read_bytes())
    if runner_sha_after != runner_sha_before:
        raise RuntimeError("runner changed during P3 suffix-domain evaluation")
    report["runner_sha256_after"] = runner_sha_after
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.write_bytes(raw)
    print(json.dumps({"status": report["status"],
                      "receipt_sha256": _sha(raw),
                      "passing": sorted(name for name, value in results.items()
                                        if value["pass"]),
                      "failing": sorted(name for name, value in results.items()
                                        if not value["pass"])}, sort_keys=True))
    return 0 if results["p3_only_fp32_suffix"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
