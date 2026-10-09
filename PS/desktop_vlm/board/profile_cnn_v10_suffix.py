#!/usr/bin/env python3
"""Collect a short target ORT profile for the frozen V10 suffix only.

The runner writes the ORT Chrome trace and optimized graph when the matching
environment variables are set.  This script keeps the diagnostic separate
from formal timing and verifies every returned feature against its frozen
float32 reference.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import pathlib
import time

import numpy as np

try:
    from cnn_v10_ps_clients import OptimizedOrtPartitionClient
except ImportError:
    from .cnn_v10_ps_clients import OptimizedOrtPartitionClient


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _load_array(path, spec):
    raw = pathlib.Path(path).read_bytes()
    if len(raw) != spec["bytes"]:
        raise ValueError("%s byte count mismatch" % path)
    value = np.frombuffer(raw, dtype="<f4").copy().reshape(tuple(spec["shape"]))
    if not np.isfinite(value).all():
        raise ValueError("%s contains a non-finite value" % path)
    return value, _sha256_bytes(raw)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--expected", action="append", required=True)
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--profile-prefix", required=True)
    parser.add_argument("--optimized-model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if len(args.input) != 2 or len(args.expected) != 2:
        parser.error("exactly two distinct inputs and references are required")
    if args.threads != 3 or args.iterations not in (2, 3, 4, 5):
        parser.error("this diagnostic requires threads=3 and 2..5 iterations")
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    manifest_raw = pathlib.Path(args.manifest).read_bytes()
    if _sha256_bytes(manifest_raw) != args.expected_manifest_sha256:
        raise ValueError("model manifest SHA mismatch")
    manifest = json.loads(manifest_raw.decode("utf-8"))
    contract = manifest["models"]["suffix"]
    inputs = [_load_array(path, contract["inputs"][0]) for path in args.input]
    references = [pathlib.Path(path).read_bytes() for path in args.expected]
    if inputs[0][1] == inputs[1][1]:
        raise ValueError("suffix inputs must be distinct")
    expected_bytes = contract["outputs"][0]["bytes"]
    if any(len(value) != expected_bytes for value in references):
        raise ValueError("suffix reference byte count mismatch")
    prefix = pathlib.Path(args.profile_prefix)
    before = set(prefix.parent.glob(prefix.name + "*.json"))
    previous_profile = os.environ.get("ORT_PARTITION_PROFILE_PREFIX")
    previous_optimized = os.environ.get("ORT_PARTITION_OPTIMIZED_MODEL")
    os.environ["ORT_PARTITION_PROFILE_PREFIX"] = str(prefix)
    os.environ["ORT_PARTITION_OPTIMIZED_MODEL"] = str(args.optimized_model)
    client = None
    samples = []
    try:
        client = OptimizedOrtPartitionClient(
            [args.runner, "--stream", str(pathlib.Path(args.model_root) /
             contract["path"]), str(args.threads)], contract,
            threads=args.threads, request_timeout=120.0,
            allow_spinning=0, preallocate_outputs=0)
        for index in range(args.iterations):
            case = index % 2
            started = time.perf_counter()
            values, run_ms = client.infer([inputs[case][0]])
            wall_ms = (time.perf_counter() - started) * 1000.0
            raw = values[contract["outputs"][0]["name"]].tobytes(order="C")
            samples.append({
                "iteration": index, "case": case, "run_ms": run_ms,
                "call_wall_ms": wall_ms, "output_sha256": _sha256_bytes(raw),
                "expected_sha256": _sha256_bytes(references[case]),
                "byte_exact": raw == references[case],
            })
    finally:
        if client is not None:
            client.close()
        if previous_profile is None:
            os.environ.pop("ORT_PARTITION_PROFILE_PREFIX", None)
        else:
            os.environ["ORT_PARTITION_PROFILE_PREFIX"] = previous_profile
        if previous_optimized is None:
            os.environ.pop("ORT_PARTITION_OPTIMIZED_MODEL", None)
        else:
            os.environ["ORT_PARTITION_OPTIMIZED_MODEL"] = previous_optimized
    created = sorted(set(prefix.parent.glob(prefix.name + "*.json")) - before)
    if len(created) != 1 or not pathlib.Path(args.optimized_model).is_file():
        raise RuntimeError("ORT profile or optimized model was not created exactly once")
    if not all(item["byte_exact"] for item in samples):
        raise RuntimeError("profiled suffix output differs from frozen FP32 reference")
    receipt = {
        "schema": "cnn-v10.1-suffix-ort-profile-diagnostic-v1",
        "status": "PASS_PROFILE_DIAGNOSTIC_SUFFIX_OUTPUT_BYTE_EXACT",
        "formal_timing": False, "threads": args.threads,
        "iterations": args.iterations, "allow_spinning": 0,
        "preallocate_outputs": 0,
        "model_manifest_sha256": args.expected_manifest_sha256,
        "model_sha256": contract["sha256"], "samples": samples,
        "profile_file": str(created[0]),
        "profile_sha256": _sha256_bytes(created[0].read_bytes()),
        "optimized_model": str(pathlib.Path(args.optimized_model)),
        "optimized_model_sha256": _sha256_bytes(
            pathlib.Path(args.optimized_model).read_bytes()),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.write_bytes(raw)
    print(json.dumps({"status": receipt["status"],
                      "receipt_sha256": _sha256_bytes(raw)}, sort_keys=True))


if __name__ == "__main__":
    main()
