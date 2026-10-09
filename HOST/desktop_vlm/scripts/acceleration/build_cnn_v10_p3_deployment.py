#!/usr/bin/env python3
"""Build an immutable A0002/P3 deployment package from an approved input spec.

This is an offline copier and validator.  It performs no SSH, JTAG, overlay,
module, or device operation.  A pending template is intentionally rejected;
only a spec whose exact final artifacts and gates are populated can emit a
READY_FOR_BOARD_VALIDATION manifest.
"""
from __future__ import print_function

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import sys


REPO = pathlib.Path(__file__).resolve().parents[3]
BOARD = REPO / "desktop_vlm" / "board"
sys.path.insert(0, str(BOARD))

from cnn_pipeline_v10_chain_deployment import (  # noqa: E402
    CHAIN_CONTRACT, EXTRA_FILES, EXTRA_GATES, IDENTITY, SCHEMA, TARGET,
    load_v10_chain_deployment,
)
from cnn_pipeline_v10_deployment import (  # noqa: E402
    CLOCK_IDENTITY_BASIS, REQUIRED_FILES,
)


INPUT_SCHEMA = "cnn-pipeline-v10.2-deployment-builder-input-v2"
INPUT_READY = "FINAL_INPUTS_APPROVED"
RELEASE_SHA = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
CHAIN_SHA = "c62b9f49b1118916168a2ca7a4a63c56d51bba66a0921523af35d46495bbab99"
KNOWN_FILE_SHA = {
    "chain_parameter_manifest": CHAIN_SHA,
    "driver_module": "b166879d3773f915d361c2579aeac15bd7126ed99243879f5eb063f2c758c5ca",
    "driver_compile_receipt": "2d88c14d375ec3ede95cacfdecb195ef076a72fb130b52fe2befb9acec9a04a0",
    "module_symvers": "ed188d47135d6224f954bd018aff9b7da988650c8a08c61abed3235cc3168326",
    "factory_bitstream": "59e1a6176194eccc05603738ba3c2e71ea25c3c09cdf9dce47ed1ad1ddf5fc2e",
    "factory_driver": "a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f",
}
REQUIRED_GATES = {
    "all_rtl_profiles_pass", "rtl_stress_pass", "full_platform_route_pass",
    "internal_setup_met", "internal_hold_met", "guard_six_master_pass",
    "target_module_compile_pass", "restore_assets_verified",
} | set(EXTRA_GATES)
REQUIRED_PACKAGE_FILES = set(REQUIRED_FILES) | set(EXTRA_FILES)
DEBUG_PROFILE = {
    "debug_profile": "release-guard-only",
    "guard_ila_count": 1,
    "pipeline_ila_count": 0,
    "trace_pack_present": False,
    "mmio_trace_count": 12,
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("%s must be a lowercase SHA256" % label)
    return value


def _repo_source(relative, label):
    if not isinstance(relative, str) or not relative:
        raise ValueError("%s source path is missing" % label)
    normalized = relative.replace("\\", "/")
    if (normalized.startswith("/") or ":" in normalized.split("/")[0] or
            any(part in ("", ".", "..") for part in normalized.split("/"))):
        raise ValueError("%s source path is unsafe" % label)
    path = (REPO / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(REPO.resolve()), str(path))) != str(REPO.resolve()):
        raise ValueError("%s source path escapes repository" % label)
    return path


def _package_child(root, relative, label):
    if not isinstance(relative, str) or not relative:
        raise ValueError("%s package path is missing" % label)
    normalized = relative.replace("\\", "/")
    if (normalized.startswith("/") or ":" in normalized.split("/")[0] or
            any(part in ("", ".", "..") for part in normalized.split("/"))):
        raise ValueError("%s package path is unsafe" % label)
    path = (root / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(root.resolve()), str(path))) != str(root.resolve()):
        raise ValueError("%s package path escapes output" % label)
    return path


def _copy_record(output, record, label):
    if not isinstance(record, dict) or set(record) != {
            "source_path", "package_path", "sha256"}:
        raise ValueError("%s record is incomplete" % label)
    expected = _checked_sha(record["sha256"], label + " SHA")
    source = _repo_source(record["source_path"], label)
    raw_sha = _sha(source.read_bytes())
    if raw_sha != expected:
        raise ValueError("%s source SHA mismatch" % label)
    destination = _package_child(output, record["package_path"], label)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(source), str(destination))
    if _sha(destination.read_bytes()) != expected:
        raise ValueError("%s copied SHA mismatch" % label)
    return {"path": record["package_path"], "bytes": destination.stat().st_size,
            "sha256": expected}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _validate_debug_profile_binding(spec_profile, full_platform_record):
    """Require the final build receipt itself to report the frozen debug shape."""
    if _canonical(spec_profile) != _canonical(DEBUG_PROFILE):
        raise ValueError("deployment debug profile mismatch")
    if not isinstance(full_platform_record, dict):
        raise ValueError("full-platform receipt record is missing")
    expected = _checked_sha(full_platform_record.get("sha256"),
                            "full-platform receipt SHA")
    source = _repo_source(full_platform_record.get("source_path"),
                          "full-platform receipt")
    raw = source.read_bytes()
    if _sha(raw) != expected:
        raise ValueError("full-platform receipt source SHA mismatch")
    try:
        receipt = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("full-platform receipt is not valid JSON")
    if not isinstance(receipt, dict):
        raise ValueError("full-platform receipt is not a JSON object")
    actual = {name: receipt.get(name) for name in DEBUG_PROFILE}
    if _canonical(actual) != _canonical(DEBUG_PROFILE):
        raise ValueError("final build receipt debug profile mismatch")


