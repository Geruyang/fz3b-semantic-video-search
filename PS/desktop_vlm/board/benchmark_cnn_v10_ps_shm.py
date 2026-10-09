#!/usr/bin/env python3
"""Compare pipe-payload and shared-mmap V10 PS clients without opening PL.

Each pair uses two frozen, distinct tensors at every partition boundary.  This
isolates PS ORT and pipe/client overhead from PL time while retaining the exact
production model files and tensor contracts.  No model outputs are fed into a
different stage: each stage consumes its independently frozen real boundary
fixture, so factory PL may remain loaded during this benchmark.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import math
import os
import pathlib
import statistics
import time

import numpy as np

try:
    from cnn_v10_ps_clients import load_optimized_split_clients
    from cnn_v10_ps_shm_clients import load_shm_split_clients
except ImportError:
    from .cnn_v10_ps_clients import load_optimized_split_clients
    from .cnn_v10_ps_shm_clients import load_shm_split_clients


STAGES = (
    ("stem-prefix", "stem-prefix-input.f32", "stem-prefix-output.f32", "n0_input"),
    ("network1-bridge", "network1-bridge-input.f32",
     "network1-bridge-output.f32", "n2_input"),
    ("network3-bridge", "network3-bridge-input.f32",
     "network3-bridge-output.f32", "n4_input"),
    ("suffix", "suffix-input.f32", "suffix-output.f32", "features"),
)


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _percentile(values, percentile):
    ordered = sorted(float(item) for item in values)
    position = (len(ordered) - 1) * float(percentile) / 100.0
    lower, upper = int(math.floor(position)), int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _stats(values):
    values = [float(item) for item in values]
    return {"count": len(values), "min": min(values), "max": max(values),
            "mean": statistics.mean(values), "p50": _percentile(values, 50),
            "p95": _percentile(values, 95)}


def _rss_kib(pid):
    try:
        with open("/proc/%d/status" % int(pid), "r") as stream:
            for line in stream:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (IOError, OSError, ValueError):
        return None
    return None


def _cpu_frequency_khz():
    result = {}
    for path in sorted(pathlib.Path("/sys/devices/system/cpu").glob(
            "cpu[0-9]*/cpufreq/scaling_cur_freq")):
        try:
            result[path.parts[-3]] = int(path.read_text().strip())
        except (IOError, OSError, ValueError):
            pass
    return result


def _load_fixture(case_root, contracts):
    case_root = pathlib.Path(case_root)
    result = {}
    for stage, input_name, output_name, logical_name in STAGES:
        spec = contracts[stage]
        input_spec = spec["inputs"][0]
        output_spec = spec["outputs"][0]
        input_raw = (case_root / input_name).read_bytes()
        output_raw = (case_root / output_name).read_bytes()
        if len(input_raw) != input_spec["bytes"]:
            raise ValueError("%s %s input size mismatch" % (case_root, stage))
        if len(output_raw) != output_spec["bytes"]:
            raise ValueError("%s %s output size mismatch" % (case_root, stage))
        array = np.frombuffer(input_raw, dtype="<f4").copy().reshape(
            tuple(input_spec["shape"]))
        if not np.isfinite(array).all():
            raise ValueError("%s %s input contains non-finite values" %
                             (case_root, stage))
        result[stage] = {
            "input": array, "logical_name": logical_name,
            "input_sha256": _sha256(input_raw),
            "expected_sha256": _sha256(output_raw),
        }
    return result


def _client_rss(clients):
    result = {"coordinator": _rss_kib(os.getpid()), "children": {}}
    for name, client in clients.items():
        process = getattr(getattr(client, "_client", None), "process", None)
        if process is not None:
            result["children"][name] = {
                "pid": process.pid, "rss_kib": _rss_kib(process.pid)}
    values = [value["rss_kib"] for value in result["children"].values()
              if value["rss_kib"] is not None]
    result["children_total_rss_kib"] = sum(values)
    return result


def _one_pair(clients, fixtures, iteration, phase):
    started = time.perf_counter()
    events = []
    clean = True
    for stage, unused_input, unused_output, logical_name in STAGES:
        for lane, fixture in zip(("A", "B"), fixtures):
            call_started = time.perf_counter()
            outputs, run_ms = clients[stage].infer([fixture[stage]["input"]])
            wall_ms = (time.perf_counter() - call_started) * 1000.0
            output = np.asarray(outputs[logical_name], dtype="<f4", order="C")
            actual = _sha256(output.tobytes(order="C"))
            exact = actual == fixture[stage]["expected_sha256"]
            clean = clean and exact
            events.append({
                "stage": stage, "lane": lane, "run_ms": run_ms,
                "call_wall_ms": wall_ms, "interface_overhead_ms": wall_ms - run_ms,
                "output_sha256": actual,
                "expected_sha256": fixture[stage]["expected_sha256"],
                "byte_exact": exact,
            })
    return {
        "phase": phase, "iteration": iteration,
        "pair_wall_ms": (time.perf_counter() - started) * 1000.0,
        "real_frame_count": 2, "events": events,
        "all_stage_outputs_byte_exact": clean,
    }


def _summarize(records):
    result = {
        "pair_wall_ms": _stats([item["pair_wall_ms"] for item in records]),
        "real_frames_per_second": _stats([
            2000.0 / item["pair_wall_ms"] for item in records]),
        "batch_real_frames_per_second": (
            2.0 * len(records) * 1000.0 /
            sum(item["pair_wall_ms"] for item in records)),
        "stage_lane": {},
    }
    for stage, unused_input, unused_output, unused_logical in STAGES:
        for lane in ("A", "B"):
            key = "%s/%s" % (stage, lane)
            events = [event for record in records for event in record["events"]
                      if event["stage"] == stage and event["lane"] == lane]
            result["stage_lane"][key] = {
                "run_ms": _stats([event["run_ms"] for event in events]),
                "call_wall_ms": _stats([
                    event["call_wall_ms"] for event in events]),
                "interface_overhead_ms": _stats([
                    event["interface_overhead_ms"] for event in events]),
            }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("optimized", "shm"), required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--fixture-root", action="append", required=True)
    parser.add_argument("--warmup-pairs", type=int, default=3)
    parser.add_argument("--measured-pairs", type=int, default=10)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if len(args.fixture_root) != 2:
        parser.error("exactly two distinct fixture roots are required")
    if args.warmup_pairs != 3 or args.measured_pairs not in (10, 30):
        parser.error("benchmark requires 3 warmup pairs and 10 or 30 measured pairs")
    output = pathlib.Path(args.output)
    if output.exists():
        raise RuntimeError("output already exists: %s" % output)
    with open(args.manifest, "rb") as stream:
        manifest_raw = stream.read()
    if _sha256(manifest_raw) != args.expected_manifest_sha256:
        raise ValueError("model manifest SHA mismatch")
    manifest = json.loads(manifest_raw.decode("utf-8"))
    contracts = dict((name, {"inputs": record["inputs"],
                             "outputs": record["outputs"]})
                     for name, record in manifest["models"].items())
    fixtures = [_load_fixture(root, contracts) for root in args.fixture_root]
    if fixtures[0]["stem-prefix"]["input_sha256"] == fixtures[1]["stem-prefix"]["input_sha256"]:
        raise ValueError("A/B stem fixtures must be distinct")
    loader = (load_shm_split_clients if args.client == "shm"
              else load_optimized_split_clients)
    clients = None
    started = time.perf_counter()
    try:
        clients, manifest_sha = loader(
            args.model_root, args.runner, args.manifest,
            args.expected_manifest_sha256, threads=args.threads)
        setup_ms = (time.perf_counter() - started) * 1000.0
        cpu_before = _cpu_frequency_khz()
        rss_before = _client_rss(clients)
        warmups = [_one_pair(clients, fixtures, index, "warmup")
                   for index in range(args.warmup_pairs)]
        rss_after_warmup = _client_rss(clients)
        measured_started = time.perf_counter()
        measured = [_one_pair(clients, fixtures, index, "measured")
                    for index in range(args.measured_pairs)]
        measured_loop_ms = (time.perf_counter() - measured_started) * 1000.0
        rss_after = _client_rss(clients)
        cpu_after = _cpu_frequency_khz()
        if not all(item["all_stage_outputs_byte_exact"]
                   for item in warmups + measured):
            raise RuntimeError("at least one PS partition output differs from frozen fixture")
    finally:
        cleanup_started = time.perf_counter()
        if clients is not None:
            for client in clients.values():
                client.close()
        cleanup_ms = (time.perf_counter() - cleanup_started) * 1000.0
    receipt = {
        "schema": "cnn-v10.1-ps-partition-pair-benchmark-v1",
        "status": "PASS_PS_ONLY_DISTINCT_PAIR_ALL_PARTITIONS_BYTE_EXACT",
        "scope": "factory PL retained; no PL device opened; fixed independent boundary fixtures",
        "client": args.client, "threads": args.threads,
        "allow_spinning": os.environ.get("ORT_PARTITION_ALLOW_SPINNING"),
        "preallocate_outputs": os.environ.get("ORT_PARTITION_PREALLOC_OUTPUTS"),
        "model_manifest_sha256": manifest_sha,
        "runner_sha256": _sha256(pathlib.Path(args.runner).read_bytes()),
        "fixture_roots": list(args.fixture_root),
        "warmup_pairs": args.warmup_pairs,
        "measured_pairs": args.measured_pairs,
        "measured_real_frames": args.measured_pairs * 2,
        "same_four_sessions_resident": True,
        "setup_ms": setup_ms, "measured_loop_ms": measured_loop_ms,
        "cleanup_ms": cleanup_ms,
        "cpu_frequency_khz_before": cpu_before,
        "cpu_frequency_khz_after": cpu_after,
        "rss_kib_before": rss_before,
        "rss_kib_after_warmup": rss_after_warmup,
        "rss_kib_after": rss_after,
        "warmups": warmups, "measured": measured,
        "statistics": _summarize(measured),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.write_bytes(raw)
    print(json.dumps({
        "status": receipt["status"], "client": args.client,
        "result_sha256": _sha256(raw),
        "pair_p50_ms": receipt["statistics"]["pair_wall_ms"]["p50"],
        "batch_real_frames_per_second": receipt["statistics"]["batch_real_frames_per_second"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
