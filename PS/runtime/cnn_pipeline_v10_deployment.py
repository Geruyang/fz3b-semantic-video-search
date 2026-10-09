"""Strict manifest gate for a complete V10.1 FZ3B platform deployment.

The release bundle binds the IP, software and model contracts.  This separate
manifest binds the final full-platform artifacts that do not exist until the
Vivado platform and target-kernel module gates finish.  Loading this manifest
performs no device, network, module, overlay or PL operation.
"""

import hashlib
import json
import os
import pathlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


SCHEMA = "cnn-pipeline-v10.1-platform-deployment-v2"
IDENTITY = {
    "core_id": "0x465A5641",
    "core_abi": "0x000A0001",
    "guard_caps": "0x000007FF",
    "software_uapi": 10,
}
KERNEL_RELEASE = "4.14.0-xilinx-v2018.3"
CLOCK_IDENTITY_BASIS = "current-board-pl0-hz-x-implemented-mmcm-ratio"
REQUIRED_FILES = {
    "bitstream", "ltx", "dtbo", "full_platform_receipt",
    "address_map_receipt", "timing_receipt", "guard_validation_receipt",
    "driver_module", "driver_compile_receipt", "module_symvers",
    "factory_bitstream", "factory_driver",
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


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
    path = (root / pathlib.PurePosixPath(normalized)).resolve()
    if os.path.commonpath((str(root), str(path))) != str(root):
        raise ValueError("%s path escapes deployment package" % label)
    return path


def _record(root, value, label):
    if not isinstance(value, dict):
        raise ValueError("%s record is missing" % label)
    path = _child(root, value.get("path"), label)
    raw = path.read_bytes()
    if (isinstance(value.get("bytes"), bool) or value.get("bytes") != len(raw) or
            _checked_sha(value.get("sha256"), label + " SHA") != _sha(raw)):
        raise ValueError("%s extent or SHA mismatch" % label)
    return path


def _clock_identity(clock):
    identity = clock.get("identity")
    required = {
        "basis", "board_input_hz", "board_input_rechecked",
        "implemented_mmcm_m", "implemented_mmcm_d", "implemented_mmcm_o0",
        "master_clock", "generated_clock", "full_platform_receipt_sha256",
        "timing_receipt_sha256",
    }
    if not isinstance(identity, dict) or set(identity) != required:
        raise ValueError("V10 deployment clock identity is incomplete")
    if (identity.get("basis") != CLOCK_IDENTITY_BASIS or
            identity.get("board_input_rechecked") is not True or
            isinstance(identity.get("board_input_hz"), bool) or
            not isinstance(identity.get("board_input_hz"), int) or
            identity.get("board_input_hz") <= 0 or
            isinstance(identity.get("implemented_mmcm_d"), bool) or
            not isinstance(identity.get("implemented_mmcm_d"), int) or
            identity.get("implemented_mmcm_d") <= 0 or
            not isinstance(identity.get("master_clock"), str) or
            not identity.get("master_clock") or
            not isinstance(identity.get("generated_clock"), str) or
            not identity.get("generated_clock")):
        raise ValueError("V10 deployment clock identity is invalid")
    try:
        multiplier = Decimal(identity["implemented_mmcm_m"])
        output_divider = Decimal(identity["implemented_mmcm_o0"])
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("V10 deployment MMCM identity is invalid")
    if (not multiplier.is_finite() or not output_divider.is_finite() or
            multiplier <= 0 or output_divider <= 0):
        raise ValueError("V10 deployment MMCM identity is invalid")
    scaled_hz = (Decimal(identity["board_input_hz"]) * multiplier /
                 (Decimal(identity["implemented_mmcm_d"]) * output_divider))
    expected_hz = int(scaled_hz.to_integral_value(rounding=ROUND_HALF_UP))
    if clock.get("kernel_hz") != expected_hz:
        raise ValueError("V10 deployment kernel clock does not match its identity")
    _checked_sha(identity["full_platform_receipt_sha256"],
                 "clock full-platform receipt")
    _checked_sha(identity["timing_receipt_sha256"], "clock timing receipt")
    return identity


def load_v10_platform_deployment(manifest_path, expected_manifest_sha256,
                                 expected_release_manifest_sha256):
    """Validate one immutable, board-ready platform package manifest."""
    return _load_platform_package(
        manifest_path, expected_manifest_sha256, expected_release_manifest_sha256,
        SCHEMA, IDENTITY, {"kernel_release": KERNEL_RELEASE,
                           "device": "/dev/network10_v10",
                           "module": "cnn_ddr_v10_candidate"})


def _load_platform_package(manifest_path, expected_manifest_sha256,
                           expected_release_manifest_sha256,
                           expected_schema, expected_identity, expected_target,
                           extra_files=(), extra_gates=(), excluded_files=()):
    """Common checks; expected contracts come from trusted loader constants.

    The public A0001 loader above has no caller-supplied identity override.
    New hardware needs its own explicit loader and independently bound assets.
    """
    path = pathlib.Path(manifest_path).resolve()
    root = path.parent
    raw = path.read_bytes()
    if _sha(raw) != _checked_sha(expected_manifest_sha256, "deployment manifest"):
        raise ValueError("V10 deployment manifest SHA mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if (manifest.get("schema") != expected_schema or
            manifest.get("status") != "READY_FOR_BOARD_VALIDATION" or
            manifest.get("identity") != expected_identity or
            manifest.get("release_manifest_sha256") !=
            _checked_sha(expected_release_manifest_sha256, "release manifest")):
        raise ValueError("V10 deployment identity or release binding mismatch")
    target = manifest.get("target")
    if (not isinstance(target, dict) or
            any(target.get(key) != value for key, value in expected_target.items())):
        raise ValueError("V10 deployment target contract mismatch")
    clock = manifest.get("clock")
    if (not isinstance(clock, dict) or isinstance(clock.get("kernel_hz"), bool) or
            not isinstance(clock.get("kernel_hz"), int) or
            clock.get("kernel_hz") <= 0 or
            clock.get("domain") != "single-domain kernel/AXI"):
        raise ValueError("V10 deployment clock binding is incomplete")
    clock_identity = _clock_identity(clock)
    gates = manifest.get("gates")
    required_gates = {
        "all_rtl_profiles_pass", "rtl_stress_pass", "full_platform_route_pass",
        "internal_setup_met", "internal_hold_met", "guard_six_master_pass",
        "target_module_compile_pass", "restore_assets_verified",
    } | set(extra_gates)
    if (not isinstance(gates, dict) or set(gates) != required_gates or
            any(gates[name] is not True for name in required_gates)):
        raise ValueError("V10 deployment gates are incomplete")
    files = manifest.get("files")
    excluded = set(excluded_files)
    if not excluded.issubset(REQUIRED_FILES):
        raise ValueError("V10 deployment excluded artifact set is invalid")
    required_files = (REQUIRED_FILES | set(extra_files)) - excluded
    if not isinstance(files, dict) or set(files) != required_files:
        raise ValueError("V10 deployment artifact set is incomplete")
    resolved = {name: _record(root, files[name], name)
                for name in sorted(required_files)}
    if (clock_identity["full_platform_receipt_sha256"] !=
            files["full_platform_receipt"]["sha256"] or
            clock_identity["timing_receipt_sha256"] !=
            files["timing_receipt"]["sha256"]):
        raise ValueError("V10 deployment clock receipt binding mismatch")
    if resolved["bitstream"].suffix.lower() not in (".bit", ".bin"):
        raise ValueError("V10 deployment bitstream extension is invalid")
    if "ltx" in resolved and resolved["ltx"].suffix.lower() != ".ltx":
        raise ValueError("V10 deployment probe file must be .ltx")
    if resolved["dtbo"].suffix.lower() != ".dtbo":
        raise ValueError("V10 deployment overlay must be .dtbo")
    if resolved["driver_module"].suffix.lower() != ".ko":
        raise ValueError("V10 deployment driver must be a .ko")
    return {
        "manifest": manifest,
        "manifest_sha256": _sha(raw),
        "release_manifest_sha256": manifest["release_manifest_sha256"],
        "clock_hz": clock["kernel_hz"],
        "files": resolved,
    }


__all__ = ["SCHEMA", "IDENTITY", "KERNEL_RELEASE", "CLOCK_IDENTITY_BASIS",
           "REQUIRED_FILES",
           "load_v10_platform_deployment"]
