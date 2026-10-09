#!/usr/bin/env python3
"""Build a complete A0005 package after final route/timing evidence exists."""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys


ROOT = pathlib.Path(__file__).resolve().parents[3]
BOARD = ROOT / "desktop_vlm/board"
sys.path.insert(0, str(BOARD))

from cnn_pipeline_v10_signed40_deployment import (  # noqa: E402
    CANDIDATE_CONTRACT_SHA256, CLOCK_CONTRACT, COMBINED_SHA256,
    DEBUG_PROFILE, IDENTITY, REQUIRED_FILES, REQUIRED_GATES, SCHEMA,
    SOURCE_MANIFEST_SHA256, TARGET, _canonical,
    load_v10_signed40_deployment)
from cnn_pipeline_v10_signed40_parameters import CHAIN_CONTRACT  # noqa: E402


INPUT_SCHEMA = "cnn-pipeline-v10.5-signed40-deployment-builder-input-v1"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("%s must be lowercase SHA256" % label)
    return value


def source_path(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError("%s source path is missing" % label)
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if (normalized.startswith("/") or ":" in parts[0] or
            any(part in ("", ".", "..") for part in parts)):
        raise ValueError("%s source path is unsafe" % label)
    path = (ROOT / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(ROOT), str(path))) != str(ROOT):
        raise ValueError("%s source escapes workspace" % label)
    return path


def safe_package_path(root, value, label):
    if not isinstance(value, str) or not value:
        raise ValueError("%s package path is missing" % label)
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if (normalized.startswith("/") or ":" in parts[0] or
            any(part in ("", ".", "..") for part in parts)):
        raise ValueError("%s package path is unsafe" % label)
    path = (root / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(root), str(path))) != str(root):
        raise ValueError("%s package path escapes output" % label)
    return path


def build(spec_path, output_path):
    spec_path = pathlib.Path(spec_path).resolve()
    output = pathlib.Path(output_path).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if (spec.get("schema") != INPUT_SCHEMA or
            spec.get("status") != "FINAL_INPUTS_APPROVED"):
        raise ValueError("A0005 deployment inputs remain pending")
    checked_sha(spec.get("base_release_manifest_sha256"),
                "base release manifest")
    if (spec.get("identity") != IDENTITY or spec.get("target") != TARGET or
            spec.get("chain_contract") != CHAIN_CONTRACT or
            spec.get("combined_parameter_manifest_sha256") != COMBINED_SHA256 or
            spec.get("candidate_source_manifest_sha256") !=
            SOURCE_MANIFEST_SHA256 or
            spec.get("candidate_contract_sha256") !=
            CANDIDATE_CONTRACT_SHA256 or
            _canonical(spec.get("clock")) != _canonical(CLOCK_CONTRACT) or
            _canonical(spec.get("debug_profile")) !=
            _canonical(DEBUG_PROFILE)):
        raise ValueError("A0005 deployment input identity mismatch")
    gates = spec.get("gates")
    if (not isinstance(gates, dict) or set(gates) != REQUIRED_GATES or
            any(gates[name] is not True for name in REQUIRED_GATES)):
        raise ValueError("A0005 deployment gates are incomplete")
    sources = spec.get("files")
    if not isinstance(sources, dict) or set(sources) != REQUIRED_FILES:
        raise ValueError("A0005 deployment source set is incomplete")

    output.mkdir(parents=True)
    package_files = {}
    for name in sorted(REQUIRED_FILES):
        record = sources[name]
        if not isinstance(record, dict):
            raise ValueError("A0005 source record %s is missing" % name)
        source = source_path(record.get("source_path"), name)
        raw = source.read_bytes()
        expected = checked_sha(record.get("sha256"), name)
        if sha(raw) != expected:
            raise ValueError("A0005 source %s SHA mismatch" % name)
        destination = safe_package_path(output, record.get("package_path"), name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(destination))
        package_files[name] = {
            "path": destination.relative_to(output).as_posix(),
            "bytes": len(raw), "sha256": expected}
    manifest = {
        "schema": SCHEMA, "status": "READY_FOR_BOARD_VALIDATION",
        "identity": IDENTITY, "target": TARGET,
        "base_release_manifest_sha256":
            spec["base_release_manifest_sha256"],
        "chain_contract": CHAIN_CONTRACT,
        "combined_parameter_manifest_sha256": COMBINED_SHA256,
        "candidate_source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "candidate_contract_sha256": CANDIDATE_CONTRACT_SHA256,
        "clock": CLOCK_CONTRACT, "debug_profile": DEBUG_PROFILE,
        "gates": gates, "files": package_files,
        "builder_spec_sha256": sha(spec_path.read_bytes()),
    }
    manifest_path = output / "manifest.json"
    manifest_raw = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_raw)
    digest = sha(manifest_raw)
    load_v10_signed40_deployment(
        manifest_path, digest, spec["base_release_manifest_sha256"],
        COMBINED_SHA256)
    receipt = {
        "schema": "cnn-pipeline-v10.5-signed40-deployment-builder-receipt-v1",
        "status": "READY_FOR_BOARD_VALIDATION", "pass": True,
        "manifest_sha256": digest,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "combined_parameter_manifest_sha256": COMBINED_SHA256,
        "file_count": len(package_files),
        "package_bytes": sum(item["bytes"] for item in package_files.values()),
        "board_operations": False,
    }
    (output / "receipt.json").write_bytes(
        (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode())
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.spec, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
