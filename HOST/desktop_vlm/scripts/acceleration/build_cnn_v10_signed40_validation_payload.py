#!/usr/bin/env python3
"""Build the immutable host-side A0005 exact-validation payload.

The arithmetic fixtures are byte-identical to the proven A0004 fixtures;
only their candidate identity manifest changes.  Existing files are hard
linked when possible so the host does not duplicate the 29 MiB payload.
"""
from __future__ import print_function

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shutil


ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE_FIXTURES = (ROOT / "artifacts/board-debug-20261008/acceleration/host/"
                   "network10-v10.4-a0004-validation-payload-004/fixtures")
COMBINED = (ROOT / "artifacts/board-debug-20261008/acceleration/host/"
            "network10-v10.5-pw2-signed40-combined-001/manifest.json")
ADMISSION = COMBINED.parent / "admission.json"
PROOF = (ROOT / "artifacts/board-debug-20261008/acceleration/host/"
         "network10-v10.5-pw2-signed40-proof-003/proof.json")
COMBINED_SHA = "4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690"
RUNTIME_FILES = (
    "cnn_ddr_v6_runtime.py", "cnn_ddr_v10_runtime.py",
    "cnn_ddr_v10_p3_dma_contract.py", "cnn_ddr_v10_p3_dma_runtime.py",
    "cnn_ddr_v10_signed40_candidate_runtime.py",
    "cnn_pipeline_v10_p3_dma_parameters.py",
    "cnn_pipeline_v10_signed40_parameters.py",
    "cnn_v10_pw2_signed40_contract.py",
    "run_cnn_pipeline_v10_a0004_validation.py",
    "run_cnn_pipeline_v10_a0005_validation.py",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def link_or_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(str(source), str(destination))
        return "hardlink"
    except OSError:
        shutil.copyfile(str(source), str(destination))
        return "copy"


def record(root, path, source=None, method=None):
    raw = path.read_bytes()
    value = {"path": path.relative_to(root).as_posix(),
             "bytes": len(raw), "sha256": sha(raw)}
    if source is not None:
        value["source_path"] = source.relative_to(ROOT).as_posix()
    if method is not None:
        value["materialization"] = method
    return value


def build(output):
    output = pathlib.Path(output).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    output.mkdir(parents=True)
    records = {}

    source_manifest = json.loads(
        (SOURCE_FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    fixture = dict(source_manifest)
    fixture["schema"] = "cnn-v10.5-a0005-board-validation-fixtures-v1"
    fixture["core_abi"] = "0x000A0005"
    fixture["combined_parameter_manifest_sha256"] = COMBINED_SHA
    fixture["generated_utc"] = datetime.datetime.now(
        datetime.timezone.utc).astimezone().isoformat()
    fixture["provenance"] = {
        "a0004_fixture_manifest_sha256":
            sha((SOURCE_FIXTURES / "manifest.json").read_bytes()),
        "fixture_payload_bytes_changed": False,
        "candidate_arithmetic_expected_unchanged": True,
    }
    for case in fixture["cases"]:
        for item in case["files"].values():
            source = SOURCE_FIXTURES / pathlib.PurePosixPath(item["path"])
            destination = output / "fixtures" / pathlib.PurePosixPath(item["path"])
            method = link_or_copy(source, destination)
            records[destination.relative_to(output).as_posix()] = record(
                output, destination, source, method)
    fixture_path = output / "fixtures/manifest.json"
    fixture_path.write_bytes(canonical(fixture))
    records["fixtures/manifest.json"] = record(
        output, fixture_path, SOURCE_FIXTURES / "manifest.json", "derived")

    for name in RUNTIME_FILES:
        source = ROOT / "desktop_vlm/board" / name
        destination = output / "runtime" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(destination))
        records[destination.relative_to(output).as_posix()] = record(
            output, destination, source, "copy")
    for name, source in (("combined-manifest.json", COMBINED),
                         ("admission.json", ADMISSION),
                         ("range-proof.json", PROOF)):
        destination = output / "contract" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(destination))
        records[destination.relative_to(output).as_posix()] = record(
            output, destination, source, "copy")

    if records["contract/combined-manifest.json"]["sha256"] != COMBINED_SHA:
        raise RuntimeError("combined manifest changed")
    package = {
        "schema": "cnn-v10.5-a0005-validation-payload-v1",
        "status": "PASS_HOST_PAYLOAD_NOT_BOARD_EXECUTED",
        "hardware_execution": False,
        "deployment_ready": False,
        "core_abi": "0x000A0005",
        "guard_caps": "0x00000fff",
        "combined_parameter_manifest_sha256": COMBINED_SHA,
        "files": records,
        "limitations": {
            "requires_final_routed_a0005_bit": True,
            "requires_matching_overlay_and_driver_load": True,
            "release_no_ila": True,
            "reject_zero_activation_gate": "unobservable and remains pending",
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_bytes(canonical(package))
    receipt = {
        "schema": "cnn-v10.5-a0005-validation-payload-receipt-v1",
        "status": "PASS_HOST_PAYLOAD_NOT_BOARD_EXECUTED",
        "manifest_sha256": sha(manifest_path.read_bytes()),
        "fixture_manifest_sha256": sha(fixture_path.read_bytes()),
        "file_count": len(records),
        "payload_bytes": sum(item["bytes"] for item in records.values()),
        "checks": {"all_source_hashes_bound": True,
                   "fixture_payload_bytes_unchanged": True,
                   "a0005_identity_manifest_derived": True,
                   "hardware_execution": False},
    }
    (output / "receipt.json").write_bytes(canonical(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.output), sort_keys=True))


if __name__ == "__main__":
    main()
