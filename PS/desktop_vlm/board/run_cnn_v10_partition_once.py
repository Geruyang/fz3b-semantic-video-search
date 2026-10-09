#!/usr/bin/env python3
"""Run one frozen V10 PS partition on explicit FP32 tensors.

This utility is intentionally limited to offline/PS-only evidence generation.
It records the actual runner header and file identities and never opens an FPGA
device or reports performance-valid results.
"""
from __future__ import print_function

import argparse
import datetime
import hashlib
import json
import os

import numpy as np

from cnn_ddr_v5_runtime import load_v5_split_contracts
from cnn_v10_ps_shm_clients import ShmOrtPartitionClient


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _record(path):
    return {"path": os.path.abspath(path), "bytes": os.path.getsize(path),
            "sha256": _sha256(path)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--partition", choices=("network3-bridge", "suffix"), required=True)
    parser.add_argument("--model-override")
    parser.add_argument("--expected-model-sha256")
    parser.add_argument("--runner", required=True)
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", action="append", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    if len(args.input) != len(args.output) or not args.input:
        raise ValueError("input/output counts must match and be nonzero")
    if (args.model_override is None) != (args.expected_model_sha256 is None):
        raise ValueError("model override path and expected SHA must be supplied together")

    bundle = load_v5_split_contracts(
        args.model_root, args.expected_manifest_sha256)
    if os.path.abspath(args.manifest) != os.path.abspath(
            os.path.join(args.model_root, "manifest.json")):
        raise ValueError("manifest path must be the selected model-root manifest")
    record = bundle["models"][args.partition]
    model_path = record["path"]
    if args.model_override is not None:
        model_path = os.path.abspath(args.model_override)
        if (_sha256(model_path) != args.expected_model_sha256.lower()):
            raise ValueError("override model SHA mismatch")
    input_spec = record["contract"]["inputs"][0]
    output_spec = record["contract"]["outputs"][0]
    report = {
        "schema": "cnn-v10-ps-partition-once-v1",
        "status": "RUNNING",
        "hardware_execution": False,
        "performance_valid": False,
        "partition": args.partition,
        "threads": args.threads,
        "model_manifest_sha256": bundle["manifest_sha256"],
        "model": _record(model_path),
        "runner": _record(args.runner),
        "cases": [],
        "started_utc": datetime.datetime.utcnow().isoformat() + "Z",
    }
    client = ShmOrtPartitionClient(
        [args.runner, model_path, str(args.threads)],
        record["contract"], threads=args.threads)
    try:
        report["runner_header"] = client.header
        for source_path, output_path in zip(args.input, args.output):
            source = np.fromfile(source_path, dtype="<f4")
            expected_count = input_spec["bytes"] // 4
            if source.size != expected_count:
                raise ValueError("input tensor byte count mismatch")
            source = source.reshape(tuple(input_spec["shape"]))
            response, run_ms = client.infer([source])
            value = response[output_spec["name"]]
            if value.shape != tuple(output_spec["shape"]):
                raise ValueError("output tensor shape mismatch")
            value.astype("<f4", copy=False).tofile(output_path)
            report["cases"].append({
                "input": _record(source_path),
                "output": _record(output_path),
                "run_ms": run_ms,
            })
    finally:
        client.close()
    report["status"] = "PASS_PS_ONLY_NOT_HARDWARE"
    report["finished_utc"] = datetime.datetime.utcnow().isoformat() + "Z"
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with open(args.report, "wb") as stream:
        stream.write(raw)
    print(json.dumps({"status": report["status"],
                      "report_sha256": hashlib.sha256(raw).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
