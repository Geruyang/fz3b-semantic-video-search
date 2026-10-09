#!/usr/bin/env python3
"""Target ORT compatibility, timing and engineering gate for suffix candidate."""
from __future__ import print_function

import argparse
import hashlib
import json
import math
import pathlib
import statistics
import time

import numpy as np

from cnn_v10_ps_shm_clients import ShmOrtPartitionClient


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _metrics(actual, reference):
    a = actual.astype(np.float64).reshape(-1)
    b = reference.astype(np.float64).reshape(-1)
    delta = a - b
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    return {"cosine": float(np.dot(a, b) / (na * nb)) if na and nb else 0.0,
            "relative_l2": float(np.linalg.norm(delta) / max(nb, np.finfo(np.float64).tiny)),
            "max_abs": float(np.max(np.abs(delta)))}


def _stats(values):
    ordered = sorted(float(x) for x in values)
    return {"count": len(ordered), "min": ordered[0], "max": ordered[-1],
            "mean": statistics.mean(ordered),
            "p50": statistics.median(ordered),
            "p95": ordered[int(math.ceil(.95 * len(ordered))) - 1]}


def _run(client, samples, repeats):
    records = []
    for unused in range(repeats):
        for sample in samples:
            started = time.perf_counter()
            outputs, run_ms = client.infer([sample["input"]])
            wall_ms = (time.perf_counter() - started) * 1000.0
            value = np.asarray(outputs["features"], dtype="<f4").reshape(1, 512)
            records.append({"case": sample["case"], "run_ms": run_ms,
                            "wall_ms": wall_ms,
                            "output_sha256": _sha(value.tobytes()),
                            "metrics": _metrics(value, sample["expected"])})
    return records


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", required=True)
    parser.add_argument("--source-model", required=True)
    parser.add_argument("--candidate-model", required=True)
    parser.add_argument("--candidate-receipt", required=True)
    parser.add_argument("--fixture-root", action="append", required=True)
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--warmup-rounds", type=int, default=3)
    parser.add_argument("--measured-rounds", type=int, default=10)
    parser.add_argument("--min-cosine", type=float, default=.999)
    parser.add_argument("--max-relative-l2", type=float, default=.05)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if len(args.fixture_root) < 2:
        parser.error("at least two engineering fixtures required")
    candidate_raw = pathlib.Path(args.candidate_model).read_bytes()
    receipt_raw = pathlib.Path(args.candidate_receipt).read_bytes()
    receipt = json.loads(receipt_raw.decode("utf-8"))
    candidate_sha = _sha(candidate_raw)
    if (receipt.get("status") != "PASS" or
            receipt.get("files", {}).get("suffix-w8a8-qdq-candidate.onnx", {}).get("sha256") != candidate_sha):
        raise ValueError("candidate receipt status/SHA mismatch")
    samples = []
    for index, root in enumerate(args.fixture_root):
        root = pathlib.Path(root)
        input_raw = (root / "suffix-input.f32").read_bytes()
        output_raw = (root / "suffix-output.f32").read_bytes()
        samples.append({"case": "image-%02d" % index,
                        "input": np.frombuffer(input_raw, dtype="<f4").copy().reshape(1, 256, 16, 16),
                        "expected": np.frombuffer(output_raw, dtype="<f4").copy().reshape(1, 512),
                        "input_sha256": _sha(input_raw), "expected_sha256": _sha(output_raw)})
    contract = {"inputs": [{"name": "/image_encoder/model/network.4/network.4.19/Add_output_0",
                              "shape": [1, 256, 16, 16], "dtype": "<f4", "bytes": 262144}],
                "outputs": [{"name": "features", "shape": [1, 512],
                               "dtype": "<f4", "bytes": 2048}]}
    results = {}
    for label, model in (("fp32", args.source_model), ("candidate", args.candidate_model)):
        client = ShmOrtPartitionClient([args.runner, model, str(args.threads)], contract,
                                       threads=args.threads, request_timeout=60.0)
        try:
            _run(client, samples, args.warmup_rounds)
            records = _run(client, samples, args.measured_rounds)
        finally:
            client.close()
        results[label] = {"records": records,
                          "run_ms": _stats([x["run_ms"] for x in records]),
                          "wall_ms": _stats([x["wall_ms"] for x in records])}
    fp32_exact = all(record["output_sha256"] == samples[int(record["case"][-2:])]["expected_sha256"]
                     for record in results["fp32"]["records"])
    candidate_gate = all(record["metrics"]["cosine"] >= args.min_cosine and
                         record["metrics"]["relative_l2"] <= args.max_relative_l2
                         for record in results["candidate"]["records"])
    if not fp32_exact or not candidate_gate:
        raise RuntimeError("target source exact or candidate engineering gate failed")
    report = {"schema": "cnn-v10.1-suffix-target-candidate-v1",
              "status": "PASS_TARGET_ORT116_ENGINEERING_GATE",
              "runtime": "onnxruntime-1.16.3-aarch64-cpu", "threads": args.threads,
              "candidate_sha256": candidate_sha,
              "candidate_receipt_sha256": _sha(receipt_raw),
              "source_model_sha256": _sha(pathlib.Path(args.source_model).read_bytes()),
              "min_cosine": args.min_cosine, "max_relative_l2": args.max_relative_l2,
              "fixtures": [{k: v for k, v in sample.items() if k not in ("input", "expected")}
                           for sample in samples],
              "warmup_rounds": args.warmup_rounds,
              "measured_rounds": args.measured_rounds,
              "fp32_exact": fp32_exact, "candidate_gate": candidate_gate,
              "results": results}
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise RuntimeError("refusing to overwrite output")
    output.write_bytes(raw)
    print(json.dumps({"status": report["status"], "receipt_sha256": _sha(raw),
                      "fp32_run_mean_ms": results["fp32"]["run_ms"]["mean"],
                      "candidate_run_mean_ms": results["candidate"]["run_ms"]["mean"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
