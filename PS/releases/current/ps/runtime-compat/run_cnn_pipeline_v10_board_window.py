#!/usr/bin/env python3
"""Paired FZVA board runner core, held behind the packaging release gate.

This file performs no programming, module loading, SSH, or device discovery.
The callable runner accepts an already-open ABI10 transport whose constructor
has validated the packaged guard and parameter identities.
"""

import argparse
import hashlib
import json
import pathlib
import time

try:
    from cnn_ddr_v10_runtime import profile_contract, LinuxIoctlV10Transport
    from cnn_pipeline_v10_paired_runtime import V10PairedNormalRuntime
    from cnn_pipeline_v10_bundle import load_v10_release_bundle
    from cnn_pipeline_v10_deployment import load_v10_platform_deployment
except ImportError:
    from .cnn_ddr_v10_runtime import profile_contract, LinuxIoctlV10Transport
    from .cnn_pipeline_v10_paired_runtime import V10PairedNormalRuntime
    from .cnn_pipeline_v10_bundle import load_v10_release_bundle
    from .cnn_pipeline_v10_deployment import load_v10_platform_deployment


def _sha256(value):
    return hashlib.sha256(bytes(value)).hexdigest()


def _exact_bytes(value, expected, label):
    raw = bytes(value)
    if len(raw) != expected:
        raise ValueError("%s must contain exactly %d bytes" % (label, expected))
    return raw


def run_paired_exact_case(transport, profile, block_count, params,
                          input_a, expected_a, input_b, expected_b,
                          timeout_s=120.0):
    """Run one paired job through an identity-gated transport.

    Only each arena's first slot is initialized before SUBMIT. The output slot
    is selected by block parity; scratch and the other slot are hardware-owned.
    """
    contract = profile_contract(profile, block_count)
    params = _exact_bytes(params, contract["params_bytes"], "params")
    input_a = _exact_bytes(input_a, contract["slot_bytes"], "input A")
    input_b = _exact_bytes(input_b, contract["slot_bytes"], "input B")
    expected_a = _exact_bytes(expected_a, contract["slot_bytes"], "expected A")
    expected_b = _exact_bytes(expected_b, contract["slot_bytes"], "expected B")
    if input_a == input_b:
        raise ValueError("paired board case requires two distinct images")

    params_handle = transport.alloc(contract["params_bytes"])
    arena_a_handle = transport.alloc(contract["arena_bytes"])
    arena_b_handle = transport.alloc(contract["arena_bytes"])
    transport.upload(params_handle, 0, params)
    transport.upload(arena_a_handle, 0, input_a)
    transport.upload(arena_b_handle, 0, input_b)
    status_before = transport.get_status()
    descriptor = transport.submit(
        profile, block_count, params_handle, arena_a_handle, arena_b_handle)
    completion = transport.wait_complete(profile, timeout_s)
    output_offset = contract["output_offset_bytes"]
    actual_a = transport.download(arena_a_handle, output_offset,
                                  contract["slot_bytes"])
    actual_b = transport.download(arena_b_handle, output_offset,
                                  contract["slot_bytes"])
    if actual_a != expected_a:
        raise RuntimeError("FZVA paired output A is not word exact")
    if actual_b != expected_b:
        raise RuntimeError("FZVA paired output B is not word exact")
    return {
        "schema": "cnn-pipeline-v10-board-paired-case-v1",
        "execution": "board_linux_ioctl_fzva_abi10_paired",
        "profile": profile,
        "block_count": block_count,
        "params_handle": params_handle,
        "activation_a_handle": arena_a_handle,
        "activation_b_handle": arena_b_handle,
        "params_sha256": _sha256(params),
        "input_a_sha256": _sha256(input_a),
        "input_b_sha256": _sha256(input_b),
        "expected_a_sha256": _sha256(expected_a),
        "expected_b_sha256": _sha256(expected_b),
        "actual_a_sha256": _sha256(actual_a),
        "actual_b_sha256": _sha256(actual_b),
        "byte_exact_a": True,
        "byte_exact_b": True,
        "descriptor": descriptor,
        "status_before": status_before,
        "completion": completion,
    }


def create_full_model_runtime(transport, parameter_contract,
                              expected_manifest_sha256, clients,
                              timeout_s=120.0):
    """Bind the three paired PL windows to the existing four PS partitions.

    ``clients`` must contain independent ``stem-prefix``, ``network1-bridge``,
    ``network3-bridge``, and ``suffix`` clients.  An isolated frame is run
    immediately with a mirrored, discarded hardware partner; callers do not
    need to implement a pairing queue.
    """
    return V10PairedNormalRuntime(
        transport, parameter_contract, expected_manifest_sha256,
        clients, timeout_s=timeout_s)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run one byte-exact paired V10.1 PL window")
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--deployment-manifest", required=True)
    parser.add_argument("--expected-deployment-sha256", required=True)
    parser.add_argument("--device", default="/dev/network10_v10")
    parser.add_argument("--profile", required=True, type=int, choices=(0, 1, 2))
    parser.add_argument("--input-a", required=True)
    parser.add_argument("--expected-a", required=True)
    parser.add_argument("--input-b", required=True)
    parser.add_argument("--expected-b", required=True)
    parser.add_argument("--timeout-s", type=float, default=300.0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if args.timeout_s <= 0:
        parser.error("--timeout-s must be positive")
    output = pathlib.Path(args.output_dir)
    if output.exists():
        raise RuntimeError("output path already exists: %s" % output)
    loaded = load_v10_release_bundle(
        args.bundle_root, args.expected_bundle_sha256)
    if loaded["manifest"].get("schema") != "cnn-pipeline-v10.1-release-bundle-v2":
        raise ValueError("board execution requires release bundle schema v2")
    deployment = load_v10_platform_deployment(
        args.deployment_manifest, args.expected_deployment_sha256,
        loaded["manifest_sha256"])
    profile = args.profile
    blocks = (12, 20, 4)[profile]
    transport = None
    cleanup = None
    primary = None
    started = time.perf_counter()
    try:
        transport = LinuxIoctlV10Transport(
            args.device,
            expected_parameter_manifest_words=loaded["parameter_manifest_words"])
        result = run_paired_exact_case(
            transport, profile, blocks,
            loaded["parameter_contract"]["profiles"][profile]["params"],
            pathlib.Path(args.input_a).read_bytes(),
            pathlib.Path(args.expected_a).read_bytes(),
            pathlib.Path(args.input_b).read_bytes(),
            pathlib.Path(args.expected_b).read_bytes(),
            timeout_s=args.timeout_s)
    except Exception as error:
        primary = error
        raise
    finally:
        if transport is not None:
            try:
                cleanup = transport.close()
            except Exception:
                if primary is None:
                    raise
    wall_ms = (time.perf_counter() - started) * 1000.0
    cycles = result["completion"].get("job_cycles")
    result.update({
        "release_manifest_sha256": loaded["manifest_sha256"],
        "deployment_manifest_sha256": deployment["manifest_sha256"],
        "kernel_clock_hz": deployment["clock_hz"],
        "kernel_ms": ((float(cycles) * 1000.0 / deployment["clock_hz"])
                      if isinstance(cycles, int) and cycles >= 0 else None),
        "wall_ms": wall_ms,
        "cleanup": cleanup,
    })
    output.mkdir(parents=True)
    (output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "FZVA_PAIRED_EXACT_PASS",
                      "profile": profile, "job_cycles": cycles,
                      "kernel_ms": result["kernel_ms"], "wall_ms": wall_ms},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["run_paired_exact_case", "create_full_model_runtime", "main"]
