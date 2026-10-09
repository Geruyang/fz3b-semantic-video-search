#!/usr/bin/env python3
"""Classify actual target ORT integer kernels for a suffix selection."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib

import onnx


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--optimized-model", required=True)
    parser.add_argument("--host-receipt", required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    analysis = json.loads(pathlib.Path(args.analysis).read_text(encoding="utf-8"))
    receipt = json.loads(pathlib.Path(args.host_receipt).read_text(encoding="utf-8"))
    selected = receipt.get("selection", {}).get("preserved_selected_nodes")
    if not isinstance(selected, list) or not selected:
        raise ValueError("host receipt selected nodes missing")
    expected_conv = sum(name.endswith("/Conv") for name in selected)
    expected_matmul = sum(name.endswith("/MatMul") for name in selected)
    if expected_conv + expected_matmul != len(selected):
        raise ValueError("selected set contains an unsupported operator")
    graph = onnx.load(args.optimized_model).graph
    rows = dict((row["name"], row) for row in analysis["all_nodes"])
    kernels = []
    for node in graph.node:
        if node.op_type not in ("QLinearConv", "QLinearMatMul"):
            continue
        row = rows.get(node.name)
        if row is None:
            raise ValueError("optimized integer node was not profiled: %s" % node.name)
        kernels.append({"name": node.name, "op": node.op_type,
                        "provider": row["provider"], "mean_ms": row["mean_ms"],
                        "inputs": list(node.input), "outputs": list(node.output)})
    kernels.sort(key=lambda value: value["name"])
    qconv = sum(value["op"] == "QLinearConv" for value in kernels)
    qmatmul = sum(value["op"] == "QLinearMatMul" for value in kernels)
    if (len(kernels) != len(selected) or qconv != expected_conv or
            qmatmul != expected_matmul):
        raise ValueError("integer kernel counts do not match selected nodes")
    if any(value["provider"] != "CPUExecutionProvider" for value in kernels):
        raise ValueError("integer kernel executed outside CPUExecutionProvider")
    report = {
        "schema": "cnn-v10.1-suffix-target-kernel-classification-v2",
        "status": "PASS_TARGET_ORT_INTEGER_KERNELS_CONFIRMED",
        "scope": "target ORT 1.16.3 three-run diagnostic; QLinear kernels proven from optimized graph and profile",
        "candidate_sha256": args.candidate_sha256,
        "host_receipt_sha256": sha(args.host_receipt),
        "analysis_sha256": sha(args.analysis),
        "optimized_model_sha256": sha(args.optimized_model),
        "selected_source_nodes": selected,
        "integer_kernel_count": len(kernels),
        "qlinear_conv_count": qconv,
        "qlinear_matmul_count": qmatmul,
        "integer_kernel_mean_ms_sum": sum(value["mean_ms"] for value in kernels),
        "integer_kernel_model_run_share_percent": 100.0 * sum(
            value["mean_ms"] for value in kernels) / analysis["model_run_mean_ms"],
        "integer_kernels": kernels,
        "quantize_linear_mean_ms": analysis.get("operators", {}).get(
            "QuantizeLinear", {}).get("mean_ms", 0.0),
        "dequantize_linear_mean_ms": analysis.get("operators", {}).get(
            "DequantizeLinear", {}).get("mean_ms", 0.0),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.write_bytes(raw)
    print(json.dumps({"status": report["status"],
                      "integer_kernel_count": len(kernels),
                      "qlinear_conv_count": qconv,
                      "qlinear_matmul_count": qmatmul,
                      "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
