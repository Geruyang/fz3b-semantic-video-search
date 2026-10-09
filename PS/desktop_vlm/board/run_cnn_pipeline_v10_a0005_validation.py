#!/usr/bin/env python3
"""Strict A0005 signed40 board validation.

The byte-exact/reuse/canary mechanics are shared with the proven A0004
validator.  This entry point adds the A0005 fixture identity, loads the
independent range proof and admission records, and opens only the A0005
identity-gated transport.  It performs no overlay, module, clock, or PL
operation.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import pathlib
import sys

from run_cnn_pipeline_v10_a0004_validation import (
    _validated_contract, run_exact_reuse_case, run_exact_suite)


FIXTURE_SCHEMA = "cnn-v10.5-a0005-board-validation-fixtures-v1"
CORE_ABI_TEXT = "0x000A0005"
COMBINED_MANIFEST_SHA256 = \
    "4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690"
FILE_NAMES = ("params", "input_a", "expected_a", "input_b", "expected_b")


def _sha(raw):
    return hashlib.sha256(bytes(raw)).hexdigest()


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


def load_fixture_manifest(path, expected_sha256):
    """Load four exact fixtures and bind them to the A0005 combined identity."""
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
            not isinstance(value.get("cases"), list) or not value["cases"]):
        raise ValueError("fixture manifest contract mismatch")
    loaded = []
    profiles = set()
    for case in value["cases"]:
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


def _write_json_exclusive(path, value):
    output = pathlib.Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def main(argv=None, transport_factory=None):
    parser = argparse.ArgumentParser(
        description="Run strict A0005 paired exact/reuse/canary validation")
    parser.add_argument("--fixture-manifest", required=True)
    parser.add_argument("--expected-fixture-manifest-sha256", required=True)
    parser.add_argument("--combined-manifest", required=True)
    parser.add_argument("--expected-combined-manifest-sha256", required=True)
    parser.add_argument("--admission", required=True)
    parser.add_argument("--expected-admission-sha256", required=True)
    parser.add_argument("--proof", required=True)
    parser.add_argument("--expected-proof-sha256", required=True)
    parser.add_argument("--device", default="/dev/network10_v10_signed40")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.expected_combined_manifest_sha256 != COMBINED_MANIFEST_SHA256:
        raise ValueError("A0005 combined manifest identity mismatch")

    fixture = load_fixture_manifest(
        args.fixture_manifest, args.expected_fixture_manifest_sha256)
    if set(case["profile"] for case in fixture["cases"]) != set(range(4)):
        raise ValueError("board exact suite requires profiles 0,1,2,3 exactly once")
    hardware_execution = transport_factory is None
    if hardware_execution:
        from cnn_ddr_v10_p3_dma_runtime import profile_contract
        from cnn_ddr_v10_signed40_candidate_runtime import \
            open_signed40_candidate
        from cnn_pipeline_v10_signed40_parameters import \
            load_v10_signed40_parameters
        parameters = load_v10_signed40_parameters(
            args.combined_manifest, args.expected_combined_manifest_sha256,
            args.admission, args.expected_admission_sha256,
            args.proof, args.expected_proof_sha256)
        transport = open_signed40_candidate(parameters, args.device)
        resolver = profile_contract
    else:
        transport, resolver = transport_factory(args)
    result = run_exact_suite(transport, fixture, resolver, args.timeout_s)
    # Shared mechanics are inherited, while every emitted record carries the
    # candidate identity used for this execution.
    result["schema"] = "cnn-v10.5-a0005-board-exact-suite-v1"
    for case in result["cases"]:
        case["schema"] = "cnn-v10.5-a0005-exact-reuse-case-v1"
    result.update({
        "hardware_execution": hardware_execution,
        "device": args.device,
        "core_abi": CORE_ABI_TEXT,
        "combined_parameter_manifest_sha256": COMBINED_MANIFEST_SHA256,
        "pw2_signed40_admission_sha256":
            _checked_sha(args.expected_admission_sha256, "admission"),
        "pw2_signed40_proof_sha256":
            _checked_sha(args.expected_proof_sha256, "proof"),
        "reject_gate": {
            "status": "NOT_RUN_BY_EXACT_CLI",
            "reason": "release-no-ila platform exposes no physical per-stage trace counters",
        },
    })
    _write_json_exclusive(args.output, result)
    print(json.dumps({"status": "PASS", "output":
                      str(pathlib.Path(args.output).resolve()),
                      "profiles": result["profiles"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["load_fixture_manifest", "main", "run_exact_reuse_case",
           "run_exact_suite"]
