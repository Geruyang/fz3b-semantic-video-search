#!/usr/bin/env python3
"""Strict A0004 board-validation primitives.

The helpers accept an already identity-gated transport.  They do not program
PL, apply an overlay, load a module, contact a board, or weaken the deployment
gate.  Rejection testing additionally requires an observable twelve-counter
activation trace; it fails closed when the transport cannot provide it.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import pathlib
import sys


TRACE_NAMES = (
    "a_feed", "a_dw3", "a_dw7", "a_pw1", "a_pw2", "a_write",
    "b_feed", "b_dw3", "b_dw7", "b_pw1", "b_pw2", "b_write",
)
CANARY_BYTES = 4096
CANARY_PATTERN = bytes(bytearray((0xD1, 0x7E, 0xCA, 0x11,
                                  0xF0, 0x0D, 0x98, 0x76)))
FIXTURE_SCHEMA = "cnn-v10.4-a0004-board-validation-fixtures-v1"
CORE_ABI_TEXT = "0x000A0004"
COMBINED_MANIFEST_SHA256 = \
    "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9"
FILE_NAMES = ("params", "input_a", "expected_a", "input_b", "expected_b")


def _sha(raw):
    return hashlib.sha256(bytes(raw)).hexdigest()


def _exact(raw, size, label):
    value = bytes(raw)
    if len(value) != size:
        raise ValueError("%s must contain exactly %d bytes" % (label, size))
    return value


def _canary(size=CANARY_BYTES):
    return (CANARY_PATTERN * ((size + len(CANARY_PATTERN) - 1) //
                              len(CANARY_PATTERN)))[:size]


def _check_exact(actual, expected, label):
    actual = bytes(actual)
    expected = bytes(expected)
    if len(actual) != len(expected):
        raise RuntimeError("%s extent differs" % label)
    if actual != expected:
        first = next(index for index, pair in enumerate(zip(actual, expected))
                     if pair[0] != pair[1])
        raise RuntimeError(
            "%s is not byte exact: word=%d lane=%d actual=%d expected=%d" %
            (label, first // 16, first % 16, actual[first], expected[first]))


def _checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(character not in "0123456789abcdef" for character in value)):
        raise ValueError("%s must be lowercase SHA256" % label)
    return value


def _safe_child(root, relative, label):
    if not isinstance(relative, str) or not relative:
        raise ValueError("%s path is missing" % label)
    normalized = relative.replace("\\", "/")
    parts = normalized.split("/")
    if (normalized.startswith("/") or ":" in parts[0] or
            any(part in ("", ".", "..") for part in parts)):
        raise ValueError("%s path is unsafe" % label)
    path = (root / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(root.resolve()), str(path))) != str(root.resolve()):
        raise ValueError("%s path escapes fixture package" % label)
    return path


def _validated_contract(contract):
    required = ("params_bytes", "arena_bytes", "input_bytes",
                "output_bytes", "output_offset_bytes")
    if not isinstance(contract, dict) or any(
            isinstance(contract.get(name), bool) or
            not isinstance(contract.get(name), int) or
            contract.get(name) < (0 if name == "output_offset_bytes" else 1)
            for name in required):
        raise ValueError("A0004 profile contract is incomplete")
    if (contract["output_offset_bytes"] > contract["arena_bytes"] or
            contract["output_bytes"] >
            contract["arena_bytes"] - contract["output_offset_bytes"] or
            contract["input_bytes"] > contract["arena_bytes"]):
        raise ValueError("A0004 profile contract exceeds the arena")
    return contract


def load_fixture_manifest(path, expected_sha256):
    """Load a self-contained fixture manifest and bind every input byte."""
    manifest_path = pathlib.Path(path).resolve()
    raw = manifest_path.read_bytes()
    digest = _checked_sha(expected_sha256, "fixture manifest")
    if _sha(raw) != digest:
        raise ValueError("fixture manifest SHA mismatch")
    value = json.loads(raw.decode("utf-8"))
    if (value.get("schema") != FIXTURE_SCHEMA or
            value.get("status") != "PASS_HOST_FIXTURES_ONLY" or
            value.get("core_abi") != CORE_ABI_TEXT or
            value.get("combined_parameter_manifest_sha256") !=
            COMBINED_MANIFEST_SHA256 or
            not isinstance(value.get("cases"), list) or
            not value["cases"]):
        raise ValueError("fixture manifest contract mismatch")
    loaded = []
    profiles = set()
    for index, case in enumerate(value["cases"]):
        profile = case.get("profile")
        blocks = case.get("block_count")
        if (isinstance(profile, bool) or not isinstance(profile, int) or
                not 0 <= profile < 4 or profile in profiles or
                isinstance(blocks, bool) or not isinstance(blocks, int) or
                blocks <= 0):
            raise ValueError("fixture case identity is invalid")
        profiles.add(profile)
        contract = dict(_validated_contract(case.get("contract")))
        records = case.get("files")
        if not isinstance(records, dict) or set(records) != set(FILE_NAMES):
            raise ValueError("fixture file set is incomplete")
        files = {}
        for name in FILE_NAMES:
            record = records[name]
            if not isinstance(record, dict):
                raise ValueError("fixture %s record is invalid" % name)
            file_path = _safe_child(manifest_path.parent, record.get("path"), name)
            payload = file_path.read_bytes()
            if (record.get("bytes") != len(payload) or
                    record.get("sha256") != _sha(payload)):
                raise ValueError("fixture %s SHA/extent mismatch" % name)
            files[name] = payload
        expected_sizes = {
            "params": contract["params_bytes"],
            "input_a": contract["input_bytes"],
            "input_b": contract["input_bytes"],
            "expected_a": contract["output_bytes"],
            "expected_b": contract["output_bytes"],
        }
        for name, size in expected_sizes.items():
            if len(files[name]) != size:
                raise ValueError("fixture %s differs from contract extent" % name)
        loaded.append({"profile": profile, "block_count": blocks,
                       "contract": contract, "files": files,
                       "case_id": case.get("case_id", "profile-%d" % profile)})
    return {"manifest_sha256": digest, "cases": loaded,
            "source": str(manifest_path)}


def _check_clean_completion(completion, profile):
    if (not isinstance(completion, dict) or
            completion.get("profile") != profile or
            completion.get("protocol_error") != 0 or
            completion.get("guard_error_flags") != 0 or
            isinstance(completion.get("job_cycles"), bool) or
            not isinstance(completion.get("job_cycles"), int) or
            completion.get("job_cycles") <= 0):
        raise RuntimeError("A0004 job returned an unclean completion")


def run_exact_reuse_case(transport, profile, block_count, params,
                         input_a, expected_a, input_b, expected_b,
                         contract, timeout_s=120.0):
    """Run normal and swapped jobs using one resident handle set.

    Both jobs verify every output byte.  A separate allocation tail, outside
    the declared arena, proves that the accelerator did not exceed the frozen
    arena extent.  The swapped job proves same-session handle and parameter
    reuse without reallocating.
    """
    contract = _validated_contract(contract)
    params = _exact(params, contract["params_bytes"], "params")
    input_a = _exact(input_a, contract["input_bytes"], "input A")
    input_b = _exact(input_b, contract["input_bytes"], "input B")
    expected_a = _exact(expected_a, contract["output_bytes"], "expected A")
    expected_b = _exact(expected_b, contract["output_bytes"], "expected B")
    if input_a == input_b:
        raise ValueError("A0004 paired validation requires distinct inputs")
    if timeout_s <= 0:
        raise ValueError("timeout must be positive")

    canary = _canary()
    params_handle = transport.alloc(contract["params_bytes"])
    arena_a = transport.alloc(contract["arena_bytes"] + len(canary))
    arena_b = transport.alloc(contract["arena_bytes"] + len(canary))
    transport.upload(params_handle, 0, params)
    for handle in (arena_a, arena_b):
        transport.upload(handle, contract["arena_bytes"], canary)

    jobs = []
    permutations = ((input_a, expected_a, input_b, expected_b, False),
                    (input_b, expected_b, input_a, expected_a, True))
    for left_in, left_expected, right_in, right_expected, swapped in permutations:
        transport.upload(arena_a, 0, left_in)
        transport.upload(arena_b, 0, right_in)
        before = transport.get_status()
        descriptor = transport.submit(
            profile, block_count, params_handle, arena_a, arena_b)
        completion = transport.wait_complete(profile, timeout_s)
        _check_clean_completion(completion, profile)
        offset = contract["output_offset_bytes"]
        actual_a = transport.download(arena_a, offset,
                                      contract["output_bytes"])
        actual_b = transport.download(arena_b, offset,
                                      contract["output_bytes"])
        _check_exact(actual_a, left_expected, "A0004 output A")
        _check_exact(actual_b, right_expected, "A0004 output B")
        _check_exact(transport.download(arena_a, contract["arena_bytes"],
                                        len(canary)), canary,
                     "A0004 arena A tail canary")
        _check_exact(transport.download(arena_b, contract["arena_bytes"],
                                        len(canary)), canary,
                     "A0004 arena B tail canary")
        jobs.append({
            "swapped": swapped, "descriptor": descriptor,
            "status_before": before, "completion": completion,
            "actual_a_sha256": _sha(actual_a),
            "actual_b_sha256": _sha(actual_b),
        })
    return {
        "schema": "cnn-v10.4-a0004-exact-reuse-case-v1",
        "pass": True, "profile": profile, "block_count": block_count,
        "word_exact": True, "tail_canary_unchanged": True,
        "same_session_swapped_reuse": True,
        "params_sha256": _sha(params), "input_a_sha256": _sha(input_a),
        "input_b_sha256": _sha(input_b),
        "expected_a_sha256": _sha(expected_a),
        "expected_b_sha256": _sha(expected_b), "jobs": jobs,
    }


def run_exact_suite(transport, fixture_manifest, contract_resolver,
                    timeout_s=120.0):
    """Run every manifest case on one identity-gated transport, then drain."""
    cleanup = None
    try:
        cases = fixture_manifest.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError("fixture suite is empty")
        # Resolve and compare all frozen contracts before the first allocation.
        for case in cases:
            runtime_contract = contract_resolver(
                case["profile"], case["block_count"])
            # The runtime contract deliberately contains additional execution
            # details (slots, residual offsets, and handles).  The fixture
            # package binds only the five byte extents that it owns.
            names = ("params_bytes", "arena_bytes", "input_bytes",
                     "output_bytes", "output_offset_bytes")
            if not isinstance(runtime_contract, dict):
                raise ValueError("frozen A0004 runtime contract is invalid")
            resolved = _validated_contract(
                {name: runtime_contract.get(name) for name in names})
            if resolved != case["contract"]:
                raise ValueError("fixture contract differs from frozen A0004 runtime")
        results = []
        for case in cases:
            files = case["files"]
            results.append(run_exact_reuse_case(
                transport, case["profile"], case["block_count"],
                files["params"], files["input_a"], files["expected_a"],
                files["input_b"], files["expected_b"], case["contract"],
                timeout_s))
        return_value = {
            "schema": "cnn-v10.4-a0004-board-exact-suite-v1",
            "status": "PASS", "pass": True,
            "fixture_manifest_sha256": fixture_manifest["manifest_sha256"],
            "profiles": [item["profile"] for item in results],
            "case_count": len(results), "cases": results,
        }
    finally:
        cleanup = transport.close()
        if (not isinstance(cleanup, dict) or
                cleanup.get("quiesce_confirmed") is not True or
                cleanup.get("all_handles_freed") is not True or
                cleanup.get("transport_closed") is not True):
            raise RuntimeError("A0004 transport cleanup was not complete")
    return_value["cleanup"] = cleanup
    return return_value


def _trace(transport):
    method = getattr(transport, "read_activation_trace", None)
    if not callable(method):
        raise RuntimeError("activation trace observability is unavailable")
    try:
        values = method()
    except (NotImplementedError, AttributeError):
        raise RuntimeError("activation trace observability is unavailable")
    if (not isinstance(values, dict) or set(values) != set(TRACE_NAMES) or
            any(isinstance(values[name], bool) or
                not isinstance(values[name], int) or values[name] < 0
                for name in TRACE_NAMES)):
        raise RuntimeError("activation trace record is invalid")
    return values


def run_reject_case(transport, profile, block_count, corrupted_params,
                    arena_bytes, timeout_s=30.0):
    """Prove protocol_error=2 before any observable activation operation.

    This intentionally requires a rejection-aware wait primitive and twelve
    per-stage activation counters.  Aggregate guard AXI counters cannot prove
    zero activation reads because parameter validation itself reads DDR.
    """
    params = bytes(corrupted_params)
    if not params or len(params) & 15 or arena_bytes <= 0 or arena_bytes & 15:
        raise ValueError("reject extents must be positive and 16-byte aligned")
    if timeout_s <= 0:
        raise ValueError("timeout must be positive")
    wait_reject = getattr(transport, "wait_reject", None)
    if not callable(wait_reject):
        raise RuntimeError("reject-aware completion is unavailable")
    trace_before = _trace(transport)
    image = _canary(arena_bytes)
    params_handle = transport.alloc(len(params))
    arena_a = transport.alloc(arena_bytes)
    arena_b = transport.alloc(arena_bytes)
    transport.upload(params_handle, 0, params)
    transport.upload(arena_a, 0, image)
    transport.upload(arena_b, 0, image)
    descriptor = transport.submit(
        profile, block_count, params_handle, arena_a, arena_b)
    completion = wait_reject(2, timeout_s)
    if completion.get("protocol_error") != 2:
        raise RuntimeError("reject did not return protocol_error=2")
    trace_after = _trace(transport)
    delta = {name: trace_after[name] - trace_before[name]
             for name in TRACE_NAMES}
    if any(delta.values()):
        raise RuntimeError("reject performed observable activation access")
    _check_exact(transport.download(arena_a, 0, arena_bytes), image,
                 "reject arena A")
    _check_exact(transport.download(arena_b, 0, arena_bytes), image,
                 "reject arena B")
    return {
        "schema": "cnn-v10.4-a0004-reject-case-v1", "pass": True,
        "profile": profile, "block_count": block_count,
        "protocol_error": 2, "descriptor": descriptor,
        "completion": completion, "activation_trace_delta": delta,
        "activation_trace_zero": True,
        "activation_canary_unchanged": True,
        "params_sha256": _sha(params),
    }


def _write_json_exclusive(path, value):
    output = pathlib.Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def main(argv=None, transport_factory=None):
    parser = argparse.ArgumentParser(
        description="Run strict A0004 paired exact/reuse/canary validation")
    parser.add_argument("--fixture-manifest", required=True)
    parser.add_argument("--expected-fixture-manifest-sha256", required=True)
    parser.add_argument("--combined-manifest", required=True)
    parser.add_argument("--expected-combined-manifest-sha256", required=True)
    parser.add_argument("--device", default="/dev/network10_v10_p3_dma")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.expected_combined_manifest_sha256 != COMBINED_MANIFEST_SHA256:
        raise ValueError("A0004 combined manifest identity mismatch")

    fixture = load_fixture_manifest(
        args.fixture_manifest, args.expected_fixture_manifest_sha256)
    if set(case["profile"] for case in fixture["cases"]) != set(range(4)):
        raise ValueError("board exact suite requires profiles 0,1,2,3 exactly once")
    hardware_execution = transport_factory is None
    if hardware_execution:
        from cnn_pipeline_v10_p3_dma_parameters import \
            load_v10_p3_dma_parameters
        from cnn_ddr_v10_p3_dma_runtime import (
            LinuxIoctlV10P3DmaTransport, profile_contract)
        parameters = load_v10_p3_dma_parameters(
            args.combined_manifest, args.expected_combined_manifest_sha256)
        transport = LinuxIoctlV10P3DmaTransport(
            args.device,
            expected_parameter_manifest_words=
            parameters["parameter_manifest_words"])
        resolver = profile_contract
    else:
        transport, resolver = transport_factory(args)
    result = run_exact_suite(transport, fixture, resolver, args.timeout_s)
    result.update({
        "hardware_execution": hardware_execution,
        "device": args.device,
        "core_abi": CORE_ABI_TEXT,
        "combined_parameter_manifest_sha256": COMBINED_MANIFEST_SHA256,
        "reject_gate": {
            "status": "NOT_RUN_BY_EXACT_CLI",
            "reason": "requires terminal reject mode plus physical per-stage trace observability",
        },
    })
    _write_json_exclusive(args.output, result)
    print(json.dumps({"status": "PASS", "output": str(pathlib.Path(args.output).resolve()),
                      "profiles": result["profiles"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["TRACE_NAMES", "load_fixture_manifest", "run_exact_reuse_case",
           "run_exact_suite", "run_reject_case", "main"]