def build(spec_path, output_path):
    spec_path = pathlib.Path(spec_path).resolve()
    output = pathlib.Path(output_path).resolve()
    if os.path.commonpath((str(REPO.resolve()), str(output))) != str(REPO.resolve()):
        raise ValueError("deployment output must stay inside the repository")
    spec_raw = spec_path.read_bytes()
    spec = json.loads(spec_raw.decode("utf-8"))
    if spec.get("schema") != INPUT_SCHEMA or spec.get("status") != INPUT_READY:
        raise ValueError("deployment input spec is pending or has the wrong schema")
    if spec.get("release_manifest_sha256") != RELEASE_SHA:
        raise ValueError("base release manifest binding mismatch")
    if spec.get("identity") != IDENTITY or spec.get("target") != TARGET:
        raise ValueError("A0002 target identity mismatch")
    if spec.get("chain_contract") != CHAIN_CONTRACT:
        raise ValueError("P3 shared-arena chain contract mismatch")
    gates = spec.get("gates")
    if (not isinstance(gates, dict) or set(gates) != REQUIRED_GATES or
            any(gates[name] is not True for name in REQUIRED_GATES)):
        raise ValueError("deployment gates are incomplete")
    sources = spec.get("files")
    if not isinstance(sources, dict) or set(sources) != REQUIRED_PACKAGE_FILES:
        raise ValueError("deployment file inputs are incomplete")
    for name, expected in KNOWN_FILE_SHA.items():
        if sources[name].get("sha256") != expected:
            raise ValueError("%s is not the frozen artifact" % name)
    _validate_debug_profile_binding(spec.get("debug_profile"),
                                    sources["full_platform_receipt"])
    clock = spec.get("clock")
    if (not isinstance(clock, dict) or clock.get("domain") != "single-domain kernel/AXI" or
            not isinstance(clock.get("kernel_hz"), int) or
            isinstance(clock.get("kernel_hz"), bool) or clock.get("kernel_hz") <= 0 or
            not isinstance(clock.get("identity"), dict) or
            clock["identity"].get("basis") != CLOCK_IDENTITY_BASIS):
        raise ValueError("final clock identity is incomplete")
    provenance_inputs = spec.get("provenance")
    if not isinstance(provenance_inputs, dict) or not provenance_inputs:
        raise ValueError("final evidence provenance is missing")
    if output.exists():
        raise ValueError("refusing to overwrite deployment package")
    output.mkdir(parents=True)
    try:
        files = {name: _copy_record(output, sources[name], name)
                 for name in sorted(REQUIRED_PACKAGE_FILES)}
        provenance = {name: _copy_record(output, record, "provenance.%s" % name)
                      for name, record in sorted(provenance_inputs.items())}
        clock_identity = clock["identity"]
        if (clock_identity.get("full_platform_receipt_sha256") !=
                files["full_platform_receipt"]["sha256"] or
                clock_identity.get("timing_receipt_sha256") !=
                files["timing_receipt"]["sha256"]):
            raise ValueError("clock identity is not bound to final receipts")
        manifest = {
            "schema": SCHEMA,
            "status": "READY_FOR_BOARD_VALIDATION",
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "identity": IDENTITY,
            "release_manifest_sha256": RELEASE_SHA,
            "target": TARGET,
            "clock": clock,
            "gates": gates,
            "files": files,
            "chain_contract": CHAIN_CONTRACT,
            "debug_profile": DEBUG_PROFILE,
            "chain_parameter_manifest_sha256": CHAIN_SHA,
            "provenance": provenance,
            "scope": "READY authorizes the staged A0002 board-validation procedure; it is not a board inference result.",
        }
        manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        manifest_path = output / "manifest.json"
        manifest_path.write_bytes(manifest_raw)
        manifest_sha = _sha(manifest_raw)
        loaded = load_v10_chain_deployment(
            manifest_path, manifest_sha, RELEASE_SHA, CHAIN_SHA)
        if loaded["clock_hz"] != clock["kernel_hz"]:
            raise ValueError("post-build clock verification mismatch")
        receipt = {
            "schema": "cnn-pipeline-v10.2-deployment-package-receipt-v1",
            "pass": True,
            "input_spec": {"path": spec_path.relative_to(REPO).as_posix(),
                           "sha256": _sha(spec_raw)},
            "manifest": {"path": "manifest.json", "bytes": len(manifest_raw),
                         "sha256": manifest_sha},
            "required_file_count": len(files),
            "provenance_file_count": len(provenance),
            "debug_profile": DEBUG_PROFILE,
            "copy_policy": "independent byte copies; no hardlinks to mutable workspace sources",
            "board_operations": False,
        }
        receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (output / "receipt.json").write_bytes(receipt_raw)
        return manifest_sha, _sha(receipt_raw)
    except Exception:
        # A failed builder must not leave a directory that could be mistaken
        # for a complete package.  The caller retains the input spec evidence.
        shutil.rmtree(str(output))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-spec", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    manifest_sha, receipt_sha = build(args.input_spec, args.output_dir)
    print(json.dumps({"manifest_sha256": manifest_sha,
                      "receipt_sha256": receipt_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
