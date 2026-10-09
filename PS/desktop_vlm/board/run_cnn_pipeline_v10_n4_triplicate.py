#!/usr/bin/env python3
"""Run exactly three paired N4 fixture jobs on one V10 transport."""
from __future__ import print_function

import argparse
import json
import pathlib
import time

from cnn_ddr_v10_runtime import LinuxIoctlV10Transport
from cnn_pipeline_v10_bundle import load_v10_release_bundle
from cnn_pipeline_v10_deployment import load_v10_platform_deployment
from run_cnn_pipeline_v10_board_window import run_paired_exact_case


def read(path):
    return pathlib.Path(path).read_bytes()


def case_files(root, swapped):
    left, right = (("b", "a") if swapped else ("a", "b"))
    base = pathlib.Path(root) / "p1"
    return (read(base / ("input-%s.i16" % left)),
            read(base / ("expected-%s.i16" % left)),
            read(base / ("input-%s.i16" % right)),
            read(base / ("expected-%s.i16" % right)))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--deployment-manifest", required=True)
    parser.add_argument("--expected-deployment-sha256", required=True)
    parser.add_argument("--cases-root", required=True)
    parser.add_argument("--device", default="/dev/network10_v10")
    parser.add_argument("--baseline-cycles", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output = pathlib.Path(args.output_dir)
    if output.exists():
        raise RuntimeError("output exists: %s" % output)
    bundle = load_v10_release_bundle(args.bundle_root, args.expected_bundle_sha256)
    deployment = load_v10_platform_deployment(
        args.deployment_manifest, args.expected_deployment_sha256,
        bundle["manifest_sha256"])
    result = {
        "schema": "cnn-pipeline-v10-board-n4-rdissue-triplicate-v1",
        "release_manifest_sha256": bundle["manifest_sha256"],
        "deployment_manifest_sha256": deployment["manifest_sha256"],
        "kernel_clock_hz": deployment["clock_hz"],
        "same_transport": True,
        "profile": 1,
        "block_count": 20,
        "baseline_cycles": args.baseline_cycles,
        "jobs": [],
    }
    transport = None
    cleanup = None
    primary = None
    started = time.perf_counter()
    try:
        transport = LinuxIoctlV10Transport(
            args.device,
            expected_parameter_manifest_words=bundle["parameter_manifest_words"])
        for index, swapped in enumerate((False, True, False)):
            values = case_files(args.cases_root, swapped)
            job_started = time.perf_counter()
            item = run_paired_exact_case(
                transport, 1, 20,
                bundle["parameter_contract"]["profiles"][1]["params"],
                values[0], values[1], values[2], values[3], timeout_s=300.0)
            item["iteration"] = index
            item["swapped"] = swapped
            item["wall_ms"] = (time.perf_counter() - job_started) * 1000.0
            cycles = item["completion"]["job_cycles"]
            item["kernel_ms"] = float(cycles) * 1000.0 / deployment["clock_hz"]
            item["gain_vs_baseline"] = float(args.baseline_cycles - cycles) / args.baseline_cycles
            if (not item["byte_exact_a"] or not item["byte_exact_b"] or
                    item["completion"]["protocol_error"] != 0 or
                    item["completion"]["guard_error_flags"] != 0):
                raise RuntimeError("N4 exact/protocol failure at iteration %d" % index)
            if index > 0 and item["completion"]["mode_switch_reset"]:
                raise RuntimeError("same-profile repeat unexpectedly reset at iteration %d" % index)
            result["jobs"].append(item)
    except Exception as error:
        primary = error
        result["error"] = "%s: %s" % (type(error).__name__, error)
        raise
    finally:
        if transport is not None:
            try:
                cleanup = transport.close()
            except Exception:
                if primary is None:
                    raise
        result["cleanup"] = cleanup
        result["total_wall_ms"] = (time.perf_counter() - started) * 1000.0
        if result["jobs"]:
            cycles = [item["completion"]["job_cycles"] for item in result["jobs"]]
            result["cycles"] = cycles
            result["mean_cycles"] = sum(cycles) / float(len(cycles))
            result["mean_gain_vs_baseline"] = (
                float(args.baseline_cycles - result["mean_cycles"]) / args.baseline_cycles)
            result["maximum_gain_vs_baseline"] = max(
                item["gain_vs_baseline"] for item in result["jobs"])
        output.mkdir(parents=True, exist_ok=True)
        (output / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "FZVA_N4_RDISSUE_TRIPLICATE_EXACT_PASS",
                      "cycles": result["cycles"],
                      "mean_gain_vs_baseline": result["mean_gain_vs_baseline"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
