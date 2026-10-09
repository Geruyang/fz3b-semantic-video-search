#!/usr/bin/env python3
"""Build the portable ABI10.1 userspace bundle from frozen, SHA-pinned inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil


V5_BUNDLE_SHA256 = "400ecf86365f5e387ce62d350b6e4f24ab34b1dd5d903142c7a139515e19f18a"
V5_SCALE_SHA256 = "59c4dde6427a95d7256800f861c76ba14a558029ac6eaec479afae31dc83db29"
V5_MODEL_SHA256 = "26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed"
V10_FIXTURE_SHA256 = "83df8803b7a8eb08795c6c19d89538637f850df9044c407b90814d725f0079c4"
PROFILE_BLOCKS = {0: 12, 1: 20, 2: 4}
MODEL_NAMES = ("stem-prefix", "network1-bridge", "network3-bridge", "suffix")


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path, expected_sha):
    actual = _sha(path)
    if actual != expected_sha:
        raise ValueError("frozen manifest SHA mismatch: %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def _materialize(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(str(source), str(target))
        return "hardlink"
    except OSError:
        shutil.copyfile(str(source), str(target))
        return "copy"


def _snapshot_copy(source, target):
    """Copy mutable source/contract files so a release cannot alias workspace edits."""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(source), str(target))
    return "copy"


def _file_record(root, path, materialization):
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def build(v10_root, v5_root, model_root, component_xml, driver_uapi,
          driver_regs, driver_source, guard_rtl, guard_bd, output):
    v10_root = pathlib.Path(v10_root).resolve()
    v5_root = pathlib.Path(v5_root).resolve()
    model_root = pathlib.Path(model_root).resolve()
    component_xml = pathlib.Path(component_xml).resolve()
    platform_sources = {
        "driver_uapi": pathlib.Path(driver_uapi).resolve(),
        "driver_regs": pathlib.Path(driver_regs).resolve(),
        "driver_source": pathlib.Path(driver_source).resolve(),
        "guard_rtl": pathlib.Path(guard_rtl).resolve(),
        "guard_bd": pathlib.Path(guard_bd).resolve(),
    }
    output = pathlib.Path(output).resolve()
    if output.exists():
        raise RuntimeError("output path already exists: %s" % output)
    if not component_xml.is_file():
        raise RuntimeError("packaged HLS component.xml is missing: %s" % component_xml)
    missing = [str(path) for path in platform_sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError("platform contract source is missing: %s" % ", ".join(missing))

    v10_manifest_path = v10_root / "manifest.json"
    v5_manifest_path = v5_root / "manifest.json"
    scale_manifest_path = v5_root / "scale-manifest.json"
    model_manifest_path = model_root / "manifest.json"
    v10 = _read_json(v10_manifest_path, V10_FIXTURE_SHA256)
    v5 = _read_json(v5_manifest_path, V5_BUNDLE_SHA256)
    scales = _read_json(scale_manifest_path, V5_SCALE_SHA256)
    models = _read_json(model_manifest_path, V5_MODEL_SHA256)

    repacked = {int(item["profile"]): item for item in v10["repacked_parameters"]}
    if set(repacked) != set(PROFILE_BLOCKS):
        raise ValueError("V10 fixture manifest profile set mismatch")
    if set(models.get("models", {})) != set(MODEL_NAMES):
        raise ValueError("split model manifest set mismatch")

    output.mkdir(parents=True)
    files = {}
    provenance = (
        (v10_manifest_path, output / "provenance" / "v10-fixture-manifest.json"),
        (v5_manifest_path, output / "provenance" / "v5-bundle-manifest.json"),
        (scale_manifest_path, output / "provenance" / "v5-scale-manifest.json"),
        (model_manifest_path, output / "models" / "manifest.json"),
    )
    for source, target in provenance:
        mode = _materialize(source, target)
        files[target.relative_to(output).as_posix()] = _file_record(output, target, mode)

    profiles = {}
    for profile in (0, 1, 2):
        source = v10_root / ("profile%d-params-%d-blocks-v10.1.bin" %
                             (profile, PROFILE_BLOCKS[profile]))
        target = output / "params" / ("profile%d.bin" % profile)
        mode = _materialize(source, target)
        record = _file_record(output, target, mode)
        files[record["path"]] = record
        repack = repacked[profile]
        v5_record = v5["profiles"][str(profile)]["parameter_file"]
        scale_record = scales["profiles"][str(profile)]
        blocks = scale_record["per_block"]
        if (repack["blocks"] != PROFILE_BLOCKS[profile] or
                repack["output"]["bytes"] != record["bytes"] or
                repack["output"]["sha256"] != record["sha256"] or
                repack["source"]["bytes"] != v5_record["bytes"] or
                repack["source"]["sha256"] != v5_record["sha256"] or
                len(blocks) != PROFILE_BLOCKS[profile]):
            raise ValueError("profile %d frozen parameter chain mismatch" % profile)
        first = float(blocks[0]["scales"]["input"])
        last = float(blocks[-1]["scales"]["add"])
        if first <= 0 or last <= 0:
            raise ValueError("profile %d scale is not positive" % profile)
        profiles[str(profile)] = {
            "profile": profile,
            "block_count": PROFILE_BLOCKS[profile],
            "parameter_file": record,
            "input_scale": first,
            "output_scale": last,
            "scale_provenance": {
                "manifest": "provenance/v5-scale-manifest.json",
                "profile": str(profile),
                "input": "per_block[0].scales.input",
                "output": "per_block[-1].scales.add",
            },
        }

    model_records = {}
    for name in MODEL_NAMES:
        declaration = models["models"][name]
        source = model_root / declaration["path"]
        target = output / "models" / declaration["path"]
        mode = _materialize(source, target)
        record = _file_record(output, target, mode)
        if (record["bytes"] != declaration["bytes"] or
                record["sha256"] != declaration["sha256"]):
            raise ValueError("split model identity mismatch: %s" % name)
        files[record["path"]] = record
        model_records[name] = record

    component_target = output / "hardware" / "component.xml"
    component_mode = _snapshot_copy(component_xml, component_target)
    component_record = _file_record(output, component_target, component_mode)
    files[component_record["path"]] = component_record

    platform_records = {}
    for name, source in platform_sources.items():
        target = output / "platform-contract" / source.name
        mode = _snapshot_copy(source, target)
        record = _file_record(output, target, mode)
        files[record["path"]] = record
        platform_records[name] = record

    parameter_words = [int(V10_FIXTURE_SHA256[index:index + 8], 16)
                       for index in range(0, 64, 8)]
    manifest = {
        "schema": "cnn-pipeline-v10.1-release-bundle-v2",
        "identity": {"core": "0x465A5641", "abi": "0x000A0001",
                     "software_uapi": 10, "software_label": "sw10.1", "flags": 0},
        "parameter_identity": {
            "source_manifest": "provenance/v10-fixture-manifest.json",
            "sha256": V10_FIXTURE_SHA256,
            "software_driver_words_be32": parameter_words,
        },
        "packaged_hardware_identity": {
            "component_xml": component_record,
            "binding_scope": "release manifest binds packaged IP metadata; hardware has no parameter-manifest hash register",
        },
        "platform_contract": {
            "sources": platform_records,
            "expected": {"core_id": "0x465A5641", "core_abi": "0x000A0001",
                         "guard_caps": "0x000007FF", "software_uapi": 10},
            "offline_checks": [
                "driver UAPI and register constants match release identity",
                "guard and guard-BD default parameters match release identity",
                "driver source, guard sources, component.xml and parameter manifest are SHA-bound",
            ],
            "requires_board_execution": [
                "guard ID/ABI/CAPS register readback from the deployed bitstream",
                "driver GET_IDENTITY response and software parameter words",
                "six-master quiesce/reset/ACK behavior and paired inference",
            ],
        },
        "source_manifests": {
            "v10_fixture": V10_FIXTURE_SHA256,
            "v5_parameter": V5_BUNDLE_SHA256,
            "v5_scale": V5_SCALE_SHA256,
            "v5_split_model": V5_MODEL_SHA256,
        },
        "profiles": profiles,
        "models": {
            "manifest": "models/manifest.json",
            "manifest_sha256": V5_MODEL_SHA256,
            "files": model_records,
        },
        "schedule": {
            "normal_profiles": [2, 0, 1],
            "ps_partitions": list(MODEL_NAMES),
            "single_frame": "mirror A into B immediately; discard shadow output",
            "shadow_counts_as_real_frame": False,
        },
        "files": files,
        "checks": {
            "frozen_scale_values_only": True,
            "v10_parameter_repack_chain_verified": True,
            "four_split_models_verified": True,
            "board_or_pl_execution": False,
            "hardware_reads_parameter_manifest": False,
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    return {"manifest": str(manifest_path), "manifest_sha256": _sha(manifest_path),
            "parameter_identity_sha256": V10_FIXTURE_SHA256}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v10-fixtures", required=True)
    parser.add_argument("--v5-bundle", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--component-xml", required=True)
    parser.add_argument("--driver-uapi", required=True)
    parser.add_argument("--driver-regs", required=True)
    parser.add_argument("--driver-source", required=True)
    parser.add_argument("--guard-rtl", required=True)
    parser.add_argument("--guard-bd", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.v10_fixtures, args.v5_bundle, args.models,
                           args.component_xml, args.driver_uapi, args.driver_regs,
                           args.driver_source, args.guard_rtl, args.guard_bd,
                           args.output), indent=2))


if __name__ == "__main__":
    main()
