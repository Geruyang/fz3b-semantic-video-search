#!/usr/bin/env python3
"""Collect a short target ORT profile for an approximate suffix candidate.

The candidate is measured against the frozen FP32 suffix references.  This is
diagnostic evidence for the execution provider and optimized graph; it is not
used as a throughput benchmark or an accuracy claim.
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


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _load_f32(path, spec):
    raw = pathlib.Path(path).read_bytes()
    if len(raw) != int(spec["bytes"]):
        raise ValueError("%s byte count mismatch" % path)
    value = np.frombuffer(raw, dtype="<f4").copy().reshape(tuple(spec["shape"]))
    if not np.isfinite(value).all():
        raise ValueError("%s contains a non-finite value" % path)
    return value, _sha256(raw)


def _metrics(value, reference):
    lhs = value.astype(np.float64, copy=False).reshape(-1)
    rhs = reference.astype(np.float64, copy=False).reshape(-1)
    denom = float(np.linalg.norm(rhs))
    lhs_norm = float(np.linalg.norm(lhs))
    cosine = float(np.dot(lhs, rhs) / (lhs_norm * denom))
    relative_l2 = float(np.linalg.norm(lhs - rhs) / denom)
    return {"cosine": cosine, "relative_l2": relative_l2,
            "max_abs": float(np.max(np.abs(lhs - rhs)))}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--expected-candidate-sha256", required=True)
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
    if args.threads != 3 or args.iterations != 3:
        parser.error("this diagnostic is frozen to threads=3 and iterations=3")
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    candidate = pathlib.Path(args.candidate)
    candidate_raw = candidate.read_bytes()
    if _sha256(candidate_raw) != args.expected_candidate_sha256:
        raise ValueError("candidate SHA mismatch")
    manifest_raw = pathlib.Path(args.manifest).read_bytes()
    if _sha256(manifest_raw) != args.expected_manifest_sha256:
        raise ValueError("model manifest SHA mismatch")
    contract = json.loads(manifest_raw.decode("utf-8"))["models"]["suffix"]
    inputs = [_load_f32(path, contract["inputs"][0]) for path in args.input]
    references = [_load_f32(path, contract["outputs"][0])[0]
                  for path in args.expected]
    if inputs[0][1] == inputs[1][1]:
        raise ValueError("suffix inputs must be distinct")
    prefix = pathlib.Path(args.profile_prefix)
    before = set(prefix.parent.glob(prefix.name + "*.json"))
    old_profile = os.environ.get("ORT_PARTITION_PROFILE_PREFIX")
    old_optimized = os.environ.get("ORT_PARTITION_OPTIMIZED_MODEL")
    os.environ["ORT_PARTITION_PROFILE_PREFIX"] = str(prefix)
    os.environ["ORT_PARTITION_OPTIMIZED_MODEL"] = str(args.optimized_model)
    client = None
    samples = []
    try:
        client = OptimizedOrtPartitionClient(
            [args.runner, "--stream", str(candidate), str(args.threads)],
            contract, threads=args.threads, request_timeout=120.0,
            allow_spinning=0, preallocate_outputs=0)
        for index in range(args.iterations):
            case = index % 2
            started = time.perf_counter()
            values, run_ms = client.infer([inputs[case][0]])
            wall_ms = (time.perf_counter() - started) * 1000.0
            value = values[contract["outputs"][0]["name"]]
            metric = _metrics(value, references[case])
            samples.append({"iteration": index, "case": case,
                            "run_ms": run_ms, "call_wall_ms": wall_ms,
                            "output_sha256": _sha256(value.tobytes(order="C")),
                            "metrics": metric})
    finally:
        if client is not None:
            client.close()
        if old_profile is None:
            os.environ.pop("ORT_PARTITION_PROFILE_PREFIX", None)
        else:
            os.environ["ORT_PARTITION_PROFILE_PREFIX"] = old_profile
        if old_optimized is None:
            os.environ.pop("ORT_PARTITION_OPTIMIZED_MODEL", None)
        else:
            os.environ["ORT_PARTITION_OPTIMIZED_MODEL"] = old_optimized
    created = sorted(set(prefix.parent.glob(prefix.name + "*.json")) - before)
    if len(created) != 1 or not pathlib.Path(args.optimized_model).is_file():
        raise RuntimeError("ORT profile or optimized model was not created exactly once")
    if min(item["metrics"]["cosine"] for item in samples) < 0.999:
        raise RuntimeError("candidate cosine gate failed")
    if max(item["metrics"]["relative_l2"] for item in samples) > 0.05:
        raise RuntimeError("candidate relative-L2 gate failed")
    receipt = {
        "schema": "cnn-v10.1-suffix-candidate-ort-profile-diagnostic-v1",
        "status": "PASS_CANDIDATE_PROFILE_AND_ENGINEERING_ERROR_GATE",
        "formal_timing": False, "threads": args.threads,
        "iterations": args.iterations, "allow_spinning": 0,
        "preallocate_outputs": 0,
        "model_manifest_sha256": args.expected_manifest_sha256,
        "source_model_sha256": contract["sha256"],
        "candidate_sha256": args.expected_candidate_sha256,
        "samples": samples, "min_cosine": min(
            item["metrics"]["cosine"] for item in samples),
        "max_relative_l2": max(
            item["metrics"]["relative_l2"] for item in samples),
        "profile_file": str(created[0]),
        "profile_sha256": _sha256(created[0].read_bytes()),
        "optimized_model": str(pathlib.Path(args.optimized_model)),
        "optimized_model_sha256": _sha256(
            pathlib.Path(args.optimized_model).read_bytes()),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.write_bytes(raw)
    print(json.dumps({"status": receipt["status"],
                      "receipt_sha256": _sha256(raw)}, sort_keys=True))


if __name__ == "__main__":
    main()
