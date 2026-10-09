#!/usr/bin/env python3
"""Bind a target ORT optimized graph to the selected suffix QDQ candidate."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib

import onnx


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--optimized-model", required=True)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    analysis_path = pathlib.Path(args.analysis)
    model_path = pathlib.Path(args.optimized_model)
    manifest_path = pathlib.Path(args.candidate_manifest)
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    graph = onnx.load(str(model_path)).graph
    rows = dict((row["name"], row) for row in analysis["all_nodes"])
    integer_nodes = []
    for node in graph.node:
        if node.op_type not in ("QLinearConv", "QLinearMatMul"):
            continue
        row = rows.get(node.name)
        if row is None:
            raise ValueError("optimized integer node was not profiled: %s" % node.name)
        integer_nodes.append({
            "name": node.name, "op": node.op_type,
            "mean_ms": row["mean_ms"], "provider": row["provider"],
            "inputs": list(node.input), "outputs": list(node.output),
        })
    integer_nodes.sort(key=lambda item: item["name"])
    if len(integer_nodes) != 13:
        raise ValueError("expected exactly 13 target integer kernels")
    if any(item["provider"] != "CPUExecutionProvider" for item in integer_nodes):
        raise ValueError("integer kernel executed outside CPUExecutionProvider")

    convffn = {}
    for block in range(4):
        needle = "/network.7.%d/convffn/" % block
        selected = [row for row in analysis["all_nodes"]
                    if row["op"] in ("Conv", "FusedConv", "QLinearConv") and
                    (needle in row["name"] or
                    (row["op"] == "QLinearConv" and any(
                        needle in value for node in integer_nodes
                        if node["name"] == row["name"]
                        for value in node["inputs"] + node["outputs"])))]
        convffn[str(block)] = {
            "kernel_count": len(selected),
            "kernel_mean_ms_sum": sum(row["mean_ms"] for row in selected),
            "kernels": selected,
            "precision": ("W8A8_QLinearConv" if block in (1, 3)
                          else "FP32_Conv"),
        }
    if any(convffn[str(block)]["kernel_count"] != 3 for block in range(4)):
        raise ValueError("each ConvFFN block must resolve to exactly three kernels")
    integer_ms = sum(item["mean_ms"] for item in integer_nodes)
    report = {
        "schema": "cnn-v10.1-suffix-target-kernel-classification-v1",
        "status": "PASS_TARGET_ORT_INTEGER_KERNELS_CONFIRMED",
        "scope": ("target ORT 1.16.3 three-run diagnostic; selected QDQ nodes "
                  "are proven as CPU QLinear kernels, not a throughput claim"),
        "analysis_sha256": _sha(analysis_path),
        "optimized_model_sha256": _sha(model_path),
        "candidate_manifest_sha256": _sha(manifest_path),
        "candidate_sha256": manifest["candidate"]["sha256"],
        "integer_kernel_count": len(integer_nodes),
        "qlinear_conv_count": sum(item["op"] == "QLinearConv"
                                  for item in integer_nodes),
        "qlinear_matmul_count": sum(item["op"] == "QLinearMatMul"
                                    for item in integer_nodes),
        "integer_kernel_mean_ms_sum": integer_ms,
        "integer_kernel_model_run_share_percent": (
            100.0 * integer_ms / analysis["model_run_mean_ms"]),
        "integer_kernels": integer_nodes,
        "convffn_blocks": convffn,
        "remaining_fp32_convffn_kernel_mean_ms_sum": (
            convffn["0"]["kernel_mean_ms_sum"] +
            convffn["2"]["kernel_mean_ms_sum"]),
        "quantized_convffn_kernel_mean_ms_sum": (
            convffn["1"]["kernel_mean_ms_sum"] +
            convffn["3"]["kernel_mean_ms_sum"]),
        "quantize_linear_mean_ms": analysis["operators"]["QuantizeLinear"]["mean_ms"],
        "dequantize_linear_mean_ms": analysis["operators"]["DequantizeLinear"]["mean_ms"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.write_bytes(raw)
    print(json.dumps({"status": report["status"],
                      "integer_kernel_count": len(integer_nodes),
                      "qlinear_conv_count": report["qlinear_conv_count"],
                      "qlinear_matmul_count": report["qlinear_matmul_count"],
                      "receipt_sha256": hashlib.sha256(raw).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
