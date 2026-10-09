#!/usr/bin/env python3
"""Steady-state V10 full-model benchmark on one live runtime instance.

Each invocation owns one mode: a single real frame with a discarded mirror, or
two real distinct frames.  It creates the four ORT clients and V10 transport
once, runs exactly three warmups, then records ten measured calls without
closing or recreating any client, parameter buffer, arena, or device handle.
"""
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
    from cnn_ddr_v10_runtime import LinuxIoctlV10Transport
    from cnn_pipeline_v10_bundle import load_v10_release_bundle
    from cnn_pipeline_v10_deployment import load_v10_platform_deployment
    from run_cnn_pipeline_v10_board_window import create_full_model_runtime
    from run_cnn_pipeline_v7_fixed import (load_existing_split_clients,
                                           mobileclip_preprocess)
except ImportError:
    from .cnn_ddr_v10_runtime import LinuxIoctlV10Transport
    from .cnn_pipeline_v10_bundle import load_v10_release_bundle
    from .cnn_pipeline_v10_deployment import load_v10_platform_deployment
    from .run_cnn_pipeline_v10_board_window import create_full_model_runtime
    from .run_cnn_pipeline_v7_fixed import (load_existing_split_clients,
                                            mobileclip_preprocess)


WARMUP_COUNT = 3
MEASURED_COUNT = 10


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _percentile(values, percentile):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    position = (len(ordered) - 1) * float(percentile) / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _stats(values):
    values = [float(value) for value in values]
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
    }


def _cpu_frequency_khz():
    result = {}
    root = pathlib.Path("/sys/devices/system/cpu")
    for path in sorted(root.glob("cpu[0-9]*/cpufreq/scaling_cur_freq")):
        try:
            result[path.parts[-3]] = int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            pass
    return result


def _record_iteration(runtime, mode, tensors, expected_sha256, iteration, phase):
    frame_base = (0x100000 if phase == "warmup" else 0x200000) + iteration * 2
    started = time.perf_counter()
    if mode == "single":
        results = [runtime.run_one(frame_base, tensors[0])]
    else:
        results = runtime.run(((frame_base, tensors[0]),
                               (frame_base + 1, tensors[1])))
    execution_ms = (time.perf_counter() - started) * 1000.0
    summary = runtime.last_run_summary
    pair = summary["pair_timings"][0]
    features = []
    for index, result in enumerate(results):
        raw = np.asarray(result["features"], dtype="<f4").reshape(512).tobytes(order="C")
        actual_sha256 = _sha256(raw)
        features.append({
            "frame_id": result["frame_id"],
            "feature_sha256": actual_sha256,
            "expected_sha256": expected_sha256[index],
            "byte_exact_by_frozen_sha256": actual_sha256 == expected_sha256[index],
            "shadow_partner_used": result["shadow_partner_used"],
        })
    completions = []
    for event in pair["pl_events"]:
        completion = event["completion"]
        completions.append({
            "profile": event["profile"],
            "block_count": event["block_count"],
            "job_cycles": completion["job_cycles"],
            "protocol_error": completion["protocol_error"],
            "guard_error_flags": completion["guard_error_flags"],
            "mode_switch_reset": completion["mode_switch_reset"],
            "reset_generation_before": completion["reset_generation_before"],
            "reset_generation": completion["reset_generation"],
            "timing": event["timing"],
        })
    clean = (all(item["byte_exact_by_frozen_sha256"] for item in features) and
             all(item["protocol_error"] == 0 and item["guard_error_flags"] == 0
                 for item in completions))
    return {
        "phase": phase,
        "iteration": iteration,
        "execution_ms": execution_ms,
        "pair_wall_ms": pair["pair_wall_ms"],
        "real_frame_count": pair["real_frame_count"],
        "hardware_lane_frame_count": pair["hardware_lane_frame_count"],
        "shadow_counts_as_real_throughput": pair["shadow_counts_as_real_throughput"],
        "features": features,
        "ps_events": pair["ps_events"],
        "pl_completions": completions,
        "functional_protocol_pass": clean,
    }


