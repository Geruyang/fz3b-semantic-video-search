#!/usr/bin/env python3
"""Summarize an ORT Chrome trace from the frozen V10 suffix diagnostic."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib
import statistics

import onnx


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--optimized-model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    profile = pathlib.Path(args.profile)
    optimized = pathlib.Path(args.optimized_model)
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    events = json.loads(profile.read_text(encoding="utf-8"))
    graph = onnx.load(str(optimized)).graph
    nodes = dict((node.name, node) for node in graph.node)
    model_runs = [event for event in events if event.get("name") == "model_run"]
    if len(model_runs) != 3:
        raise ValueError("expected three profiled model runs")
    grouped = {}
    for event in events:
        if (event.get("cat") == "Node" and
                str(event.get("name", "")).endswith("_kernel_time")):
            name = event["name"][:-len("_kernel_time")]
            grouped.setdefault(name, []).append(event)
    rows = []
    for name, samples in grouped.items():
        if len(samples) != len(model_runs):
            raise ValueError("node %s sample count mismatch" % name)
        args0 = samples[0].get("args", {})
        node = nodes.get(name)
        durations = [float(item["dur"]) / 1000.0 for item in samples]
        rows.append({
            "name": name,
            "op": args0.get("op_name", node.op_type if node is not None else None),
            "provider": args0.get("provider"),
            "samples": len(durations),
            "mean_ms": statistics.mean(durations),
            "min_ms": min(durations), "max_ms": max(durations),
        })
    rows.sort(key=lambda row: row["mean_ms"], reverse=True)
    operators = {}
    for row in rows:
        record = operators.setdefault(row["op"], {"nodes": 0, "mean_ms": 0.0})
        record["nodes"] += 1
        record["mean_ms"] += row["mean_ms"]
    mean_model_ms = statistics.mean(float(item["dur"]) / 1000.0
                                    for item in model_runs)
    for record in operators.values():
        record["model_run_share_percent"] = (
            100.0 * record["mean_ms"] / mean_model_ms)
    report = {
        "schema": "cnn-v10.1-suffix-ort-node-profile-analysis-v1",
        "status": "PASS_THREE_RUN_TARGET_ORT_PROFILE_ANALYZED",
        "scope": "diagnostic only; profiler timing is not a formal throughput benchmark",
        "profile_sha256": _sha(profile),
        "optimized_model_sha256": _sha(optimized),
        "model_run_ms": [float(item["dur"]) / 1000.0 for item in model_runs],
        "model_run_mean_ms": mean_model_ms,
        "optimized_node_count": len(graph.node),
        "profiled_node_count": len(rows),
        "operators": operators,
        "top_nodes": rows[:32],
        "all_nodes": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "model_run_mean_ms": mean_model_ms,
                      "top_operators": sorted(
                          ((key, value["mean_ms"]) for key, value in operators.items()),
                          key=lambda item: item[1], reverse=True)[:8]}, sort_keys=True))


if __name__ == "__main__":
    main()
