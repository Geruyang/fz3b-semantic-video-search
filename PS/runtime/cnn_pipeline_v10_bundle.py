"""Strict loader for the portable V10.1 userspace release bundle."""

import hashlib
import json
import math
import os
import pathlib
import re

try:
    from cnn_ddr_v10_runtime import profile_contract
except ImportError:
    from .cnn_ddr_v10_runtime import profile_contract


SOURCE_SHA = {
    "v10_fixture": "83df8803b7a8eb08795c6c19d89538637f850df9044c407b90814d725f0079c4",
    "v5_parameter": "400ecf86365f5e387ce62d350b6e4f24ab34b1dd5d903142c7a139515e19f18a",
    "v5_scale": "59c4dde6427a95d7256800f861c76ba14a558029ac6eaec479afae31dc83db29",
    "v5_split_model": "26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed",
}
PROFILE_BLOCKS = {0: 12, 1: 20, 2: 4}
MODEL_NAMES = {"stem-prefix", "network1-bridge", "network3-bridge", "suffix"}


def _sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _checked_sha(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("%s must be a lowercase SHA256" % label)
    return value


def _child(root, relative, label):
    if not isinstance(relative, str) or not relative:
        raise ValueError("%s path is missing" % label)
    normalized = relative.replace("\\", "/")
    if (normalized.startswith("/") or ":" in normalized.split("/")[0] or
            any(part in ("", ".", "..") for part in normalized.split("/"))):
        raise ValueError("%s path is unsafe" % label)
    candidate = (root / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(root), str(candidate))) != str(root):
        raise ValueError("%s path escapes bundle" % label)
    return candidate


def _read_record(root, record, label):
    if not isinstance(record, dict):
        raise ValueError("%s file record is missing" % label)
    path = _child(root, record.get("path"), label)
    raw = path.read_bytes()
    if (isinstance(record.get("bytes"), bool) or record.get("bytes") != len(raw) or
            _checked_sha(record.get("sha256"), label + " SHA") != _sha_bytes(raw)):
        raise ValueError("%s extent or SHA mismatch" % label)
    return raw, path


def _c_define(raw, name, label):
    match = re.search(rb"(?m)^#define\s+" + name.encode("ascii") +
                      rb"\s+(0x[0-9a-fA-F]+|[0-9]+)(?:U|UL|ULL)?\s*(?:/\*.*)?$", raw)
    if match is None:
        raise ValueError("%s is missing %s" % (label, name))
    return int(match.group(1), 0)


def _sv_parameter(raw, name, label):
    match = re.search(name.encode("ascii") + rb"\s*=\s*32'h([0-9a-fA-F]+)", raw)
    if match is None:
        raise ValueError("%s is missing %s" % (label, name))
    return int(match.group(1), 16)


