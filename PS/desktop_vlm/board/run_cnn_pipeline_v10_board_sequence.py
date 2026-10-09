#!/usr/bin/env python3
"""Run the three V10 profiles, repeats, switches and one driver reject."""
from __future__ import print_function

import argparse
import errno
import json
import pathlib
import time

from cnn_ddr_v6_runtime import _iow
from cnn_ddr_v10_runtime import LinuxIoctlV10Transport, _SUBMIT_STRUCT
from cnn_pipeline_v10_bundle import load_v10_release_bundle
from cnn_pipeline_v10_deployment import load_v10_platform_deployment
from run_cnn_pipeline_v10_board_window import run_paired_exact_case


def read(path):
    return pathlib.Path(path).read_bytes()


def case_files(root, profile, swapped):
    left, right = (("b", "a") if swapped else ("a", "b"))
    base = pathlib.Path(root) / ("p%d" % profile)
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
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output = pathlib.Path(args.output_dir)
    if output.exists():
        raise RuntimeError("output exists: %s" % output)
    bundle = load_v10_release_bundle(args.bundle_root, args.expected_bundle_sha256)
    deployment = load_v10_platform_deployment(
        args.deployment_manifest, args.expected_deployment_sha256,
        bundle["manifest_sha256"])
    plan = [
        (2, False, False, "n0"),
        (2, True, False, "n0-repeat-swapped"),
        (0, False, True, "n2-switch"),
        (0, True, False, "n2-repeat-swapped"),
        (1, False, True, "n4-switch"),
        (1, True, False, "n4-repeat-swapped"),
        (2, False, True, "n0-switch-back"),
    ]
    transport = None
    result = {
        "schema": "cnn-pipeline-v10-board-sequence-v1",
        "release_manifest_sha256": bundle["manifest_sha256"],
        "deployment_manifest_sha256": deployment["manifest_sha256"],
        "kernel_clock_hz": deployment["clock_hz"],
        "same_transport": True,
        "jobs": [],
    }
    started = time.perf_counter()
    cleanup = None
    primary = None
    try:
        transport = LinuxIoctlV10Transport(
            args.device,
            expected_parameter_manifest_words=bundle["parameter_manifest_words"])
        for index, (profile, swapped, expect_switch, label) in enumerate(plan):
            blocks = (12, 20, 4)[profile]
            values = case_files(args.cases_root, profile, swapped)
            job_started = time.perf_counter()
            item = run_paired_exact_case(
                transport, profile, blocks,
                bundle["parameter_contract"]["profiles"][profile]["params"],
                values[0], values[1], values[2], values[3], timeout_s=300.0)
            item["label"] = label
            item["swapped"] = swapped
            item["wall_ms"] = (time.perf_counter() - job_started) * 1000.0
            item["kernel_ms"] = (float(item["completion"]["job_cycles"]) *
                                 1000.0 / deployment["clock_hz"])
            if bool(item["completion"]["mode_switch_reset"]) != expect_switch:
                raise RuntimeError("unexpected profile-switch reset for " + label)
            result["jobs"].append(item)
            if index == 0:
                before = transport.get_status()
                raw = bytearray(_SUBMIT_STRUCT.pack(
                    profile, blocks, item["params_handle"],
                    item["activation_a_handle"], item["activation_b_handle"],
                    0, 0, 1))
                rejected_errno = None
                try:
                    transport._ioctl(_iow(0x45, _SUBMIT_STRUCT.size), raw)
                except OSError as error:
                    rejected_errno = error.errno
                if rejected_errno != errno.EINVAL:
                    raise RuntimeError("reserved submit was not rejected with EINVAL")
                after = transport.get_status()
                if before != after:
                    raise RuntimeError("rejected submit changed live hardware status")
                result["driver_reject"] = {
                    "kind": "reserved_field_nonzero",
                    "errno": rejected_errno,
                    "status_unchanged": True,
                    "after_first_valid_job": True,
                }
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
        output.mkdir(parents=True, exist_ok=True)
        (output / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "FZVA_SEQUENCE_EXACT_PASS",
                      "jobs": len(result["jobs"]),
                      "total_wall_ms": result["total_wall_ms"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