def _summarize(measured):
    execution = [item["execution_ms"] for item in measured]
    pair_wall = [item["pair_wall_ms"] for item in measured]
    real_counts = [item["real_frame_count"] for item in measured]
    real_fps = [count * 1000.0 / elapsed
                for count, elapsed in zip(real_counts, execution)]
    ps_ort = [sum(event["ort_run_ms"] for event in item["ps_events"])
              for item in measured]
    ps_wall = [sum(event["call_wall_ms"] for event in item["ps_events"])
               for item in measured]
    keys = ("quantize_ms", "upload_ms", "submit_ms", "wait_ms",
            "download_ms", "dequantize_ms", "pl_window_wall_ms")
    pl = {key: _stats([sum(event["timing"][key]
                               for event in item["pl_completions"])
                            for item in measured]) for key in keys}
    return {
        "execution_ms": _stats(execution),
        "pair_wall_ms": _stats(pair_wall),
        "real_frames_per_second": _stats(real_fps),
        "batch_real_frames_per_second": sum(real_counts) * 1000.0 / sum(execution),
        "ps_ort_run_ms_sum": _stats(ps_ort),
        "ps_call_wall_ms_sum": _stats(ps_wall),
        "pl_timing_ms_sum": pl,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("single", "paired"), required=True)
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--deployment-manifest", required=True)
    parser.add_argument("--expected-deployment-sha256", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--device", default="/dev/network10_v10")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout-s", type=float, default=300.0)
    parser.add_argument("--input-image", action="append", required=True)
    parser.add_argument("--expected-feature-sha256", action="append", required=True)
    parser.add_argument("--warmup", type=int, default=WARMUP_COUNT)
    parser.add_argument("--measured", type=int, default=MEASURED_COUNT)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    required_inputs = 1 if args.mode == "single" else 2
    if (len(args.input_image) != required_inputs or
            len(args.expected_feature_sha256) != required_inputs):
        parser.error("mode %s requires exactly %d input and expected feature SHA values" %
                     (args.mode, required_inputs))
    if args.warmup != WARMUP_COUNT or args.measured != MEASURED_COUNT:
        parser.error("formal benchmark requires exactly 3 warmups and 10 measurements")
    if args.threads != 4:
        parser.error("formal benchmark requires --threads 4")
    output = pathlib.Path(args.output_dir)
    if output.exists():
        raise RuntimeError("output path already exists: %s" % output)
    for value in args.expected_feature_sha256:
        if (len(value) != 64 or any(char not in "0123456789abcdef" for char in value)):
            parser.error("expected feature SHA256 must be lowercase hex")

    loaded = load_v10_release_bundle(args.bundle_root, args.expected_bundle_sha256)
    deployment = load_v10_platform_deployment(
        args.deployment_manifest, args.expected_deployment_sha256,
        loaded["manifest_sha256"])
    clients = None
    transport = None
    runtime = None
    cleanup = None
    primary = None
    process_started = time.perf_counter()
    cpu_before = _cpu_frequency_khz()
    try:
        started = time.perf_counter()
        clients, unused_split_sha = load_existing_split_clients(
            loaded["model_root"], args.runner, loaded["model_manifest"],
            loaded["model_manifest_sha256"], threads=args.threads)
        transport = LinuxIoctlV10Transport(
            args.device,
            expected_parameter_manifest_words=loaded["parameter_manifest_words"])
        runtime = create_full_model_runtime(
            transport, loaded["parameter_contract"],
            loaded["manifest_sha256"], clients, timeout_s=args.timeout_s)
        setup_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        tensors = [mobileclip_preprocess(path) for path in args.input_image]
        preprocess_ms = (time.perf_counter() - started) * 1000.0

        warmups = [_record_iteration(
            runtime, args.mode, tensors, args.expected_feature_sha256, index, "warmup")
                   for index in range(args.warmup)]
        measured_started = time.perf_counter()
        measured = [_record_iteration(
            runtime, args.mode, tensors, args.expected_feature_sha256, index, "measured")
                    for index in range(args.measured)]
        measured_loop_ms = (time.perf_counter() - measured_started) * 1000.0
        if not all(item["functional_protocol_pass"] for item in warmups + measured):
            raise RuntimeError("feature identity or protocol/guard check failed")
    except Exception as error:
        primary = error
        raise
    finally:
        cleanup_started = time.perf_counter()
        if runtime is not None and not runtime.closed:
            try:
                cleanup = runtime.close()
            except Exception:
                if primary is None:
                    raise
        elif transport is not None:
            try:
                transport.close()
            except Exception:
                if primary is None:
                    raise
        elif clients is not None:
            for client in clients.values():
                try:
                    client.close()
                except Exception:
                    if primary is None:
                        raise
        cleanup_ms = (time.perf_counter() - cleanup_started) * 1000.0
    cpu_after = _cpu_frequency_khz()
    receipt = {
        "schema": "cnn-pipeline-v10.1-full-model-steady-benchmark-v1",
        "status": "PASS_3_WARMUP_10_MEASURED_FEATURE_EXACT_PROTOCOL_CLEAN",
        "mode": args.mode,
        "ort_threads": args.threads,
        "warmup_count": args.warmup,
        "measured_count": args.measured,
        "same_runtime_instance": True,
        "parameters_and_ort_sessions_resident_across_all_iterations": True,
        "steady_state_claim": True,
        "schedule": "synchronous serial PS->PL stages; no cross-pair pipeline",
        "single_shadow_counts_as_real_throughput": False,
        "release_manifest_sha256": loaded["manifest_sha256"],
        "deployment_manifest_sha256": deployment["manifest_sha256"],
        "kernel_clock_hz": deployment["clock_hz"],
        "split_model_manifest_sha256": loaded["model_manifest_sha256"],
        "input_paths": list(args.input_image),
        "expected_feature_sha256": list(args.expected_feature_sha256),
        "cpu_frequency_khz_before": cpu_before,
        "cpu_frequency_khz_after": cpu_after,
        "setup_ms": setup_ms,
        "preprocess_ms": preprocess_ms,
        "measured_loop_ms": measured_loop_ms,
        "cleanup_ms": cleanup_ms,
        "process_wall_ms": (time.perf_counter() - process_started) * 1000.0,
        "warmups": warmups,
        "measured": measured,
        "statistics": _summarize(measured),
        "cleanup": cleanup,
        "interpretation": {
            "submit_timing": "submit ioctl includes the hardware job; it is not launch-only overhead",
            "profile_switch": "frozen driver performs guarded reset between distinct profiles",
            "scope": "existing engineering images; no independent new-sample accuracy evaluation",
        },
    }
    output.mkdir(parents=True)
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output / "result.json").write_bytes(raw)
    print(json.dumps({
        "status": receipt["status"], "mode": args.mode,
        "result_sha256": _sha256(raw),
        "execution_p50_ms": receipt["statistics"]["execution_ms"]["p50"],
        "execution_p95_ms": receipt["statistics"]["execution_ms"]["p95"],
        "batch_real_frames_per_second": receipt["statistics"]["batch_real_frames_per_second"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["WARMUP_COUNT", "MEASURED_COUNT", "main"]