def load_v10_release_bundle(bundle_root, expected_manifest_sha256):
    root = pathlib.Path(bundle_root).resolve()
    raw = (root / "manifest.json").read_bytes()
    expected = _checked_sha(expected_manifest_sha256, "release manifest")
    if _sha_bytes(raw) != expected:
        raise ValueError("V10 release manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    schema = manifest.get("schema")
    if (schema not in {"cnn-pipeline-v10.1-release-bundle-v1",
                       "cnn-pipeline-v10.1-release-bundle-v2"} or
            manifest.get("identity") != {"core": "0x465A5641", "abi": "0x000A0001",
                                         "software_uapi": 10,
                                         "software_label": "sw10.1", "flags": 0} or
            manifest.get("source_manifests") != SOURCE_SHA or
            manifest.get("checks", {}).get("frozen_scale_values_only") is not True or
            manifest.get("checks", {}).get("board_or_pl_execution") is not False):
        raise ValueError("V10 release identity or provenance mismatch")
    identity = manifest.get("parameter_identity")
    wanted_words = [int(SOURCE_SHA["v10_fixture"][i:i + 8], 16)
                    for i in range(0, 64, 8)]
    if (not isinstance(identity, dict) or
            identity.get("sha256") != SOURCE_SHA["v10_fixture"] or
            identity.get("software_driver_words_be32") != wanted_words):
        raise ValueError("V10 parameter identity words mismatch")

    hardware = manifest.get("packaged_hardware_identity")
    if not isinstance(hardware, dict):
        raise ValueError("V10 packaged hardware identity is missing")
    component_raw, component_path = _read_record(
        root, hardware.get("component_xml"), "packaged component.xml")
    if (component_path.as_posix().split("/")[-2:] != ["hardware", "component.xml"] or
            not component_raw.strip().startswith(b"<?xml")):
        raise ValueError("V10 packaged component.xml is invalid")
    checks = manifest.get("checks", {})
    if checks.get("hardware_reads_parameter_manifest") is not False:
        raise ValueError("V10 parameter identity boundary is ambiguous")

    platform_identity = None
    if schema == "cnn-pipeline-v10.1-release-bundle-v2":
        platform = manifest.get("platform_contract")
        sources = platform.get("sources") if isinstance(platform, dict) else None
        expected_platform = {"core_id": "0x465A5641", "core_abi": "0x000A0001",
                             "guard_caps": "0x000007FF", "software_uapi": 10}
        if (not isinstance(sources, dict) or
                set(sources) != {"driver_uapi", "driver_regs", "driver_source",
                                 "guard_rtl", "guard_bd"} or
                platform.get("expected") != expected_platform):
            raise ValueError("V10 platform contract is incomplete")
        platform_raw = {name: _read_record(root, record, "platform " + name)[0]
                        for name, record in sources.items()}
        expected_values = (0x465A5641, 0x000A0001, 0x000007FF)
        uapi_values = (
            _c_define(platform_raw["driver_uapi"], "NETWORK10_V10_CORE_ID", "driver UAPI"),
            _c_define(platform_raw["driver_uapi"], "NETWORK10_V10_CORE_ABI", "driver UAPI"),
            _c_define(platform_raw["driver_uapi"], "NETWORK10_V10_GUARD_CAPS", "driver UAPI"),
        )
        regs_values = (
            _c_define(platform_raw["driver_regs"], "V10_CORE_ID", "driver regs"),
            _c_define(platform_raw["driver_regs"], "V10_CORE_ABI", "driver regs"),
            _c_define(platform_raw["driver_regs"], "V10_CORE_CAPS", "driver regs"),
        )
        if (_c_define(platform_raw["driver_uapi"], "NETWORK10_V10_ABI_VERSION",
                      "driver UAPI") != 10 or uapi_values != expected_values or
                regs_values != expected_values):
            raise ValueError("V10 driver identity constants mismatch")
        for source_name in ("guard_rtl", "guard_bd"):
            values = tuple(_sv_parameter(platform_raw[source_name], name, source_name)
                           for name in ("ID_VALUE", "ABI_VERSION_VALUE", "CAPS_VALUE"))
            if values != expected_values:
                raise ValueError("V10 guard identity constants mismatch")
        driver_source = platform_raw["driver_source"]
        for token in (b"V10_CORE_ID", b"V10_CORE_ABI", b"V10_CORE_CAPS",
                      b"software_parameter_manifest_words"):
            if token not in driver_source:
                raise ValueError("V10 driver source identity gate is incomplete")
        platform_identity = {
            "core_id": expected_values[0], "core_abi": expected_values[1],
            "guard_caps": expected_values[2], "software_uapi": 10,
            "source_sha256": {name: _sha_bytes(value)
                              for name, value in platform_raw.items()},
        }

    provenance_values = {}
    for name, sha in (("v10-fixture-manifest.json", SOURCE_SHA["v10_fixture"]),
                      ("v5-bundle-manifest.json", SOURCE_SHA["v5_parameter"]),
                      ("v5-scale-manifest.json", SOURCE_SHA["v5_scale"])):
        path = root / "provenance" / name
        provenance_raw = path.read_bytes()
        if _sha_bytes(provenance_raw) != sha:
            raise ValueError("V10 provenance manifest mismatch: %s" % name)
        provenance_values[name] = json.loads(provenance_raw.decode("utf-8"))
    model_manifest = root / "models" / "manifest.json"
    if _sha_bytes(model_manifest.read_bytes()) != SOURCE_SHA["v5_split_model"]:
        raise ValueError("V10 split model manifest mismatch")

    profiles = {}
    records = manifest.get("profiles")
    v10_records = {int(item["profile"]): item for item in
                   provenance_values["v10-fixture-manifest.json"]["repacked_parameters"]}
    v5_records = provenance_values["v5-bundle-manifest.json"]["profiles"]
    scale_records = provenance_values["v5-scale-manifest.json"]["profiles"]
    if not isinstance(records, dict) or set(records) != {"0", "1", "2"}:
        raise ValueError("V10 release profiles are incomplete")
    for profile in (0, 1, 2):
        item = records[str(profile)]
        cfg = profile_contract(profile, PROFILE_BLOCKS[profile])
        payload, unused_path = _read_record(root, item.get("parameter_file"),
                                            "profile %d params" % profile)
        input_scale = float(item.get("input_scale"))
        output_scale = float(item.get("output_scale"))
        provenance = item.get("scale_provenance")
        repack = v10_records[profile]
        v5_parameter = v5_records[str(profile)]["parameter_file"]
        frozen_scales = scale_records[str(profile)]["per_block"]
        if (item.get("profile") != profile or
                item.get("block_count") != PROFILE_BLOCKS[profile] or
                len(payload) != cfg["params_bytes"] or
                not math.isfinite(input_scale) or input_scale <= 0 or
                not math.isfinite(output_scale) or output_scale <= 0 or
                input_scale != float(frozen_scales[0]["scales"]["input"]) or
                output_scale != float(frozen_scales[-1]["scales"]["add"]) or
                repack["blocks"] != PROFILE_BLOCKS[profile] or
                repack["output"]["bytes"] != len(payload) or
                repack["output"]["sha256"] != _sha_bytes(payload) or
                repack["source"]["bytes"] != v5_parameter["bytes"] or
                repack["source"]["sha256"] != v5_parameter["sha256"] or
                not isinstance(provenance, dict) or
                provenance.get("manifest") != "provenance/v5-scale-manifest.json" or
                provenance.get("profile") != str(profile)):
            raise ValueError("profile %d release contract mismatch" % profile)
        profiles[profile] = {
            "params": payload,
            "params_sha256": _sha_bytes(payload),
            "input_scale": input_scale,
            "output_scale": output_scale,
        }

    models = manifest.get("models", {})
    model_files = models.get("files")
    if (models.get("manifest_sha256") != SOURCE_SHA["v5_split_model"] or
            not isinstance(model_files, dict) or set(model_files) != MODEL_NAMES):
        raise ValueError("V10 release model declaration mismatch")
    for name, record in model_files.items():
        _read_record(root, record, "model " + name)
    return {
        "manifest": manifest,
        "manifest_sha256": expected,
        "parameter_manifest_words": tuple(wanted_words),
        "component_xml_sha256": _sha_bytes(component_raw),
        "platform_identity": platform_identity,
        "parameter_contract": {"manifest_sha256": expected, "profiles": profiles},
        "model_root": str(root / "models"),
        "model_manifest": str(model_manifest),
        "model_manifest_sha256": SOURCE_SHA["v5_split_model"],
    }


__all__ = ["SOURCE_SHA", "load_v10_release_bundle"]
